# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import pyuv
from tornado import escape, websocket
from tornado.web import HTTPError

from ...message import Message, decode_frame, make_response
from ...error import ProcessError
from ..keys import Key, DummyKey, KeyNotFound
from .util import CorsHandler, CorsHandlerWithAuth

class AllProcessIdsHandler(CorsHandlerWithAuth):

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        if (not self.api_key.is_admin() and
                not self.api_key.can_manage_all()):
            raise HTTPError(403)

        self.write({"pids": list(m.running)})

class ProcessIdHandler(CorsHandlerWithAuth):

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
           p = m.get_process(pid)
        except ProcessError:
            self.set_status(404)
            return

        if not self.api_key.can_read(p.name):
            raise HTTPError(403)

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

        if not self.api_key.can_read(p.name):
            raise HTTPError(403)

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
            p = m.get_process(pid)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        if not self.api_key.can_manage(p.name):
            raise HTTPError(403)

        try:
            m.stop_process(pid)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        # return the response, we set the status to accepted since the result
        # is async.
        self.set_status(202)
        self.write({"ok": True})


class ProcessIdSignalHandler(CorsHandlerWithAuth):

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

        if not self.api_key.can_manage(p.name):
            raise HTTPError(403)


        # decode object
        obj = escape.json_decode(self.request.body)
        try:
            p.kill(obj.get('signal'))
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_signal"})


        self.set_status(202)
        self.write({"ok": True})

class ProcessIdStatsHandler(CorsHandlerWithAuth):

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

        if not self.api_key.can_read(p.name):
            raise HTTPError(403)


        self.set_status(200)
        self.write({"stats": p.stats})


class PidChannel(websocket.WebSocketHandler):
    """ bi-directionnal stream handler using a wensocket,
    this handler allows you to read and write to a stream if the operation is
    available """

    def open(self, *args):
        self.manager = self.settings.get('manager')
        self.args = args

        # initialize key handling
        self.require_key = self.settings.get('require_key', False)
        self.key_mgr = self.settings.get('key_mgr')
        self.api_key = None

        try:
            process = self.process = self.manager.get_process(int(args[0]))
        except ProcessError as e:
            self.write_error(e.to_json())
            return self.close()

        # subscribe to exit event so we make sure to close the connection when
        # the process exit.
        self.manager.events.subscribe("proc.%s.exit" % process.pid,
                self.on_exit)

        if not self.require_key:
            self.api_key = DummyKey()
            try:
                self.open_stream(self.process, self.args)
            except ProcessError as e:
                self.write_error(e.to_json())
                self.close()
        else:
            self.opened = False


    def open_stream(self, process, args):
        self._write = None
        self._stream = None
        self._io = None

        # mode is the maskk used to handle this stream. It can be
        # pyuv.UV_READABLE or pyuv.UV_WRITABLE.
        mode = self.mode = int(self.get_argument("mode", 3))
        if len(args) == 1:
            # we try to read from stdout and write to stdin

            # test if we need to read
            if mode & pyuv.UV_READABLE:
                if not self.api_key.can_read(self.process.name):
                    raise ProcessError(403, "FORBIDDEN")

                if not process.redirect_output:
                    raise ProcessError(403, "EPERM")

                self.process.monitor_io(process.redirect_output[0],
                    self.on_output)
                self._stream = process.redirect_output[0]

            # test if we need to write
            if mode & pyuv.UV_WRITABLE:
                if not self.api_key.can_write(self.process.name):
                    raise ProcessError(403, "FORBIDDEN")

                if not process.redirect_input:
                    raise ProcessError(403, "EPERM")
                self._write = process.write

        elif len(args) == 2:
            # a stream name is used
            stream = escape.native_str(args[1])

            if stream in process.redirect_output:
                if mode & pyuv.UV_READABLE:
                    self.process.monitor_io(stream, self.on_output)
                if mode & pyuv.UV_WRITABLE:
                    if not process.redirect_input:
                        raise ProcessError(403, "EPERM")
                    self._write = process.write

            elif stream in process.custom_streams:
                self._io = process.streams[stream]
                self._io.subscribe(self.on_output)
                if mode & pyuv.UV_WRITABLE:
                    self._write = self._io.write
            else:
                raise ProcessError(404, "ENOENT")

            self._stream = stream

        self.opened = True

    def authenticate(self, body):
        if body.startswith(b"AUTH:"):
            key = body.split(b"AUTH:")[1].decode('utf-8')
            try:
                self.api_key = Key.load(self.key_mgr.get_key(key))
            except KeyNotFound:
                raise ProcessError(403, "AUTH_REQUIRED")
        else:
            raise ProcessError(403, "AUTH_REQUIRED")

    def close(self):
        self._close_subscriptions()
        super(PidChannel, self).close()

    def on_message(self, frame):
        # decode the coming msg frame
        msg = decode_frame(frame)

        is_auth = msg.body.startswith(b"AUTH:") == True
        if not self.api_key and self.require_key:
            try:
                self.authenticate(msg.body)
            except ProcessError as e:
                self.write_error(e.to_json())
                self.close()

        if not self.opened:
            try:
                self.open_stream(self.process, self.args)
            except ProcessError as e:
                self.write_error(e.to_json())
                self.close()


        if not is_auth:
            # we can write on this stream, return an error
            if not self._write:
                error = ProcessError(403, "EPERM")
                return self.write_error(error.to_json(), msg.id)

            # send the message
            try:
                self._write(msg.body)
            except Exception:
                error = ProcessError(500, "EIO")
                return self.write_error(error.to_json(), msg.id)


        # send OK response
        resp = make_response("OK", id=msg.id)
        self.write_message(resp.encode())

    def on_output(self, evtype, message):
        msg = Message(message['data'])
        self.write_message(msg.encode())

    def on_close(self):
        self.manager.events.unsubscribe("proc.%s.exit" % self.process.pid,
                self.on_exit)

        # close the subscriptions
        self._close_subscriptions()

    def on_exit(self):
        self.close()

    def write_error(self, error_msg, msgid=None):
        msgid = msgid or b"gaffer_error"

        msg = Message(error_msg, id=msgid, type=b'error')
        self.write_message(msg.encode())

    def _close_subscriptions(self):
        self.manager.events.unsubscribe("proc.%s.exit" % self.process.pid,
                self.on_exit)

        # unsubscribe reads
        if self._stream is not None:
            if self._stream in self.process.redirect_output:
                self.process.unmonitor_io(self._stream, self.on_output)
            else:
                self._io.unsubscribe(self.on_output)
