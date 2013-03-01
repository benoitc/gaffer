# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.


from ... import __version__
from .util import CorsHandler

class WelcomeHandler(CorsHandler):

    def get(self):
        self.preflight()
        self.write({"welcome": "gaffer", "version": __version__})

class VersionHandler(CorsHandler):

    def get(self):
        self.preflight()
        self.write({"name": "gaffer", "version": __version__})

class PingHandler(CorsHandler):

    def get(self):
        self.preflight()
        self.set_status(200)
        self.write("OK")
