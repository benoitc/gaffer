# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import signal
import time

import pyuv
from gaffer.process import Process

from .test_manager import dummy_cmd

def test_simple():
    def exit_cb(process, return_code, term_signal):
        assert process.name == "dummy"
        assert process.active == False

    loop = pyuv.Loop.default_loop()
    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd, on_exit_cb=exit_cb)

    assert p.id == "someid"
    assert p.name == "dummy"
    assert p.cmd == cmd
    assert p.args == args
    assert cwd == cwd

    p.spawn()
    assert p.active == True

    def test_cb(handle):
        handle.stop()
        p.stop()

        time.sleep(0.2)
        assert p.active == False

    stop_later = pyuv.Timer(loop)
    stop_later.start(test_cb, 0.4, 0.4)

    loop.run()
    assert p.active == False

    with open(testfile, 'r') as f:
        res = f.read()
        assert res == 'STARTQUITSTOP'

def test_signal():

    loop = pyuv.Loop.default_loop()
    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd)

    p.spawn()

    def test_cb(handle):
        handle.stop()
        p.kill(signal.SIGHUP)
        time.sleep(0.2)
        p.stop()

        time.sleep(0.2)
        assert p.active == False

    stop_later = pyuv.Timer(loop)
    stop_later.start(test_cb, 0.4, 0.4)
    loop.run()
    with open(testfile, 'r') as f:
        res = f.read()
        assert res == 'STARTHUPQUITSTOP'

