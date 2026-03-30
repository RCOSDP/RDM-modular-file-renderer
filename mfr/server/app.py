from mfr import settings
from mfr.server import settings as server_settings
from mfr.server.handlers.export import ExportHandler
from mfr.server.handlers.render import RenderHandler
from mfr.server.handlers.status import StatusHandler
from mfr.server.handlers.exporters import ExportersHandler
from mfr.server.handlers.renderers import RenderersHandler
from mfr.server.handlers.core import ExtensionsStaticFileHandler
from mfr.server.handlers.core import XrayStaticFileHandler
from mfr.version import __version__

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

logger = logging.getLogger(__name__)
access_logger = logging.getLogger('tornado.access')


def sig_handler(sig, frame):
    io_loop = tornado.ioloop.IOLoop.instance()

    def stop_loop():
        if len(asyncio.Task.all_tasks(io_loop)) == 0:
            io_loop.stop()
        else:
            io_loop.call_later(1, stop_loop)

    io_loop.add_callback_from_signal(stop_loop)


def almost_apache_style_log(handler):
    '''without status code and body length'''
    req = handler.request
    access_logger.info('%s - - [%s +0800] "%s %s %s" - - "%s" "%s"' %
                       (req.remote_ip, time.strftime("%d/%b/%Y:%X"), req.method,
                        req.uri,
                        req.version, getattr(req, 'referer', '-'),
                        req.headers['User-Agent']))


def make_app(debug):
    xray_recorder.configure(
        service='mfr',
        daemon_address='192.168.168.167:2000',
        sampling=False,
        context_missing='LOG_ERROR',
        plugins=('EC2Plugin',),
        dynamic_naming='*.perfin.rdm.nii.ac.jp',
    )
    patch_all()
    app = tornado.web.Application(
        [
            (r'/static/(.*)', XrayStaticFileHandler, {'path': server_settings.STATIC_PATH}),
            (r'/assets/(.*?)/(.*\..*)', ExtensionsStaticFileHandler),
            (r'/export', ExportHandler),
            (r'/exporters', ExportersHandler),
            (r'/render', RenderHandler),
            (r'/renderers', RenderersHandler),
            (r'/status', StatusHandler),
        ],
        debug=debug,
        log_function=almost_apache_style_log,
    )
    app.sentry_client = AsyncSentryClient(settings.SENTRY_DSN, release=__version__)
    return app


def serve():
    tornado.platform.asyncio.AsyncIOMainLoop().install()

    app = make_app(server_settings.DEBUG)

    ssl_options = None
    if server_settings.SSL_CERT_FILE and server_settings.SSL_KEY_FILE:
        ssl_options = {
            'certfile': server_settings.SSL_CERT_FILE,
            'keyfile': server_settings.SSL_KEY_FILE,
        }

    app.listen(
        server_settings.PORT,
        address=server_settings.ADDRESS,
        xheaders=server_settings.XHEADERS,
        max_buffer_size=server_settings.MAX_BUFFER_SIZE,
        ssl_options=ssl_options,
    )

    logger.info("Listening on {0}:{1}".format(server_settings.ADDRESS, server_settings.PORT))

    signal.signal(signal.SIGTERM, partial(sig_handler))
    asyncio.get_event_loop().set_debug(server_settings.DEBUG)
    asyncio.get_event_loop().run_forever()