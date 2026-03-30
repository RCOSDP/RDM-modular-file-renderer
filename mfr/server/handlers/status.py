from mfr.server.handlers import core
from mfr.version import __version__


class StatusHandler(core.XrayHandler):

    def get(self):
        """List information about modular-file-renderer status"""
        self.write({
            'status': 'up',
            'version': __version__
        })
