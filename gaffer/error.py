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
        return json.dumps(self.to_dict)

class TopicError(ProcessError):
    """ raised on topic error """
