# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import json

from tornado.web import asynchronous
import pyuv

from .util import CorsHandler

class WatcherHandler(CorsHandler):
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
        self.preflight()
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
