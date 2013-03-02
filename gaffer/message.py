# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import uuid

FRAME_ERROR_TYPE = b'error'
FRAME_RESPONSE_TYPE = b'response'
FRAME_MESSAGE_TYPE = b'message'

MAGIC_V1 = b"V1"

class MessageError(Exception):
    """ exception raised when a message doesn't validate """

class Message(object):
    """ A class to abstract our simple message format used in stream.

    a Message is constructed with a header that starts with the magic bit
    telling us the protocol version, then it add a space followed by the type
    of the message and another space followed by the message id and finally a
    null byte:

        V1 type messageid\0

    The body follow the null byte. Then a full message is:

        V1 type messageid\0body

    This simple messaging protocol allows us to pass any kind of blob as a
    body and eventually a json while still beeing able to know the type of the
    message.
    """

    def __init__(self, body=None, id=None, type=FRAME_MESSAGE_TYPE):
        self.body = body or b""
        if not isinstance(self.body, bytes):
            self.body = self.body.encode('utf-8')

        self.id = id or uuid.uuid4().hex
        if not isinstance(self.id, bytes):
            self.id = self.id.encode('utf-8')

        self.type = type

    def __str__(self):
        return "Message: %s" % self.id.decode("utf-8")

    @classmethod
    def decode_frame(cls, frame):
        if not isinstance(frame, bytes):
            frame = frame.encode('utf-8')

        try:
            # get header and body
            header, body = frame.split(b"\0")

            # parse header
            # since we have only 1 version of the protocol we can ignore for now
            # the magic bit.
            _, type, id = header.split()

            # return the message classe
            return cls(body, id=id, type=type)
        except ValueError:
            raise MessageError("invalid message %r" % frame)

    def encode(self):
        """ encode a message to bytes """
        header = b" ".join([MAGIC_V1, self.type, self.id])
        return b"".join([header, b"\0", self.body])


def decode_frame(frame):
    return Message.decode_frame(frame)

def make_response(body, id=None):
    return Message(body, id=id, type=FRAME_RESPONSE_TYPE)
