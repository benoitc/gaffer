# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from tornado.web import asynchronous
from tornado import websocket

from .util import AsyncHandler

class StreamHandler(AsyncHandler):
    """ stream handler to stream stout & stderr """

    def post(self, *args):
        self.preflight()
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            self.finish()
            return

        if not pid in m.running or args[1] != "stdin":
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        p = m.running[pid]

        try:
            p.write(self.request.body)
        except IOError:
            self.set_status(403)
            self.write({"error": "forbidden_write"})
            return

        self.set_status(200)
        self.write({"ok": True})

    @asynchronous
    def get(self, *args):
        self.preflight()
        self._feed = feed = self.get_argument('feed', default="longpoll")
        heartbeat = self.get_argument('heartbeat', default="true")
        m = self.settings.get('manager')
        self._pattern = None

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            self.finish()
            return

        if not pid in m.running:
            return self.send_not_found()

        self._source = p = m.running[pid]

        if not p.redirect_output:
            self.set_status(400)
            self.write({"error": "io_not_redirected"})
            return self.finish()

        io = args[1]
        if io not in p.redirect_output:
            self.set_status(404)
            self.write({"error": "io_not_found"})
            return self.finish()

        self._pattern = io
        if feed == "continuous":
            self.setup_continous(feed, m, heartbeat)
            p.monitor_io(io, self._on_continuous)
        else:
            self.setup_stream(feed, m, heartbeat)
            p.monitor_io(io, self._on_event)


    def _handle_disconnect(self):
        if not self._source and not self._pattern:
            return
        if self._feed == "continuous":
            cb = self._on_continuous
        else:
            cb = self._on_event

        self._source.unmonitor_io(self._pattern, cb)

    def setup_stream(self, feed, m, heartbeat):
        self._feed = feed

        self.setup_heartbeat(heartbeat, m)
        if feed == "eventsource":
            self.set_header("Content-Type", "text/event-stream")
        else:
            self.set_header("Content-Type", "application/octet-stream")
        self.set_header("Cache-Control", "no-cache")

    def setup_continous(self, feed, m, heartbeat):
        self._feed = feed
        self.setup_heartbeat(heartbeat, m)
        self.set_header("Transfer-Encoding", "chunked")
        self.set_header("Content-Type", "application/octet-stream")
        self.set_header("Cache-Control", "no-cache")

    def write_chunk(self, data):
        chunk_size = "%X\r\n" % len(data)
        chunk = b"".join([chunk_size.encode('latin1'), data, b"\r\n"])
        self.write(chunk)

    def _on_heartbeat(self, handle):
        if self._feed == "continuous":
            self.write_chunk("\n")
        else:
            self.write("\n")

    def _on_continuous(self, evtype, msg):
        self.write_chunk(msg['data'])
        self.flush()

    def _on_event(self, evtype, msg):
        if self._feed == "eventsource":
            event = b"".join([b"event: ", evtype.encode('latin1')])
            data = b"".join([b"data: ", msg['data']])

            event = [event, data ,b""]
            self.write(b"\r\n".join(event))
            self.flush()
        else:
            self.write(msg['data'])
            self.flush()
            self.finish()


class WStreamHandler(websocket.WebSocketHandler):

    def open(self, *args):
        self._source = None
        m = self.settings.get('manager')
        try:
            pid = int(args[0])
        except ValueError:
            self.write_message({"error": "bad_value"})
            self.close()

        if not pid in m.running:
            self.write_message({"error": "not_found"})
            self.close()

        self._source = p = m.running[pid]

        if p.redirect_output:
            p.monitor_io(p.redirect_output[0], self._on_event)

        if not p.redirect_input:
            self.write_message({"error": "forbidden_write"})
            self.close()

        if p.redirect_output:
            p.monitor_io(p.redirect_output[0], self._on_event)


    def on_message(self, message):
        self._source.write(message)

    def on_close(self):
        if not hasattr(self, '_source') or not self._source:
            return
        self._source.unmonitor_io("stdout", self._on_event)

    def _on_event(self, evtype, msg):
        self.write_message(msg['data'])
        self.flush()
