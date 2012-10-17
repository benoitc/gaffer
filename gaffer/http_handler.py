# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy
import socket

# patch tornado IOLoop
from .tornado_pyuv import IOLoop, install
install()

import six
from tornado import netutil
from tornado.web import Application
from tornado.httpserver import HTTPServer

from .util import parse_address, is_ipv6
from . import http


DEFAULT_HANDLERS = [
        (r'/', http.WelcomeHandler),
        (r'/processes', http.ProcessesHandler),
        (r'/processes/([0-9^/]+)', http.ProcessIdHandler),
        (r'/processes/([^/]+)', http.ProcessHandler),
        (r'/processes/([0-9^/]+)/(_[^/]+)$', http.ProcessIdManageHandler),
        (r'/processes/([^/]+)/(_[^/]+)$', http.ProcessManagerHandler),
        (r'/processes/([0-9^/]+)/(_[^/]+)/(.*)$', http.ProcessIdManageHandler),
        (r'/processes/([^/]+)/(_[^/]+)/(.*)$', http.ProcessManagerHandler),
        (r'/status/([^/]+)', http.StatusHandler),
        (r'/watch', http.WatcherHandler),
        (r'/watch/([^/]+)$', http.WatcherHandler),
        (r'/watch/([^/]+)/([^/]+)$', http.WatcherHandler),
        (r'/watch/([^/]+)/([^/]+)/([^/]+)$', http.WatcherHandler),
        (r'/stats', http.StatsHandler),
        (r'/stats/([^/]+)', http.StatsHandler),
        (r'/stats/([^/]+)/([0-9^/]+)$', http.StatsHandler),
        (r'/streams/([0-9^/]+)/([^/]+)$', http.StreamHandler),
        (r'/wstreams/([0-9^/]+)$', http.WStreamHandler),
        (r'/groups', http.GroupsHandler),
        (r'/groups/([^/]+)$', http.GroupHandler),
        (r'/groups/([^/]+)/(_[^/]+)$', http.GroupHandler),
]

class HttpEndpoint(object):

    def __init__(self, uri='127.0.0.1:5000', backlog=128,
            ssl_options=None):
        # uri should be a list
        if isinstance(uri, six.string_types):
            self.uri = uri.split(",")
        else:
            self.uri = uri
        self.backlog = backlog
        self.ssl_options = ssl_options
        self.server = None
        self.loop = None
        self.io_loop = None

    def __str__(self):
        return ",".join(self.uri)

    def start(self, loop, app):
        self.loop = loop
        self.app = app
        self.io_loop = IOLoop(_loop=loop)
        self._start_server()

    def _start_server(self):
        self.server = HTTPServer(self.app, io_loop=self.io_loop,
                ssl_options=self.ssl_options)

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

    def stop(self):
        self.server.stop()
        self.io_loop.close(True)

    def restart(self):
        self.server.stop()
        self._start_server()

class HttpHandler(object):
    """ simple gaffer application that gives an HTTP API access to gaffer.

    This application can listen on multiple endpoints (tcp or unix
    sockets) with different options. Each endpoint can also listen on
    different interfaces """

    def __init__(self, endpoints=[], handlers=None):
        self.endpoints = endpoints or []
        if not endpoints: # if no endpoints passed add a default
            self.endpoints.append(HttpEndpoint())

        # set http handlers
        self.handlers = copy.copy(DEFAULT_HANDLERS)
        self.handlers.extend(handlers or [])

    def start(self, loop, manager):
        self.loop = loop
        self.manager = manager
        self.app = Application(self.handlers, manager=self.manager)

        # start endpoints
        for endpoint in self.endpoints:
            endpoint.start(self.loop, self.app)

    def stop(self):
        for endpoint in self.endpoints:
            endpoint.stop()

    def restart(self):
        for endpoint in self.endpoints:
            endpoint.restart()
