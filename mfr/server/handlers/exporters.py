import pkg_resources
import tornado.web
from mfr.server.handlers import core


class ExportersHandler(core.XrayHandler):

    def get(self):
        """List available exporters"""

        exporters = {}
        for ep in pkg_resources.iter_entry_points(group='mfr.exporters'):
            exporters.update({ep.name: ep.load().__name__})

        self.write({
            'exporters': exporters,
        })
