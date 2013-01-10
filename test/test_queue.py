# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import pyuv

from gaffer.queue import AsyncQueue

class DummyError(Exception):
    pass

def test_basic():
    loop = pyuv.Loop.default_loop()
    ret = []

    # define callbacks
    def cb(msg, err):
        ret.append(msg)

    # initialize the queue
    q = AsyncQueue(loop, cb)

    def heartbeat(handle):
        if len(ret) == 3:
            q.close()
            handle.close()

    for i in range(3):
        q.send("msg%s" % i)

    t = pyuv.Timer(loop)
    t.start(heartbeat, 0.1, 0.1)

    loop.run()

    assert len(ret) == 3
    assert ret == ["msg0", "msg1", "msg2"]


def test_error():
    loop = pyuv.Loop.default_loop()
    ret = []
    errors = []

    # define callback for the queue
    def cb(msg, err):
        if err is None:
            ret.append(msg)
            if len(ret) == 1:
                raise DummyError()
        else:
            t, e, tb = err
            errors.append((msg, isinstance(e, DummyError)))

    # initialize the queue
    q = AsyncQueue(loop, cb)

    def heartbeat(handle):
        if len(ret) == 3 and errors:
            q.close()
            handle.close()


    for i in range(3):
        q.send("msg%s" % i)

    t = pyuv.Timer(loop)
    t.start(heartbeat, 0.1, 0.1)

    loop.run()

    assert len(ret) == 3
    assert len(errors) == 1
    assert ret == ["msg0", "msg1", "msg2"]
    assert errors == [("msg0", True)]

if __name__ == "__main__":
    test_error()
