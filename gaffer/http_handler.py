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
        names = [name for name in m.processes]
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(names))

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
                i = 2
            m.ttou(name, i)
        elif action == "_restart":
            m.restart_process(name)

        self.write({"ok": True})

class StatusHandler(RequestHandler):

    def get(self, *args):
        m = self.settings.get('manager')
        name = args[0]

        try:
            info = m.get_process_info(name)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return
        ret = { "active": info['active'],
                "running": info['running'],
                "max_processes": info['max_processes'] }

        self.write(ret)

class HttpHandler(object):

    DEFAULT_HANDLERS = [
            (r'/', WelcomeHandler),
            (r'/processes', ProcessesHandler),
            (r'/processes/([^/]+)', ProcessHandler),
            (r'/processes/([^/]+)/(_[^/]+)$', ProcessManagerHandler),
            (r'/processes/([^/]+)/(_[^/]+)/(.*)$', ProcessManagerHandler),
            (r'/status/([^/]+)', StatusHandler)
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
