# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from gaffer.message import (Message, decode_frame, make_response,
        FRAME_ERROR_TYPE, FRAME_RESPONSE_TYPE, FRAME_MESSAGE_TYPE, MAGIC_V1)

def test_encode():
    m = Message(b"test", id=b"someid")

    # validate info
    assert m.body == b"test"
    assert m.id == b"someid"
    assert m.type == FRAME_MESSAGE_TYPE
    assert str(m) == "Message: someid"
    assert m.encode() == b"V1 message someid\0test"

def test_decode():
    m = decode_frame(b"V1 message someid\0test")

    assert isinstance(m, Message)
    assert m.id == b"someid"
    assert m.type == FRAME_MESSAGE_TYPE
    assert m.body == b"test"

def test_response():
    m = make_response("test", id="someid")

    assert isinstance(m, Message)
    assert m.id == b"someid"
    assert m.type == FRAME_RESPONSE_TYPE
    assert m.body == b"test"
    assert m.encode() == b"V1 response someid\0test"
