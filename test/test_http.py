# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import time

import pytest
import pyuv

from gaffer import __version__
from gaffer.manager import Manager
from gaffer.http_handler import HttpEndpoint, HttpHandler
from gaffer.httpclient import (Server, Template, Process,
        GafferNotFound, GafferConflict)

from test_manager import dummy_cmd

TEST_HOST = '127.0.0.1'
TEST_PORT = (os.getpid() % 31000) + 1024

TEST_PORT2 = (os.getpid() % 31000) + 1023


def start_manager():
    http_endpoint = HttpEndpoint(uri="%s:%s" % (TEST_HOST, TEST_PORT))
    http_handler = HttpHandler(endpoints=[http_endpoint])
    m = Manager()
    m.start(apps=[http_handler])
    time.sleep(0.2)
    return m

def get_server(loop):
    return Server("http://%s:%s" % (TEST_HOST, TEST_PORT), loop=loop)

def init():
    m = start_manager()
    s = get_server(m.loop)
    return (m, s)

def test_basic():
    m = start_manager()
    s = get_server(m.loop)
    assert s.version == __version__

    m.stop()
    m.run()

def test_multiple_handers():
    http_endpoint = HttpEndpoint(uri="%s:%s" % (TEST_HOST, TEST_PORT))
    http_endpoint2 = HttpEndpoint(uri="%s:%s" % (TEST_HOST, TEST_PORT2))
    http_handler = HttpHandler(endpoints=[http_endpoint, http_endpoint2])
    m = Manager()
    m.start(apps=[http_handler])
    time.sleep(0.2)

    s = Server("http://%s:%s" % (TEST_HOST, TEST_PORT), loop=m.loop)
    s2 = Server("http://%s:%s" % (TEST_HOST, TEST_PORT2), loop=m.loop)
    assert TEST_PORT != TEST_PORT2
    assert s.version == __version__
    assert s2.version == __version__

    m.stop()
    m.run()

def test_template():
    m, s = init()

    assert s.get_templates() == []

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir, start=False)
    time.sleep(0.2)
    assert len(m.get_templates()) == 1
    assert len(s.get_templates()) == 1
    assert s.get_templates()[0] == "dummy"

    m.stop()
    m.run()

def test_template_create():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    s.add_template("dummy", cmd, args=args, cwd=wdir, start=False)
    time.sleep(0.2)
    assert len(m.get_templates()) == 1
    assert len(s.get_templates()) == 1
    assert s.get_templates()[0] == "dummy"
    assert "dummy" in m.get_templates()
    assert len(m.running) == 0

    with pytest.raises(GafferConflict):
        s.add_template("dummy", cmd, args=args, cwd=wdir, start=False)

    p = s.get_template("dummy")
    assert isinstance(p, Template)

    m.stop()

    m.run()

def test_template():
    m, s = init()
    testfile, cmd, args, wdir = dummy_cmd()
    s.add_template("dummy", cmd, args=args, cwd=wdir, start=False)
    assert s.get_templates()[0] == "dummy"
    s.remove_template("dummy")
    assert len(s.get_templates()) == 0
    assert len(m.get_templates()) == 0
    m.stop()
    m.run()

def test_notfound():
    m, s = init()

    with pytest.raises(GafferNotFound):
        s.get_template("dummy")

    m.stop()
    m.run()

def test_process_start_stop():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    p = s.add_template("dummy", cmd, args=args, cwd=wdir, start=False)
    assert isinstance(p, Template)

    p.start()
    time.sleep(0.2)

    assert len(m.running) == 1
    info = p.info()
    assert info['running'] == 1
    assert info['active'] == True
    assert info['max_processes'] == 1

    p.stop()
    time.sleep(0.2)
    assert len(m.running) == 0
    assert p.active == False

    s.remove_template("dummy")
    assert len(s.get_templates()) == 0

    p = s.add_template("dummy", cmd, args=args, cwd=wdir, start=True)
    time.sleep(0.2)
    assert len(m.running) == 1
    assert p.active == True

    p.restart()
    time.sleep(0.4)
    assert len(m.running) == 1
    assert p.active == True

    m.stop()
    m.run()

def test_template_scale():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    p = s.add_template("dummy", cmd, args=args, cwd=wdir)
    time.sleep(0.2)
    assert isinstance(p, Template)
    assert p.active == True
    assert p.numprocesses == 1


    p.scale(3)
    time.sleep(0.2)
    assert p.numprocesses == 4
    assert p.running == 4

    p.scale(-3)
    time.sleep(0.2)
    assert p.numprocesses == 1
    assert p.running == 1

    m.stop()
    m.run()

def test_running():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    s.add_template("dummy", cmd, args=args, cwd=wdir)
    time.sleep(0.2)

    assert len(m.running) == 1
    assert len(s.running()) == 1

    assert 1 in m.running
    assert s.running()[0] == 1

    m.stop()
    m.run()


def test_pids():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    p = s.add_template("dummy", cmd, args=args, cwd=wdir)
    time.sleep(0.2)

    p = s.get_template("dummy")
    assert isinstance(p, Template) == True

    pid = s.get_process(1)
    assert isinstance(pid, Process) == True
    assert pid.pid == 1
    assert pid.info.get('name') == "dummy"
    assert pid.name == "dummy"
    assert pid.os_pid == pid.info.get('os_pid')
    assert p.pids == [1]

    pid.stop()
    assert 1 not in m.running

    time.sleep(0.2)
    assert p.pids == [2]
    m.stop()
    m.run()


def test_stats():
    m, s = init()
    testfile, cmd, args, wdir = dummy_cmd()
    p = s.add_template("dummy", cmd, args=args, cwd=wdir)
    time.sleep(0.2)

    pid = s.get_process(1)
    assert isinstance(pid, Process) == True
    assert pid.pid == 1

    stats = pid.stats
    assert isinstance(stats, dict) == True
    assert "cpu" in stats
    assert "mem_info1" in stats

    pid.stop()
    m.stop()
    m.run()

def test_applications():
    m, s = init()
    started = []
    stopped = []
    def cb(evtype, info):
        if evtype == "start":
            started.append((info['appname'], info['name']))
        elif evtype == "stop":
            stopped.append((info['appname'], info['name']))

    m.events.subscribe('start', cb)
    m.events.subscribe('stop', cb)
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("a", cmd, appname="ga", args=args, cwd=wdir, start=False)
    m.add_template("b", cmd, appname="ga", args=args, cwd=wdir, start=False)
    m.add_template("a", cmd, appname="gb", args=args, cwd=wdir, start=False)

    apps = s.all_apps()

    ga1 = s.get_templates('ga')
    gb1 = s.get_templates('gb')

    start_app = lambda m, t: t.start()
    stop_app = lambda m, t: t.stop()

    s.walk_templates(start_app, "ga")
    s.walk_templates(start_app, "gb")

    ga2 = []
    def rem_cb(h):
        s.remove_template("a", "ga")
        [ga2.append(name) for name in s.get_templates('ga')]

    t0 = pyuv.Timer(m.loop)
    t0.start(rem_cb, 0.2, 0.0)
    s.walk_templates(stop_app, "gb")

    def stop(handle):
        m.events.unsubscribe("start", cb)
        m.events.unsubscribe("stop", cb)
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.6, 0.0)
    m.run()

    assert apps == ['ga', 'gb']
    assert ga1 == ['a', 'b']
    assert gb1 == ['a']
    assert started == [('ga', 'a'), ('ga', 'b'), ('gb', 'a')]
    assert stopped == [('gb', 'a'), ('ga', 'a')]
    assert ga2 == ['b']

if __name__ == "__main__":
    test_template()
