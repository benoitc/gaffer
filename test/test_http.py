# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import time

import pytest

from gaffer import __version__
from gaffer.manager import Manager
from gaffer.http_handler import HttpEndpoint, HttpHandler
from gaffer.httpclient import (Server, Process, ProcessId,
        GafferNotFound, GafferConflict)

from test_manager import dummy_cmd

TEST_HOST = '127.0.0.1'
TEST_PORT = (os.getpid() % 31000) + 1024

TEST_PORT2 = (os.getpid() % 31000) + 1023


def start_manager():
    http_endpoint = HttpEndpoint(uri="%s:%s" % (TEST_HOST, TEST_PORT))
    http_handler = HttpHandler(endpoints=[http_endpoint])
    m = Manager()
    m.start(controllers=[http_handler])
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
    m.start(controllers=[http_handler])
    time.sleep(0.2)

    s = Server("http://%s:%s" % (TEST_HOST, TEST_PORT), loop=m.loop)
    s2 = Server("http://%s:%s" % (TEST_HOST, TEST_PORT2), loop=m.loop)
    assert TEST_PORT != TEST_PORT2
    assert s.version == __version__
    assert s2.version == __version__

    m.stop()
    m.run()

def test_processes():
    m, s = init()

    assert s.processes() == []

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, start=False)
    time.sleep(0.2)
    assert len(m.processes) == 1
    assert len(s.processes()) == 1
    assert s.processes()[0] == "dummy"

    m.stop()
    m.run()

def test_process_create():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    s.add_process("dummy", cmd, args=args, cwd=wdir, start=False)
    time.sleep(0.2)
    assert len(m.processes) == 1
    assert len(s.processes()) == 1
    assert s.processes()[0] == "dummy"
    assert "dummy" in m.processes
    assert len(m.running) == 0

    with pytest.raises(GafferConflict):
        s.add_process("dummy", cmd, args=args, cwd=wdir, start=False)

    p = s.get_process("dummy")
    assert isinstance(p, Process)

    m.stop()

    m.run()

def test_process_remove():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    s.add_process("dummy", cmd, args=args, cwd=wdir, start=False)

    assert s.processes()[0] == "dummy"

    s.remove_process("dummy")
    assert len(s.processes()) == 0
    assert len(m.processes) == 0

    m.stop()

    m.run()

def test_notfound():
    m, s = init()

    with pytest.raises(GafferNotFound):
        s.get_process("dummy")

    m.stop()
    m.run()

def test_process_start_stop():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    p = s.add_process("dummy", cmd, args=args, cwd=wdir, start=False)
    assert isinstance(p, Process)

    p.start()
    time.sleep(0.2)
    assert len(m.running) == 1
    status = p.status()
    assert status['running'] == 1
    assert status['active'] == True
    assert status['max_processes'] == 1

    p.stop()
    time.sleep(0.2)
    assert len(m.running) == 0
    assert p.active == False

    s.remove_process("dummy")
    assert len(s.processes()) == 0

    p = s.add_process("dummy", cmd, args=args, cwd=wdir, start=True)
    time.sleep(0.2)
    assert len(m.running) == 1
    assert p.active == True

    p.restart()
    assert len(m.running) == 1
    assert p.active == True

    m.stop()
    m.run()

def test_process_add_sub():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    p = s.add_process("dummy", cmd, args=args, cwd=wdir)
    time.sleep(0.2)
    assert isinstance(p, Process)
    assert p.active == True
    assert p.numprocesses == 1


    p.add(3)
    time.sleep(0.2)
    assert p.numprocesses == 4
    assert p.running == 4

    p.sub(3)
    time.sleep(0.2)
    assert p.numprocesses == 1
    assert p.running == 1

    m.stop()
    m.run()

def test_running():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    p = s.add_process("dummy", cmd, args=args, cwd=wdir)
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
    p = s.add_process("dummy", cmd, args=args, cwd=wdir)
    time.sleep(0.2)

    p = s.get_process("dummy")
    assert isinstance(p, Process) == True

    pid = s.get_process(1)
    assert isinstance(pid, ProcessId) == True
    assert pid.pid == 1
    assert pid.process.get('name') == "dummy"

    assert p.pids == [1]

    pid.stop()
    assert 1 not in m.running

    time.sleep(0.2)
    assert p.pids == [2]


    m.stop()
    m.run()
