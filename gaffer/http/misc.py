# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from tornado.web import RequestHandler

from .. import __version__

class WelcomeHandler(RequestHandler):

    def get(self):
        self.write({"welcome": "gaffer", "version": __version__})


class StatusHandler(RequestHandler):

    def get(self, *args):
        m = self.settings.get('manager')
        name = args[0]

        try:
            ret = m.get_process_status(name)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write(ret)
