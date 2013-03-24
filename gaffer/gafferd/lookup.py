# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import logging
from threading import RLock
import uuid

import pyuv

from ..httpclient.websocket import WebSocket

LOGGER = logging.getLogger("gaffer")

class Message(object):

    def __init__(self, msg, callback=None):
        self.id = uuid.uuid4().hex
        self.msg = msg
        self.msg['msgid'] = self.id
        self.callback = None
        self._result = None

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self.id)

    def done(self):
        return self._result is not None

    def result(self):
        return self._result

    def reply(self, msg):
        self._result = msg
        if self.callback is not None:
            try:
                self.callback(msg)
            except Exception:
                LOGGER.exception('exception calling callback for %r', self)

    def to_json(self):
        return json.dumps(self.msg)


class LookupClient(WebSocket):

    def __init__(self, loop, url, **kwargs):
        loop = loop
        self._lock = RLock()

        # initialize the heartbeart. It will PING the lookupd server to say
        # it's alive
        try:
            self.heartbeat_timeout = kwargs.pop('heartbeat')
        except KeyError:
            self.heartbeat_timeout = 15.0
        self._heartbeat = pyuv.Timer(loop)

        # define status
        self.active = False
        self.closed = False

        # dict to maintain list of sent messages to handle replies from the
        # lookupd server
        self.messages = dict()

        super(LookupClient, self).__init__(loop, url, **kwargs)

    def start(self, on_exit_cb=None):
        # set the exit callabck
        self.exit_cb = on_exit_cb

        # already started, return
        if self.active:
            return
        super(LookupClient, self).start()
        self.active = True

    def close(self):
        self._heartbeat.stop()
        self.closed = True
        self.active = False
        super(LookupClient, self).close()

    def ping(self):
        if self.closed:
            return
        return self.write_message({"type": "PING"})

    def identify(self, name, broadcast_address, version,
            callback=None):
        return self.write_message({"type": "IDENTIFY", "name": name,
            "origin": broadcast_address, "version": version},
            callback=callback)

    def add_job(self, job_name, callback=None):
        return self.write_message({"type": "REGISTER_JOB",
            "job_name": job_name}, callback=callback)

    def remove_job(self, job_name, callback=None):
        return self.write_message({"type": "UNREGISTER_JOB",
            "job_name": job_name}, callback=callback)

    def add_process(self, job_name, pid, callback=None):
        return self.write_message({"type": "REGISTER_PROCESS",
            "job_name": job_name, "pid": pid}, callback=callback)

    def remove_process(self, job_name, pid, callback=None):
        return self.write_message({"type": "UNREGISTER_PROCESS",
            "job_name": job_name, "pid": pid}, callback=callback)

    ### websocket methods

    def on_message(self, message):
        try:
            result = json.loads(message)
        except ValueError as e:
            LOGGER.error('invalid json: %r' % str(e))
            return

        msgid = result.get('msgid')
        if not msgid:
            LOGGER.error('invalid message: %r' % str(e))
            return

        try:
            msg = self.messages.pop(msgid)
        except KeyError:
            return

        msg.reply(result)

    def on_open(self):
        # start the heartbeat
        self._heartbeat.start(self.on_heartbeat, self.heartbeat_timeout,
                self.heartbeat_timeout)
        self._heartbeat.unref()

    def on_close(self):
        self.active = False
        self.closed = True
        self._heartbeat.stop()

        # call exit the callback
        if self.exit_cb is not None:
            try:
                self.exit_cb(self)
            except Exception:
                LOGGER.exception('exception calling exit callback for %r',
                        self)

    def on_heartbeat(self, h):
        # on heartbeat send a `PING` message to the channel
        # it will maintain the connection open
        self.ping()

    def write_message(self, message, callback=None):
        if isinstance(message, bytes):
            super(LookupClient, self).write_message(message)
            return

        msg = Message(message, callback=callback)

        # store the message to handle the reply
        with self._lock:
            self.messages[msg.id] = msg

        super(LookupClient, self).write_message(msg.to_json())
        return msg
