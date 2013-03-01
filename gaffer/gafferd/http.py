# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy
import logging

# patch tornado IOLoop
from ..tornado_pyuv import IOLoop, install
install()

from tornado.web import Application
from tornado.httpserver import HTTPServer

from ..httpclient import make_uri
from ..loop import patch_loop
from ..util import bind_sockets, hostname
from . import http_handlers
from .http_handlers import sockjs
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
            handlers=None, **settings):

        self.uri = uri

        self.backlog = backlog
        self.ssl_options = ssl_options
        self.client = dict()

        # init lookupd
        self.hostname = hostname()
        self.broadcast_address = broadcast_address
        self.lookupd_addresses = lookupd_addresses
        self.clients = dict()

        if not ssl_options:
            self.client_ssl_options = {}
        else:
            self.client_ssl_options = {"certfile": ssl_options['certfile'],
                    "keyfile": ssl_options['keyfile']}

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
        for addr in self.lookupd_addresses:
            if addr.startswith("http"):
                addr = addr.replace("http", "ws")

            addr = make_uri(addr, "/ws")
            if addr in self.clients:
                return

            ssl_options = None
            if addr.startswith("wss"):
                ssl_options = self.client_ssl_options

            if ssl_options is None:
                client = LookupClient(self.loop, addr)
            else:
                client = LookupClient(self.loop, addr, ssl_options=ssl_options)

            self.clients[addr] = client
            client.start(on_exit_cb=self._on_exit_lookup)

            # identify the client
            broadcast_address = self.broadcast_address or self.hostname
            client.identify(self.hostname, self.port, broadcast_address,
                    PROTOCOL_VERSION)

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
