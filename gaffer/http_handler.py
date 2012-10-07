# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

import pyuv
# patch tornado IOLoop
from .tornado_pyuv import IOLoop, install
install()

import six
from tornado import netutil
from tornado.web import Application, RequestHandler
from tornado.httpserver import HTTPServer

from .util import parse_address, is_ipv6
from . import __version__

class WelcomeHandler(RequestHandler):

    def get(self):
        self.write({"welcome": "gaffer", "version": __version__})


class HttpHandler(object):

    DEFAULT_HANDLERS = [
            (r'/', WelcomeHandler)
    ]

    def __init__(self, uri='127.0.0.1:5000', backlog=128,
            ssl_options=None, handlers=None):

        # uri should be a list
        if isinstance(uri, six.string_types):
            self.uri = [uri]
        else:
            self.uri = uri
        self.backlog = backlog

        # set http handlers
        self.handlers = self.DEFAULT_HANDLERS
        #self.handlers.update(handlers or {})


    def start(self, loop, manager):
        self.loop = loop
        self.manager = manager

        # create default ioloop
        self.io_loop = IOLoop(_loop=loop)

        # finally start the server
        self._start_server()

    def stop(self):
        self.server.stop()

    def restart(self):
        self.server.stop()
        self._start_server()

    def _start_server(self):
        self.app = Application(self.handlers, manager=self.manager)
        self.server = HTTPServer(self.app, io_loop=self.io_loop)

        # bind the handler to needed interface
        for uri in self.uri:
            addr = parse_address(uri)
            if isinstance(addr, six.string_types):
                sock = netutil.bind_unix_socket(addr)
            elif is_ipv6(addr[0]):
                sock = netutil.bind_sockets(addr[1], address=addr[0],
                        family=socket.AF_INET6, backlog=self.backlog)
            else:
                sock = netutil.bind_sockets(addr[1], backlog=self.backlog)

            if isinstance(sock, list):
                for s in sock:
                    self.server.add_socket(s)
            else:
                self.server.add_socket(sock)

        # start the server
        self.server.start()
