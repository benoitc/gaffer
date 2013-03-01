# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import deque
from functools import partial
import os
import signal
import sys
import time
from tempfile import mkstemp

import pyuv
import pytest

from gaffer.error import ProcessError, ProcessNotFound
from gaffer.manager import Manager
from gaffer.process import ProcessConfig, Process
from gaffer.state import FlappingInfo

def tmpfile():
     fd, testfile = mkstemp()
     os.close(fd)
     return testfile

def dummy_cmd():
    fd, testfile = mkstemp()
    os.close(fd)
    if sys.platform == 'win32':
        cmd = "cmd.exe"
        args = args=["/c", "proc_dummy.py", testfile],
    else:
        cmd = sys.executable
        args = ["-u", "./proc_dummy.py", testfile]
    wdir = os.path.dirname(__file__)
    return (testfile, cmd, args, wdir)


def crash_cmd():
    fd, testfile = mkstemp()
    os.close(fd)
    if sys.platform == 'win32':
        cmd = "cmd.exe"
        args = args=["/c", "proc_crash.py"],
    else:
        cmd = sys.executable
        args = ["-u", "./proc_crash.py"]
    wdir = os.path.dirname(__file__)
    return (cmd, args, wdir)

def test_simple():
    m = Manager()
    m.start()
    assert m.started == True

    def on_stop(manager):
        assert manager.started == False

    m.stop(on_stop)
    m.run()

def test_simple_job():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()

    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)

    m.load(config, start=False)
    state = m._get_locked_state("dummy")

    assert state.numprocesses == 1
    assert state.name == "default.dummy"
    assert state.cmd == cmd
    assert state.config['args'] == args
    assert state.config['cwd'] == wdir

    m.unload("dummy")

    with pytest.raises(ProcessError):
        m._get_locked_state("dummy")

    m.stop()
    m.run()

def test_start_stop_job():
    res = []
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    m.load(config)
    state = m._get_locked_state("dummy")
    res.append(len(state.running))
    m.stop_job("dummy")
    res.append(len(state.running))
    m.stop()
    m.run()

    assert res == [1, 0]


def test_start_multiple():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=2)
    m.load(config)
    state = m._get_locked_state("dummy")
    assert len(state.running) == 2
    m.stop()
    m.run()

def test_scalein():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=1)
    m.load(config)
    state = m._get_locked_state("dummy")

    assert len(state.running) == 1
    ret = m.scale("dummy", 1)
    assert ret == 2

    time.sleep(0.2)
    assert len(state.running) == 2

    ret = m.scale("dummy", 1)
    assert ret == 3

    time.sleep(0.2)
    assert len(state.running) == 3


    ret = m.scale("dummy", 3)
    assert ret == 6

    time.sleep(0.2)
    assert len(state.running) == 6

    m.stop()
    m.run()

def test_scaleout():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    m.load(config)
    state = m._get_locked_state("dummy")


    assert len(state.running) == 4
    ret = m.scale("dummy", -1)
    assert ret == 3

    time.sleep(0.2)
    assert len(state.running) == 3

    ret = m.scale("dummy", -2)
    assert ret == 1

    time.sleep(0.2)
    assert len(state.running) == 1
    m.stop()
    m.run()

def test_numprocesses():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    m.load(config)
    state = m._get_locked_state("dummy")

    assert len(state.running) == 4
    state.numprocesses = 0
    assert state.numprocesses == 0

    m.manage("dummy")
    time.sleep(0.2)
    assert len(state.running) == 0
    m.stop()
    m.run()

def test_process_id():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    m.load(config)
    state = m._get_locked_state("dummy")

    res = []
    def cb(m, p):
        res.append(p.pid)

    res2 = [p.pid for p in m.list("dummy")]
    m.walk(cb, "dummy")
    m.stop()
    m.run()

    assert res == [1, 2, 3, 4]
    assert res == res2

def test_restart_process():
    results = []
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    m.load(config)

    results.append(m.pids("dummy"))
    m.reload("dummy")

    def cb(handle):
        results.append(m.pids("dummy"))
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(cb, 0.4, 0.0)
    m.run()

    assert results[0] != results[1]

def test_restart_manager():
    results = []
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    m.load(config)
    results.append(m.pids("dummy"))

    def cb(manager):
        results.append(m.pids("dummy"))
        m.stop()

    m.restart()
    t = pyuv.Timer(m.loop)
    t.start(cb, 0.4, 0.0)
    m.run()

    assert results[0] != results[1]

def test_send_signal():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    m.load(config)
    time.sleep(0.2)

    m.killall("dummy", signal.SIGHUP)
    time.sleep(0.2)


    with pytest.raises(ProcessError) as e:
        m.killall("dummy1", signal.SIGHUP)
        assert e.errno == 404

    m.stop_job("dummy")

    def stop(handle):
        handle.stop()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.8, 0.0)
    m.run()

    with open(testfile, 'r') as f:
        res = f.read()
        assert res == 'STARTHUPQUITSTOP'

def test_flapping():
    m = Manager()
    m.start()
    states = []
    cmd, args, wdir = crash_cmd()

    # create flapping info object
    flapping = FlappingInfo(attempts=1., window=1, retry_in=0.1,
            max_retry=1)

    # load conf
    conf1 = ProcessConfig("crashing", cmd, args=args, cwd=wdir,
            flapping=flapping)
    conf2 = ProcessConfig("crashing2", cmd, args=args, cwd=wdir)
    m.load(conf1)
    m.load(conf2)

    time.sleep(0.2)

    def cb(handle):
        state = m._get_locked_state("crashing")
        states.append(state.stopped)
        state2 = m._get_locked_state("crashing2")
        states.append(state2.stopped)
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(cb, 0.8, 0.0)
    m.run()

    assert states == [True, False]

def test_events():
    emitted = []
    m = Manager()
    m.start()

    def cb(ev, msg):
        emitted.append((ev, msg['name']))

    # subscribe to all events
    m.events.subscribe('.', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    m.load(config)
    m.scale("dummy", 1)
    m.unload("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()

    assert ('load', 'default.dummy') in emitted
    assert ('start', 'default.dummy') in emitted
    assert ('update', 'default.dummy') in emitted
    assert ('stop', 'default.dummy') in emitted
    assert ('unload', 'default.dummy') in emitted

def test_process_events():
    emitted = []
    m = Manager()
    m.start()

    def cb(ev, *args):
        emitted.append(ev)

    # subscribe to all events
    m.events.subscribe('job.default.dummy', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    m.load(config)
    m.unload("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()

    assert 'job.default.dummy.start' in emitted
    assert 'job.default.dummy.spawn' in emitted
    assert 'job.default.dummy.stop' in emitted
    assert 'job.default.dummy.exit' in emitted

def test_process_exit_event():
    emitted = []
    m = Manager()
    m.start()

    def cb(ev, msg):
        emitted.append(msg)

    # subscribe to all events
    m.events.subscribe('job.default.dummy.exit', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    m.load(config)
    m.unload("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()

    assert len(emitted) == 1
    assert len(emitted[0]) == 7

    msg = emitted[0]
    assert "exit_status" in msg
    assert msg['once'] == False

def test_process_stats():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    m.load(config)
    time.sleep(0.2)
    info = m.stats("dummy")
    info_by_id = m.get_process(1).info
    os_pid = m.running[1].os_pid
    m.stop()
    m.run()

    assert isinstance(info, dict)
    assert isinstance(info_by_id, dict)
    assert "os_pid" in info_by_id
    assert info_by_id["os_pid"] == os_pid
    assert info['name'] == "default.dummy"
    assert len(info['stats']) == 1
    assert info['stats'][0]['os_pid'] == info_by_id['os_pid']

def test_processes_stats():

    def collect_cb(inf, m, name):
        inf.append(m.stats(name))

    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    testfile1, cmd1, args1, wdir1 = dummy_cmd()
    configa = ProcessConfig("a", cmd, args=args, cwd=wdir)
    m.load(configa)

    time.sleep(0.2)
    infos = []
    infos2 = []
    m.jobs_walk(partial(collect_cb, infos))
    configb = ProcessConfig("b", cmd, args=args, cwd=wdir)
    m.load(configb)
    m.jobs_walk(partial(collect_cb, infos2))
    m.stop()
    m.run()

    assert len(infos) == 1
    assert len(infos2) == 2
    assert infos[0]['name'] == "default.a"
    assert infos2[0]['name'] == "default.a"
    assert infos2[1]['name'] == "default.b"

def test_monitor():
    m = Manager()
    monitored = []
    def cb(evtype, info):
        monitored.append((evtype, info))

    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    configa = ProcessConfig("a", cmd, args=args, cwd=wdir)
    m.load(configa)
    time.sleep(0.2)
    os_pid = m.running[1].os_pid
    m.monitor(cb, "a")

    def stop(handle):
        m.unmonitor(cb, "a")
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.3, 0.0)

    m.run()
    assert len(monitored) >= 1
    res = monitored[0]
    assert res[0] == "stat"
    assert "cpu" in res[1]
    assert res[1]["os_pid"] == os_pid

def test_priority():
    m = Manager()
    started = []
    def cb(evtype, info):
        started.append(info['name'])

    m.start()
    m.events.subscribe('start', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    a = ProcessConfig("a", cmd, args=args, cwd=wdir)
    b = ProcessConfig("b", cmd, args=args, cwd=wdir)
    c = ProcessConfig("c", cmd, args=args, cwd=wdir)


    m.load(a, start=False)
    m.load(b, start=False)
    m.load(c, start=False)

    # start all processes
    m.jobs_walk(lambda mgr, label: mgr.start_job(label))

    def stop(handle):
        m.events.unsubscribe("start", cb)
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.4, 0.0)
    m.run()

    assert started == ["default.a", "default.b", "default.c"]

def test_sessions():
    m = Manager()
    started = []
    stopped = []
    def cb(evtype, info):
        if evtype == "start":
            started.append(info['name'])
        elif evtype == "stop":
            stopped.append(info['name'])

    start_job = lambda mgr, label: mgr.start_job(label)
    stop_job = lambda mgr, label: mgr.stop_job(label)

    m.start()
    m.events.subscribe('start', cb)
    m.events.subscribe('stop', cb)
    testfile, cmd, args, wdir = dummy_cmd()
    a = ProcessConfig("a", cmd, args=args, cwd=wdir)
    b = ProcessConfig("b", cmd, args=args, cwd=wdir)


    # load process config in different sessions
    m.load(a, sessionid="ga", start=False)
    m.load(b, sessionid="ga", start=False)
    m.load(a, sessionid="gb", start=False)


    sessions = m.sessions

    ga1 = m.jobs('ga')
    gb1 = m.jobs('gb')

    m.jobs_walk(start_job, "ga")
    m.jobs_walk(start_job, "gb")

    ga2 = []
    def rem_cb(h):
        m.unload("a", sessionid="ga")
        [ga2.append(name) for name in m.jobs('ga')]


    t0 = pyuv.Timer(m.loop)
    t0.start(rem_cb, 0.2, 0.0)
    m.jobs_walk(stop_job, "gb")

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


def test_process_commit():
    emitted = []
    m = Manager()
    m.start()

    def cb(ev, msg):
        emitted.append(msg)

    # subscribe to all events
    m.events.subscribe('job.default.dummy.exit', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=0)
    m.load(config)

    pids0 = m.pids()
    pid = m.commit("dummy", env={"BLAH": "test"})
    process = m.get_process(pid)
    pids1 = m.pids()

    state = m._get_locked_state("dummy")

    assert len(state.running) == 0
    assert state.numprocesses == 0
    assert len(state.running_out) == 1


    m.unload("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()

    assert pids0 == []
    assert pid == 1
    assert process.name == "default.dummy"
    assert process.pid == 1
    assert "BLAH" in process.env
    assert pids1 == [1]

    assert len(emitted) == 1
    assert len(emitted[0]) == 7

    msg = emitted[0]
    assert "exit_status" in msg
    assert msg['once'] == True

if __name__ == "__main__":
    test_sessions()
