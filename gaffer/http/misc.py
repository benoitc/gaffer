# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.


from .. import __version__
from .util import CorsHandler

class WelcomeHandler(CorsHandler):

    def get(self):
        self.preflight()
        self.write({"welcome": "gaffer", "version": __version__})


class StatusHandler(CorsHandler):

    def get(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        name = args[0]

        try:
            ret = m.get_process_status(name)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write(ret)
