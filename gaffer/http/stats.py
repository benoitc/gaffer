# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import json

from tornado.web import RequestHandler, asynchronous
import pyuv

class StatsHandler(RequestHandler):
    """ watcher handler used to watch processes stats in quasi rt """

    def initialize(self, *args, **kwargs):
        self._heartbeat = None
        self._feed = None
        self._closed = False
        self._source = None

    @asynchronous
    def get(self, *args):
        self._feed = feed = self.get_argument('feed', default="normal")
        heartbeat = self.get_argument('heartbeat', default="true")
        m = self.settings.get('manager')

        if not args:
            """ stream all process stats """
            self.set_status(200)
            self.set_header("Content-Type", "application/json")
            self.set_header("Transfer-Encoding", "chunked")

            self.write_chunk("[\r\n")
            pre = ""
            for info in m.processes_stats():
                line = "%s%s" % (pre, json.dumps(info))
                pre = ",\r\n"
                self.write_chunk(line)
            self.write_chunk("\r\n]")
            self.write_chunk("")
            self.finish()
        elif len(args) == 1:
            try:
                infos = m.get_process_stats(args[0])
            except KeyError:
                return self.send_not_found()

            if feed == "normal": # send the infos once
                self.set_header("Content-Type", "application/json")
                self.write(infos)
                self.finish()
            else:
                self.setup_stream(feed, m, heartbeat)
                m.monitor(args[0], self._on_event)
                self._source = m
        else:
            try:
                pid = int(args[1])
            except ValueError:
                self.set_status(400)
                self.write({"error": "bad_value"})
                self.finish()
                return

            if pid in m.running:
                p = m.running[pid]

                if feed == "normal": # send the infos once
                    self.set_header("Content-Type", "application/json")
                    self.write(p.info)
                    self.finish()
                else:
                    self.setup_stream(feed, m, heartbeat)
                    p.monitor(self._on_event)
                    self._source = p
            else:
                return self.send_not_found()

    def setup_stream(self, feed, m, heartbeat):
        self._feed = feed

        self.setup_heartbeat(heartbeat, m)
        if feed == "eventsource":
            self.set_header("Content-Type", "text/event-stream")
        else:
            self.set_header("Content-Type", "application/json")
        self.set_header("Cache-Control", "no-cache")

    def setup_heartbeat(self, heartbeat, m):
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

    def write_chunk(self, data):
        chunk = "".join(("%X\r\n" % len(data), data, "\r\n"))
        self.write(chunk)

    def send_not_found(self):
        self.set_status(404)
        self.write({"error": "not_found"})
        self.finish()

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
        self._source.unmonitor(self._on_event)
        if self._heartbeat is not None:
            self._heartbeat.close()

    def on_close_connection(self):
        self._handle_disconnect()
