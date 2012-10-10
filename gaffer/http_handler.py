# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import socket

# patch tornado IOLoop
from .tornado_pyuv import IOLoop, install
install()

import pyuv
import six
from tornado import netutil
from tornado.web import Application, RequestHandler, asynchronous
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

class ProcessIdHandler(RequestHandler):

    def head(self, *args):
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        if pid in m.running:
            self.set_status(200)
        else:
            self.set_status(404)


    def get(self, *args):
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        if pid in m.running:
            p = m.running[pid]
            try:
                info = m.get_process_info(p.name)
            except KeyError:
                self.set_status(404)
                self.write({"error": "not_found"})
                return
            self.write(info)
        else:
            self.set_status(404)
            self.write({"error": "not_found"})

    def delete(self, *args):
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        if pid in m.running:
            m.stop_process(pid)
            self.write({"ok": True})
        else:
            self.set_status(404)
            self.write({"error": "not_found"})

class ProcessIdManageHandler(RequestHandler):

    def post(self, *args):
        m = self.settings.get('manager')
        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return
        if pid in m.running:
            p = m.running[pid]
            action = args[1]
            if action == "_stop":
                m.stop_process(pid)
            elif action == "_signal":
                if len(args) < 2:
                    self.set_status(400)
                    self.write({"error": "no_signal_number"})
                    return
                else:
                    try:
                        signum = int(args[2])
                    except ValueError:
                        self.set_status(400)
                        self.write({"error": "bad_value"})
                        return
                    m.send_signal(pid, signum)

            self.write({"ok": True})
        else:
            self.set_status(404)
            self.write({"error": "not_found"})

class ProcessManagerHandler(RequestHandler):

    def get(self, *args):
        m = self.settings.get('manager')
        name = args[0]

        if name not in m.processes:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        action = args[1]
        extra = {}
        if action == "_pids":
            state = m.processes[name]
            pids = [p.id for p in state.running]
            extra = {"pids": pids}
        else:
            self.set_status(404)
            self.write({"error": "resource_not_found"})
            return

        json_obj = {"ok": True}
        json_obj.update(extra)
        self.write(json_obj)

    def post(self, *args):
        m = self.settings.get('manager')
        name = args[0]

        if name not in m.processes:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        action = args[1]
        extra = {}
        if action == "_start":
            m.start_process(name)
        elif action == "_stop":
            m.stop_process(name)
        elif action == "_add":
            if len(args) > 2:
                i = int(args[2])
            else:
                i = 1
            ret = m.ttin(name, i)
            extra = {"numprocesses": ret}
        elif action == "_sub":
            if len(args) > 2:
                i = int(args[2])
            else:
                i = 1
            ret = m.ttou(name, i)
            extra = {"numprocesses": ret}
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

        json_obj = {"ok": True}
        json_obj.update(extra)
        self.write(json_obj)

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


class WatcherHandler(RequestHandler):
    """ watcher handler used to watch process and manager events """

    MANAGER_EVENTS = ["start", "stop", "create", "update", "delete"]
    PROC_EVENTS = ["start", "stop", "spawn", "reap", "exit", "stop_pid"]

    def initialize(self, *args, **kwargs):
        self._heartbeat = None
        self._pattern = None
        self._feed = None
        self._closed = False

    @asynchronous
    def get(self, *args):
        self._feed = feed = self.get_argument('feed', default="longpoll")
        heartbeat = self.get_argument('heartbeat', default="true")
        m = self.settings.get('manager')

        if not args:
            pattern = "."
        else:
            pattern = ".".join(args)

        if len(args) == 1:
            if args[0].lower() not in self.MANAGER_EVENTS:
                self.set_status(404)
                self.write_error({"error": "bad_event_type"})
                self.finish()
                return
        elif len(args) == 3:
            if args[0].lower() not in self.PROC_EVENTS:
                self.set_status(404)
                self.write_error({"error": "bad_event_type"})
                self.finish()
                return

        # set heartbeta
        if heartbeat.lower() == "true":
            heartbeat = 60000
        else:
            try:
                heartbeat = int(heartbeat)
            except TypeError:
                heartbeat = False

        if heartbeat:
            self._heartbeat = pyuv.Timer(m.loop)
            self._heartbeat.start(self._on_heartbeat, heartbeat,
                    heartbeat)

        if feed == "eventsource":
            self.set_header("Content-Type", "text/event-stream")
        else:
            self.set_header("Content-Type", "application/json")
        self.set_header("Cache-Control", "no-cache")

        # subscribe to events
        self._pattern = pattern
        m.subscribe(pattern, self._on_event)


    def _on_heartbeat(self, handle):
        self.write("\n")

    def _on_event(self, evtype, msg):
        if self._feed == "eventsource":
            event = ["event: %s" % evtype,
                    "data: %s" % json.dumps(msg), ""]
            self.write("\r\n".join(event))
            self.flush()
        else:
            self.write("%s\r\n" % json.dumps(msg))
            self.finish()

    def _handle_disconnect(self):
        self._closed = True
        m = self.settings.get('manager')
        m.unsubscribe(self._pattern, self._on_event)
        if self._heartbeat is not None:
            self._heartbeat.close()


    def on_close_connection(self):
        self._handle_disconnect()

    def on_finish(self):
        if not self._closed:
            self._handle_disconnect()

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
            (r'/processes/([0-9^/]+)', ProcessIdHandler),
            (r'/processes/([^/]+)', ProcessHandler),
            (r'/processes/([0-9^/]+)/(_[^/]+)$', ProcessIdManageHandler),
            (r'/processes/([^/]+)/(_[^/]+)$', ProcessManagerHandler),
            (r'/processes/([0-9^/]+)/(_[^/]+)/(.*)$', ProcessIdManageHandler),
            (r'/processes/([^/]+)/(_[^/]+)/(.*)$', ProcessManagerHandler),
            (r'/status/([^/]+)', StatusHandler),
            (r'/watch', WatcherHandler),
            (r'/watch/([^/]+)$', WatcherHandler),
            (r'/watch/([^/]+)/([^/]+)$', WatcherHandler),
            (r'/watch/([^/]+)/([^/]+)/([^/]+)$', WatcherHandler),

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
            endpoint.start(self.loop, self.app)

    def stop(self):
        for endpoint in self.endpoints:
            endpoint.stop()

    def restart(self):
        for endpoint in self.endpoints:
            endpoint.restart()
