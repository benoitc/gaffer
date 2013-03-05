# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy
import logging
import ssl
import sys

# patch tornado IOLoop
from ..tornado_pyuv import IOLoop, install
install()

from tornado.web import Application
from tornado.httpserver import HTTPServer

from ..httpclient import make_uri
from ..loop import patch_loop
from .. import sockjs
from ..util import (bind_sockets, hostname, DEFAULT_CA_CERTS, is_ssl)
from . import http_handlers
from .lookup import LookupClient

LOGGER = logging.getLogger("gaffer")
PROTOCOL_VERSION = "0.1"
LOOKUP_EVENTS = ("load", "unload", "spawn", "stop_process", "exit")

DEFAULT_HANDLERS = [
        (r'/', http_handlers.WelcomeHandler),
        (r'/ping', http_handlers.PingHandler),
        (r'/version', http_handlers.VersionHandler),
        (r'/([0-9^/]+)', http_handlers.ProcessIdHandler),
        (r'/([0-9^/]+)/signal$', http_handlers.ProcessIdSignalHandler),
        (r'/([0-9^/]+)/stats$', http_handlers.ProcessIdStatsHandler),
        (r'/([0-9^/]+)/channel', http_handlers.PidChannel),
        (r'/([0-9^/]+)/channel/([^/]+)$', http_handlers.PidChannel),
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
        (r'/jobs/([^/]+)/([^/]+)/commit$', http_handlers.CommitJobHandler),
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

    def __init__(self, uri='127.0.0.1:5000', lookupd_addresses=[],
            broadcast_address = None, backlog=128, ssl_options=None,
            client_ssl_options=None, handlers=None, **settings):

        self.uri = uri
        self.backlog = backlog
        self.ssl_options = ssl_options
        self.client = dict()

        # init lookupd
        self.hostname = hostname()
        self.broadcast_address = broadcast_address
        self.lookupd_addresses = lookupd_addresses
        self.clients = dict()

        # client SSL options
        client_ssl_options = client_ssl_options or {}
        self.client_options = client_ssl_options.copy()
        # disable SSLv2
        # http://blog.ivanristic.com/2011/09/ssl-survey-protocol-support.html
        if sys.version_info >= (2, 7):
            self.client_options["ciphers"] = "DEFAULT:!SSLv2"
        else:
            # This is really only necessary for pre-1.0 versions
            # of openssl, but python 2.6 doesn't expose version
            # information.
            self.client_options["ssl_version"] = ssl.PROTOCOL_SSLv3

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

        # start the lookup client
        self._start_lookup()


    def stop(self):
        # stop the server
        self.server.stop()

        for event in LOOKUP_EVENTS:
            self.manager.events.unsubscribe(event, self._on_event)


        # close all lookups clients
        addresses = list(self.clients)
        for addr in addresses:
            client = self.clients.pop(addr)
            if not client.closed:
                client.close()

        # finally close the tornado loop
        self.io_loop.close(True)


    def restart(self):
        # stop the server
        self.server.stop()

        # close all lookups clients
        addresses = list(self.clients)
        for addr in addresses:
            client = self.clients.pop(addr)
            if not client.closed:
                client.close()

        # reinit the hostname
        self.hostname = hostname()
        self._start_server()

        # restart lookup clients
        self._start_lookup()

        # notify all jobs
        jobs = self.manager.jobs()
        for _, client in self.clients:
            [client.add_job(job_name) for job_name in jobs]


    def _start_server(self):
        self.server = HTTPServer(self.app, io_loop=self.io_loop,
                ssl_options=self.ssl_options)

        # initialize the socket
        sock = bind_sockets(self.uri, backlog=self.backlog)
        self.server.add_sockets(sock)
        self.port = sock[0].getsockname()[1]

        # start the server
        self.server.start()

    def _start_lookup(self):
        if not self.broadcast_address:
            if self.ssl_options:
                scheme = "https"
            else:
                scheme = "http"

            origin = "%s://%s:%s" % (scheme, self.hostname, self.port)
        else:
            origin = self.broadcast_address

        for addr in self.lookupd_addresses:
            if addr.startswith("http"):
                addr = addr.replace("http", "ws")

            addr = make_uri(addr, "/ws")
            if addr in self.clients:
                return

            # initialize the client
            options = {}
            if is_ssl(addr):
                options["ssl_options"] = self.client_options
            client = LookupClient(self.loop, addr, **options)

            # register the client
            self.clients[addr] = client

            # start the client
            client.start(on_exit_cb=self._on_exit_lookup)

            # identify the client
            # node name is its hostname for now
            client.identify(self.hostname, origin, PROTOCOL_VERSION)

            for event in LOOKUP_EVENTS:
                self.manager.events.subscribe(event, self._on_event)

    def _on_event(self, event, msg):
        if not self.clients:
            return

        if event == "load":
            args = (msg['name'],)
            lookup_event = "add_job"

        elif event == "unload":
            args = (msg['name'],)
            lookup_event = "remove_job"
        elif event == "spawn":
            args = (msg['name'], msg['pid'],)
            lookup_event = "add_process"
        elif event in ("stop_process", "exit"):
            args = (msg['name'], msg['pid'],)
            lookup_event = "remove_process"


        for _, client in self.clients.items():
            fun = getattr(client, lookup_event)
            fun(*args)

    def _on_exit_lookup(self, client):
        if client.url not in self.clients:
            return

        LOGGER.info("LOOKUP: %r exited" % client.url)
        try:
            del self.clients[client.url]
        except KeyError:
            pass
