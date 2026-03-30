import pkg_resources
import tornado.web
from mfr.server.handlers import core


class RenderersHandler(core.XrayHandler):

    def get(self):
        """List available renderers"""

        renderers = {}
        for ep in pkg_resources.iter_entry_points(group='mfr.renderers'):
            renderers.update({ep.name: ep.load().__name__})

        self.write({
            'renderers': renderers,
        })
