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
from gaffer.httpclient import (Server, Job, Process,
        GafferNotFound, GafferConflict)
from gaffer.process import ProcessConfig

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

def test_simple_job():
    m, s = init()

    assert s.jobs() == []

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    m.load(config, start=False)
    time.sleep(0.2)
    assert len(m.jobs()) == 1
    assert len(s.jobs()) == 1
    assert s.jobs()[0] == "default.dummy"

    m.stop()
    m.run()

def test_job_create():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)

    s.load(config, start=False)
    time.sleep(0.2)
    assert len(m.jobs()) == 1
    assert len(s.jobs()) == 1
    assert s.jobs()[0] == "default.dummy"
    assert "default.dummy" in m.jobs()
    assert len(m.running) == 0

    with pytest.raises(GafferConflict):
        s.load(config, start=False)

    job = s.get_job("dummy")
    assert isinstance(job, Job)

    m.stop()
    m.run()

def test_remove_job():
    m, s = init()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    s.load(config, start=False)
    assert s.jobs()[0] == "default.dummy"
    s.unload("dummy")
    assert len(s.jobs()) == 0
    assert len(m.jobs()) == 0
    m.stop()
    m.run()

def test_notfound():
    m, s = init()

    with pytest.raises(GafferNotFound):
        s.get_job("dummy")

    m.stop()
    m.run()

def test_process_start_stop():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    job = s.load(config, start=False)
    assert isinstance(job, Job)

    job.start()
    time.sleep(0.2)

    assert len(m.running) == 1
    info = job.info()
    assert info['running'] == 1
    assert info['active'] == True
    assert info['max_processes'] == 1

    job.stop()
    time.sleep(0.2)
    assert len(m.running) == 0
    assert job.active == False

    s.unload("dummy")
    assert len(s.jobs()) == 0

    job = s.load(config, start=True)
    time.sleep(0.2)
    assert len(m.running) == 1
    assert job.active == True

    job.restart()
    time.sleep(0.4)
    assert len(m.running) == 1
    assert job.active == True

    m.stop()
    m.run()

def test_job_scale():
    m, s = init()

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    job = s.load(config)
    time.sleep(0.2)
    assert isinstance(job, Job)
    assert job.active == True
    assert job.numprocesses == 1


    job.scale(3)
    time.sleep(0.2)
    assert job.numprocesses == 4
    assert job.running == 4

    job.scale(-3)
    time.sleep(0.2)
    assert job.numprocesses == 1
    assert job.running == 1

    m.stop()
    m.run()

def test_running():
    m, s = init()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    job = s.load(config)
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
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    s.load(config)
    time.sleep(0.2)

    job = s.get_job("dummy")
    assert isinstance(job, Job) == True

    pid = s.get_process(1)
    assert isinstance(pid, Process) == True
    assert pid.pid == 1
    assert pid.info.get('name') == "default.dummy"
    assert pid.name == "default.dummy"
    assert pid.os_pid == pid.info.get('os_pid')
    assert job.pids == [1]

    pid.stop()
    assert 1 not in m.running

    time.sleep(0.2)
    assert job.pids == [2]
    m.stop()
    m.run()


def test_stats():
    m, s = init()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    s.load(config)
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

def test_sessions():
    m, s = init()
    started = []
    stopped = []
    def cb(evtype, info):
        if evtype == "start":
            started.append(info['name'])
        elif evtype == "stop":
            stopped.append(info['name'])

    m.events.subscribe('start', cb)
    m.events.subscribe('stop', cb)
    testfile, cmd, args, wdir = dummy_cmd()
    a = ProcessConfig("a", cmd, args=args, cwd=wdir)
    b = ProcessConfig("b", cmd, args=args, cwd=wdir)


    # load process config in different sessions
    m.load(a, sessionid="ga", start=False)
    m.load(b, sessionid="ga", start=False)
    m.load(a, sessionid="gb", start=False)

    sessions = s.sessions()

    ga1 = s.jobs('ga')
    gb1 = s.jobs('gb')

    start_app = lambda mgr, job: job.start()
    stop_app = lambda mgr, job: job.stop()

    s.jobs_walk(start_app, "ga")
    s.jobs_walk(start_app, "gb")

    ga2 = []
    def rem_cb(h):
        s.unload("a", sessionid="ga")
        [ga2.append(name) for name in s.jobs('ga')]

    t0 = pyuv.Timer(m.loop)
    t0.start(rem_cb, 0.2, 0.0)
    s.jobs_walk(stop_app, "gb")

    def stop(handle):
        m.events.unsubscribe("start", cb)
        m.events.unsubscribe("stop", cb)
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.6, 0.0)
    m.run()

    assert len(sessions) == 2
    assert sessions == ['ga', 'gb']
    assert ga1 == ['ga.a', 'ga.b']
    assert gb1 == ['gb.a']
    assert started == ['ga.a', 'ga.b', 'gb.a']
    assert stopped == ['gb.a', 'ga.a']
    assert ga2 == ['ga.b']

if __name__ == "__main__":
    test_template()
