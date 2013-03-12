# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

class ProcessError(Exception):
    """ exception raised on process error """

    def __init__(self, errno=400, reason="bad_request"):
        self.errno = errno
        self.reason = reason

    def __str__(self):
        return "%s: %s" % (self.errno, self.reason)

    def to_dict(self):
        return {"error": self.reason, "errno": self.errno}

    def to_json(self):
        return json.dumps(self.to_dict())

class ProcessNotFound(ProcessError):
    """ exception raised when a process or job isn't found """

    def __init__(self, reason="not_found"):
        ProcessError.__init__(self, errno=404, reason=reason)


class ProcessConflict(ProcessError):
    """ exception raised when a job already exists in the manager """

    def __init__(self, reason="process_conflict"):
        ProcessError.__init__(self, errno=409, reason=reason)

class TopicError(ProcessError):
    """ raised on topic error """


class CommandError(ProcessError):
    """ exception raised on command error """

    def __init__(self, reason="bad_command"):
        ProcessError.__init__(self, errno=400, reason=reason)

class CommandNotFound(ProcessNotFound):
    """ exception raised when a command doesn't exist """

class AlreadyRead(ProcessError):

    def __init__(self,):
        ProcessError.__init__(self, errno=403, reason="already_read")
