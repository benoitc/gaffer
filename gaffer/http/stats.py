# -*- coding: utf-8 -
#
# this file is part of gaffer. see the notice for more information.

import json

from tornado.web import asynchronous

from .util import AsyncHandler

class StatsHandler(AsyncHandler):
    """ watcher handler used to watch processes stats in quasi rt """

    @asynchronous
    def get(self, *args):
        self.preflight()
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


    def _handle_disconnect(self):
        if not self._source:
            return
        self._source.unmonitor(self._on_event)
