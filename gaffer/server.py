# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .manager import get_manager
from .sig_handler import SigHandler
from .http_handler import HttpHandler

class Server(object):

    def __init__(self):
        self.sig_handler= SigHandler()
        self.http_handler = HttpHandler()
        self.controllers = [self.sig_handler, self.http_handler]
        self.manager = get_manager(controllers=self.controllers)

    def run(self):
        self.manager.run()


def run():
    s = Server()
    s.run()
