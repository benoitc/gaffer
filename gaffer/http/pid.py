# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import signal

import six
from tornado import escape

from .util import CorsHandler
from ..error import ProcessError


class AllProcessIdsHandler(CorsHandler):

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        self.write({"pids": list(m.running)})

class ProcessIdHandler(CorsHandler):

    def head(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        try:
            m.get_process(pid)
        except ProcessError:
            self.set_status(404)
            return

        self.set_status(200)

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        try:
            p = m.get_process(pid)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write(p.info)

    def delete(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        try:
            m.stop_process(pid)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        # return the response, we set the status to accepted since the result
        # is async.
        self.set_status(202)
        self.write({"ok": True})


class ProcessIdSignalHandler(CorsHandler):

    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        # get pidnum
        try:
            p = m.get_process(pid)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        # decode object
        obj = escape.json_decode(self.request.body)
        try:
            p.kill(obj.get('signal'))
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_signal"})


        self.set_status(202)
        self.write({"ok": True})

class ProcessIdStatsHandler(CorsHandler):

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        # get pidnum
        try:
            p = m.get_process(pid)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.set_status(200)
        self.write({"stats": p.stats})
