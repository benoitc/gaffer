# -*- coding: utf-8 -
#
# this file is part of gaffer. see the notice for more information.

import json

from tornado.web import RequestHandler, asynchronous

import pyuv

ACCESS_CONTROL_HEADERS = ['X-Requested-With',
            'X-HTTP-Method-Override', 'Content-Type', 'Accept',
            'Authorization']

CORS_HEADERS = {
    'Access-Control-Allow-Methods' : 'POST, GET, PUT, DELETE, OPTIONS',
    'Access-Control-Max-Age'       : '86400', # 24 hours
    'Access-Control-Allow-Headers' : ", ".join(ACCESS_CONTROL_HEADERS),
    'Access-Control-Allow-Credentials': 'true'
}


class CorsHandler(RequestHandler):

    @asynchronous
    def options(self, *args, **kwargs):
        self.preflight()
        self.set_status(204)
        self.finish()

    def preflight(self):
        origin = self.request.headers.get('Origin', '*')

        if origin == 'null':
            origin = '*'

        self.set_header('Access-Control-Allow-Origin', origin)
        for k, v in CORS_HEADERS.items():
            self.set_header(k, v)


class AsyncHandler(CorsHandler):

    def initialize(self, *args, **kwargs):
        self._heartbeat = None
        self._feed = None
        self._closed = False
        self._source = None
        self._pattern = None

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
            heartbeat = 60
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
            self.flush()
            self.finish()

    def handle_disconnect(self):
        self._closed = True
        self._handle_disconnect()
        if self._heartbeat is not None:
            self._heartbeat.close()

    def on_finish(self):
        self.handle_disconnect()

    def on_close_connection(self):
        self.handle_disconnect()
