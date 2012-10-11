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

    time.sleep(0.2)
    p.stop()
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
    time.sleep(0.2)
    p.kill(signal.SIGHUP)
    time.sleep(0.2)
    p.stop()
    loop.run()
    with open(testfile, 'r') as f:
        res = f.read()
        assert res == 'STARTHUPQUITSTOP'


def test_info():
    loop = pyuv.Loop.default_loop()
    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd)
    p.spawn()
    time.sleep(0.2)
    info = p.info
    pid = p.pid
    p.stop()
    loop.run()

    assert "cpu" in info
    assert info['pid'] == pid

def test_stat_events():
    loop = pyuv.Loop.default_loop()
    monitored = []
    def cb(evtype, info):
        monitored.append((evtype, info))

    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd)
    p.spawn()
    time.sleep(0.2)
    pid = p.pid
    p.monitor(cb)

    def stop(handle):
        p.unmonitor(cb)
        assert p._process_watcher.active == False
        p.stop()

    t = pyuv.Timer(loop)
    t.start(stop, 0.3, 0.0)
    loop.run()

    assert len(monitored) >= 1
    res = monitored[0]
    assert res[0] == "stat"
    assert "cpu" in res[1]
    assert res[1]["pid"] == pid


def test_stat_events_refcount():
    loop = pyuv.Loop.default_loop()
    monitored = []
    def cb(evtype, info):
        monitored.append((evtype, info))

    def cb2(evtype, info):
        monitored.append((evtype, info))

    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd)
    p.spawn()
    time.sleep(0.2)
    pid = p.pid
    p.monitor(cb)
    p.monitor(cb2)
    def stop(handle):
        p.unmonitor(cb)
        assert p._process_watcher.active == True
        assert p._process_watcher._refcount == 1
        p.unmonitor(cb2)
        assert p._process_watcher.active == False
        p.stop()

    t = pyuv.Timer(loop)
    t.start(stop, 0.3, 0.0)
    loop.run()

    assert len(monitored) >= 2
    res = monitored[0]
    assert res[0] == "stat"
    assert "cpu" in res[1]
    assert res[1]["pid"] == pid
