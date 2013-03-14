# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import json
import os
import time

import pyuv

from gaffer import __version__
from gaffer.gafferd.http import HttpHandler
from gaffer.httpclient import (Server, Job, Process,
        GafferNotFound, GafferConflict, WebSocket)
from gaffer.manager import Manager
from gaffer.process import ProcessConfig

from test_manager import dummy_cmd
from test_http import MockConfig

TEST_HOST = '127.0.0.1'
TEST_PORT = (os.getpid() % 31000) + 1024
TEST_URL = "ws://%s:%s/channel/websocket" % (TEST_HOST, str(TEST_PORT))


def start_manager():
    http_handler = HttpHandler(MockConfig(bind="%s:%s" % (TEST_HOST,
        TEST_PORT)))
    m = Manager(loop=pyuv.Loop.default_loop())
    m.start(apps=[http_handler])
    return m

def get_server(loop):
    return Server("http://%s:%s" % (TEST_HOST, TEST_PORT), loop=loop)

def init():
    m = start_manager()
    s = get_server(m.loop)

    # get a gaffer socket
    socket = s.socket()
    socket.start()

    return (m, s, socket)

def test_basic_socket():
    m = start_manager()
    s = get_server(m.loop)
    t = pyuv.Timer(m.loop)

    # get a gaffer socket
    socket = s.socket()
    socket.start()

    messages =[]
    def cb(event, data):
        print("got %s" % event)
        messages.append(event)

    # bind to all events
    socket.subscribe('EVENTS')
    socket['EVENTS'].bind_all(cb)

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=1)


    def stop_all(handle):
        m.stop()
        socket.close()

    def load_process(ev, msg):
        m.load(config)
        m.scale("dummy", 1)
        m.unload("dummy")
        t.start(stop_all, 0.6, 0.0)

    socket.bind("subscription_success", load_process)
    m.run()

    assert 'load' in messages
    assert 'start' in messages
    assert 'update' in messages
    assert 'stop' in messages
    assert 'unload' in messages


def test_stats():
    m = start_manager()
    s = get_server(m.loop)

    # get a gaffer socket
    socket = s.socket()
    socket.start()

    monitored = []
    def cb(event, info):
        monitored.append(info)

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("a", cmd, args=args, cwd=wdir)

    # bind to all events
    socket.subscribe("STATS:default.a")
    socket["STATS:default.a"].bind_all(cb)


    m.load(config)
    os_pid = m.running[1].os_pid


    def stop(handle):
        socket.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.4, 0.0)

    m.run()

    assert len(monitored) >= 1
    res = monitored[0]
    assert "cpu" in res
    assert res["os_pid"] == os_pid


def test_simple_job():
    m, s, socket = init()

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)

    # send a command
    cmd0 = socket.send_command("load", config.to_dict(), start=False)
    cmd1 = socket.send_command("jobs")

    results = []
    def do_events(h):
        results.append((len(m.jobs()), len(s.jobs()), s.jobs()[0]))

    def stop(h):
        h.close()
        socket.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(do_events, 0.4, 0.0)
    t1 = pyuv.Timer(m.loop)
    t1.start(stop, 0.8, 0.0)
    m.run()

    assert cmd0.error() == None
    assert cmd1.error() == None
    assert results[0] == (1, 1, "default.dummy")
    assert cmd0.result() == {"ok": True}
    assert cmd1.result()["jobs"][0] == "default.dummy"


def test_remove_job():
    m, s, socket = init()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)

    results = []
    def cb(event, cmd):
        jobs = m.jobs()
        results.append((cmd, jobs))

    socket.bind("command_success", cb)
    socket.send_command("load", config.to_dict(), start=False)
    socket.send_command("unload", "dummy")

    def stop(h):
        h.close()
        socket.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.4, 0.0)
    m.run()

    assert len(results) == 2
    cmd0, jobs0 = results[0]
    cmd1, jobs1 = results[1]

    assert cmd0.result()["ok"] == True
    assert cmd1.result()["ok"] == True
    assert len(jobs0) == 1
    assert jobs0[0] == "default.dummy"
    assert len(jobs1) == 0


def test_notfound():
    m, s, socket = init()
    cmd = socket.send_command("info", "dummy")

    def stop(h):
        h.close()
        socket.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.2, 0.0)
    m.run()

    assert cmd is not None
    assert cmd.error() is not None
    assert cmd.error()["errno"] == 404
    assert cmd.error()["reason"] == "not_found"


def test_commit():
    m, s, socket = init()

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir,
            numprocesses=0)

    # send a command
    cmd0 = socket.send_command("load", config.to_dict(), start=False)
    cmd1 = socket.send_command("commit", "dummy")

    def stop(c):
        socket.close()
        m.stop()


    cmd1.add_done_callback(stop)
    m.run()

    assert cmd0.error() == None
    assert cmd1.error() == None
    assert cmd0.result() == {"ok": True}
    assert cmd1.result()["pid"] == 1

if __name__ == "__main__":
    test_basic_socket()
