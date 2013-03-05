# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import json

from tornado import websocket

from ..error import ProcessError
from .registry import (NoIdent, JobNotFound, AlreadyIdentified, IdentExists,
        AlreadyRegistered)

class MessageError(ProcessError):

    def __init__(self, reason="invalid_message", msgid=None):
        ProcessError.__init__(self, errno=400, reason=reason)
        self.msgid = msgid


class LookupMessage(object):

    def __init__(self, raw):
        self.raw = raw
        self.type = None
        self.id = None
        self.args = ()

        self.parse(raw)

    def parse(self, raw):
        # message should at least have the msgid and type properties
        try:
            self.id = raw['msgid']
            self.type = raw['type']
        except KeyError:
            raise MessageError(msgid=self.id)

        # validate the message type
        if self.type not in ("REGISTER_JOB", "UNREGISTER_JOB",
                "REGISTER_PROCESS", "UNREGISTER_PROCESS", "PING", "IDENTIFY"):
            raise MessageError("invalid_message_type")

        # validate message arguments
        try:
            if self.type == "IDENTIFY":
                self.args = (raw['name'], raw['origin'], raw['version'],)
            if self.type in ("REGISTER_JOB", "UNREGISTER_JOB"):
                self.args  = (raw['job_name'],)
            elif self.type in ("REGISTER_PROCESS", "UNREGISTER_PROCESS"):
                self.args  = (raw['job_name'], raw['pid'],)
        except KeyError:
            raise MessageError(msgid=self.id)

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self.id)


class LookupWebSocket(websocket.WebSocketHandler):

    def open(self):
        db = self.settings.get('registration_db')
        db.add_node(self)
        self.active = True

    def on_close(self):
        db = self.settings.get('registration_db')
        db.remove_node(self)
        self.active = False

    def on_message(self, message):
        db = self.settings.get('registration_db')
        try:
            msg_raw = json.loads(message)
        except ValueError as e:
            self.write_error(400, "invalid_json")

        try:
            msg = LookupMessage(msg_raw)
        except MessageError as e:
            return self.write_error(e.errno, e.reason, e.msgid)

        try:
            if msg.type == "PING":
                db.update(self)
            elif msg.type == "IDENTIFY":
                db.identify(self, *msg.args)
            elif msg.type == "REGISTER_JOB":
                db.add_job(self, *msg.args)
            elif msg.type == "UNREGISTER_JOB":
                db.remove_job(self, *msg.args)
            elif msg.type == "REGISTER_PROCESS":
                db.add_process(self, *msg.args)
            elif msg.type == "UNREGISTER_PROCESS":
                db.remove_process(self, *msg.args)
        except JobNotFound as e:
            return self.write_error(404, str(e), msg.id)
        except AlreadyRegistered as e:
            return self.write_error(409, str(e), msg.id)
        except NoIdent as e:
            return self.write_error(404, str(e), msg.id)
        except AlreadyIdentified as e:
            return self.write_error(409, str(e), msg.id)
        except IdentExists as e:
            return self.write_error(409, str(e), msg.id)

        self.write_message({"ok": True, "msgid": msg.id})

    def write_error(self, errno, reason, msgid=None):
        msg = {"errno": errno, "reason": reason, "msgid": msgid}
        self.write_message(msg)

    def write_message(self, msg):
        if isinstance(msg, dict):
            msg = json.dumps(msg)

        super(LookupWebSocket, self).write_message(msg)
