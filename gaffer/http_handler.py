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

class ProcessesHandler(RequestHandler):

    def get(self, *args, **kwargs):
        m = self.settings.get('manager')
        running = self.get_argument('running', default="")

        if running.lower() == "1" or running == "true":
            processes = [pid for pid in m.running]
        else:
            processes = [name for name in m.processes]

        # send response
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(processes))

    def post(self, *args, **kwargs):
        try:
            obj = json.loads(self.request.body.decode('utf-8'))
        except ValueError:
            self.set_status(400)
            self.write({"error": "invalid_json"})
            return

        if not "name" or not "cmd" in obj:
            self.set_status(400)
            self.write({"error": "invalid_process_info"})
            return

        name = obj.pop("name")
        cmd = obj.pop("cmd")

        m = self.settings.get('manager')
        try:
            m.add_process(name, cmd, **obj)
        except KeyError:
            self.set_status(409)
            self.write({"error": "conflict"})
            return

        self.write({"ok": True})

class ProcessHandler(RequestHandler):

    def head(self, *args):
        m = self.settings.get('manager')
        name = args[0]
        if name in m.processes:
            self.set_status(200)
        else:
            self.set_status(404)

    def get(self, *args):
        m = self.settings.get('manager')
        name = args[0]

        try:
            info = m.get_process_info(name)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write(info)

    def delete(self, *args):
        m = self.settings.get('manager')
        name = args[0]

        try:
            m.remove_process(name)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write({"ok": True})

    def put(self, *args):
        m = self.settings.get('manager')
        name = args[0]

        try:
            obj = json.loads(self.request.body.decode('utf-8'))
        except ValueError:
            self.set_status(400)
            self.write({"error": "invalid_json"})
            return

        if not "cmd" in obj:
            self.set_status(400)
            self.write({"error": "invalid_process_info"})
            return

        if "name" in obj:
            del obj['name']

        cmd = obj.pop("cmd")
        try:
            m.update(name, cmd, **obj)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write({"ok": True})

class ProcessManagerHandler(RequestHandler):

    def post(self, *args):
        m = self.settings.get('manager')
        name = args[0]

        if name not in m.processes:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        action = args[1]
        if action == "_start":
            m.start_process(name)
        elif action == "_stop":
            m.stop_process(name)
        elif action == "_add":
            if len(args) > 2:
                i = int(args[2])
            else:
                i = 1
            m.ttin(name, i)
        elif action == "_sub":
            if len(args) > 2:
                i = int(args[2])
            else:
                i = 1
            m.ttou(name, i)
        elif action == "_restart":
            m.restart_process(name)
        elif action == "_signal":
            if len(args) < 2:
                self.set_status(400)
                self.write({"error": "no_signal_number"})
                return
            else:
                signum = int(args[2])
            m.send_signal(name, signum)
        else:
            self.set_status(404)
            self.write({"error": "resource_not_found"})
            return

        self.write({"ok": True})

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


class HttpEndpoint(object):

    def __init__(self, uri='127.0.0.1:5000', backlog=128,
            ssl_options=None):
        # uri should be a list
        if isinstance(uri, six.string_types):
            self.uri = [uri]
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

        print("%s bound" % sock)

        # start the server
        self.server.start()

    def stop(self):
        self.server.stop()

    def restart(self):
        self.server.stop()
        self._start_server()

class HttpHandler(object):
    """ simple HTTP controller for gaffer.

    This controller can listen on multiple endpoints (tcp or unix
    sockets) with different options. Each endpoint can also listen on
    different interfaces """

    DEFAULT_HANDLERS = [
            (r'/', WelcomeHandler),
            (r'/processes', ProcessesHandler),
            (r'/processes/([^/]+)', ProcessHandler),
            (r'/processes/([^/]+)/(_[^/]+)$', ProcessManagerHandler),
            (r'/processes/([^/]+)/(_[^/]+)/(.*)$', ProcessManagerHandler),
            (r'/status/([^/]+)', StatusHandler)
    ]

    def __init__(self, endpoints=[], handlers=None):
        self.endpoints = endpoints or []
        if not endpoints: # if no endpoints passed add a default
            self.endpoints.append(HttpEndpoint())

        # set http handlers
        self.handlers = self.DEFAULT_HANDLERS
        self.handlers.extend(handlers or [])

    def start(self, loop, manager):
        self.loop = loop
        self.manager = manager
        self.app = Application(self.handlers, manager=self.manager)

        # start endpoints
        for endpoint in self.endpoints:
            print("start %s" % endpoint)
            endpoint.start(self.loop, self.app)
            print("%s started" % endpoint)

    def stop(self):
        for endpoint in self.endpoints:
            endpoint.stop()

    def restart(self):
        for endpoint in self.endpoints:
            endpoint.restart()
