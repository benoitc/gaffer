# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import time

from gaffer.manager import Manager
from test_manager import dummy_cmd

import pyuv

def test_basic():
    emitted = []
    m = Manager()
    m.start()

    def cb(ev, msg):
        emitted.append((ev, msg['name']))

    # subscribe to all events
    chan = m.subscribe("EVENTS")
    chan.bind('.', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    m.scale("dummy", 1)
    m.remove_template("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()

    assert ('create', 'dummy') in emitted
    assert ('start', 'dummy') in emitted
    assert ('update', 'dummy') in emitted
    assert ('stop', 'dummy') in emitted
    assert ('delete', 'dummy') in emitted

def test_process_events():
    emitted = []
    m = Manager()
    m.start()

    def cb(ev, *args):
        emitted.append(ev)

    # subscribe to all events
    chan = m.subscribe("PROCESS:system.dummy")
    chan.bind_all(cb)

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir)
    m.stop_template("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()

    assert 'start' in emitted
    assert 'spawn' in emitted
    assert 'stop' in emitted
    assert 'exit' in emitted

def test_stats():
    m = Manager()
    monitored = []
    def cb(info):
        monitored.append(info)

    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("a", cmd, args=args, cwd=wdir)
    os_pid = m.running[1].os_pid

    chan = m.subscribe("STATS:system.a")
    chan.bind(cb)

    def stop(handle):
        chan.unbind(cb)
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.3, 0.0)

    m.run()
    assert len(monitored) >= 1
    res = monitored[0]
    assert "cpu" in res
    assert res["os_pid"] == os_pid
