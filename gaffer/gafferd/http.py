# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy
import socket

# patch tornado IOLoop
from ..tornado_pyuv import IOLoop, install
install()

import six
from tornado import netutil
from tornado.web import Application
from tornado.httpserver import HTTPServer

from ..loop import patch_loop
from ..util import parse_address, is_ipv6
from . import http_handlers
from .http_handlers import sockjs

DEFAULT_HANDLERS = [
        (r'/', http_handlers.WelcomeHandler),
        (r'/ping', http_handlers.PingHandler),
        (r'/version', http_handlers.VersionHandler),
        (r'/([0-9^/]+)', http_handlers.ProcessIdHandler),
        (r'/([0-9^/]+)/signal$', http_handlers.ProcessIdSignalHandler),
        (r'/([0-9^/]+)/stats$', http_handlers.ProcessIdStatsHandler),
        (r'/pids', http_handlers.AllProcessIdsHandler),
        (r'/sessions', http_handlers.SessionsHandler),
        (r'/jobs', http_handlers.AllJobsHandler),
        (r'/jobs/([^/]+)', http_handlers.JobsHandler),
        (r'/jobs/([^/]+)/([^/]+)', http_handlers.JobHandler),
        (r'/jobs/([^/]+)/([^/]+)/stats$', http_handlers.JobStatsHandler),
        (r'/jobs/([^/]+)/([^/]+)/numprocesses$', http_handlers.ScaleJobHandler),
        (r'/jobs/([^/]+)/([^/]+)/signal$', http_handlers.SignalJobHandler),
        (r'/jobs/([^/]+)/([^/]+)/state$', http_handlers.StateJobHandler),
        (r'/jobs/([^/]+)/([^/]+)/pids$', http_handlers.PidsJobHandler),
        (r'/watch', http_handlers.WatcherHandler),
        (r'/watch/([^/]+)$', http_handlers.WatcherHandler),
        (r'/watch/([^/]+)/([^/]+)$', http_handlers.WatcherHandler),
        (r'/watch/([^/]+)/([^/]+)/([^/]+)$', http_handlers.WatcherHandler),
        (r'/stats', http_handlers.StatsHandler),
        (r'/stats/([^/]+)', http_handlers.StatsHandler),
        (r'/stats/([^/]+)/([0-9^/]+)$', http_handlers.StatsHandler),
        (r'/streams/([0-9^/]+)/([^/]+)$', http_handlers.StreamHandler),
        (r'/wstreams/([0-9^/]+)$', http_handlers.WStreamHandler)
]

class HttpHandler(object):
    """ simple gaffer application that gives an HTTP API access to gaffer.
    """

    def __init__(self, uri='127.0.0.1:5000', backlog=128, ssl_options=None,
            handlers=None, **settings):

        self.uri = uri
        self.backlog = backlog
        self.ssl_options = ssl_options

        # set http handlers
        self.handlers = copy.copy(DEFAULT_HANDLERS)
        self.handlers.extend(handlers or [])

        # custom settings
        if 'manager' in settings:
            del settings['manager']
        self.settings = settings

    def start(self, loop, manager):
        self.loop = patch_loop(loop)
        self.io_loop = IOLoop(_loop=loop)
        self.manager = manager

        # add channel routes
        user_settings = { "manager": manager }
        channel_router = sockjs.SockJSRouter(http_handlers.ChannelConnection,
                "/channel", io_loop=self.io_loop, user_settings=user_settings)
        handlers = self.handlers + channel_router.urls

        # create the application
        self.app = Application(handlers, manager=self.manager,
                **self.settings)


        # start the server
        self._start_server()

    def stop(self):
        self.server.stop()
        self.io_loop.close(True)


    def restart(self):
        self.server.stop()
        self._start_server()

    def _start_server(self):
        self.server = HTTPServer(self.app, io_loop=self.io_loop,
                ssl_options=self.ssl_options)

        # initialize the socket
        addr = parse_address(self.uri)
        if isinstance(addr, six.string_types):
            raise RuntimeError("unix addresses aren't supported")

        if is_ipv6(addr[0]):
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
