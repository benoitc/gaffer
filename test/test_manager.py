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

from gaffer.error import ProcessError
from gaffer.manager import Manager
from gaffer.process import Process
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

def test_simple_template():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir, start=False)
    state = m.get_template("dummy")

    assert state.numprocesses == 1
    assert state.name == "dummy"
    assert state.appname == "system"
    assert state.cmd == cmd
    assert state.settings['args'] == args
    assert state.settings['cwd'] == wdir

    m.remove_template("dummy")

    with pytest.raises(ProcessError):
        m.get_template("dummy")

    m.stop()
    m.run()

def test_start_stop_template():
    res = []
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir)
    state = m.get_template("dummy")
    res.append(len(state.running))
    m.stop_template("dummy")
    res.append(len(state.running))
    m.stop()
    m.run()

    print(res)
    assert res == [1, 0]


def test_start_multiple():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir, numprocesses=2)
    state = m.get_template("dummy")
    assert len(state.running) == 2
    m.stop()
    m.run()

def test_scalein():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir, numprocesses=1)
    state = m.get_template("dummy")

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

    m.add_template("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    state = m.get_template("dummy")

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
    m.add_template("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    state = m.get_template("dummy")

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
    m.add_template("dummy", cmd, args=args, cwd=wdir, numprocesses=4)

    res = []
    def cb(m, p):
        res.append(p.pid)

    m.walk_processes(cb, "dummy")
    m.stop()
    m.run()

    assert res == [1, 2, 3, 4]

def test_restart_process():
    results = []
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    state = m.get_template("dummy")
    results.append(state.pids)
    m.restart_template("dummy")

    def cb(handle):
        state = m.get_template("dummy")
        results.append(state.pids)
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
    m.add_template("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    state = m.get_template("dummy")
    results.append(state.pids)

    def cb(manager):
        state = m.get_template("dummy")
        results.append(state.pids)
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
    m.add_template("dummy", cmd, args=args, cwd=wdir)
    time.sleep(0.2)
    state = m.get_template("dummy")
    processes = state.list_processes()
    m.send_signal("dummy", signal.SIGHUP)
    time.sleep(0.2)


    with pytest.raises(ProcessError) as e:
        m.send_signal("dummy1", signal.SIGHUP)
        assert e.errno == 404

    m.stop_process("dummy")

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
    flapping = FlappingInfo(attempts=1., window=1, retry_in=0.1,
            max_retry=1)
    m.add_template("crashing", cmd, args=args, cwd=wdir, flapping=flapping)
    m.add_template("crashing2", cmd, args=args, cwd=wdir)
    time.sleep(0.2)

    def cb(handle):
        state = m.get_template("crashing")
        states.append(state.stopped)
        state2 = m.get_template("crashing2")
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
    m.subscribe('.', cb)

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
    m.subscribe('proc.system.dummy', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir)
    m.stop_template("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()

    assert 'proc.system.dummy.start' in emitted
    assert 'proc.system.dummy.spawn' in emitted
    assert 'proc.system.dummy.stop' in emitted
    assert 'proc.system.dummy.exit' in emitted

def test_process_exit_event():
    emitted = []
    m = Manager()
    m.start()

    def cb(ev, msg):
        emitted.append(msg)

    # subscribe to all events
    m.subscribe('proc.system.dummy.exit', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir)
    m.stop_template("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()

    assert len(emitted) == 1
    assert len(emitted[0]) == 7

    msg = emitted[0]
    assert "exit_status" in msg

def test_process_stats():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("dummy", cmd, args=args, cwd=wdir)
    time.sleep(0.2)
    info = m.get_template_stats("dummy")
    info_by_id = m.get_process(1).info
    os_pid = m.running[1].os_pid
    m.stop()
    m.run()

    assert isinstance(info, dict)
    assert isinstance(info_by_id, dict)
    assert "os_pid" in info_by_id
    assert info_by_id["os_pid"] == os_pid
    assert info['name'] == "dummy"
    assert len(info['stats']) == 1
    assert info['stats'][0]['os_pid'] == info_by_id['os_pid']

def test_processes_stats():

    def collect_cb(inf, m, template):
        inf.append(m.get_template_stats(template.name, template.appname))

    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    testfile1, cmd1, args1, wdir1 = dummy_cmd()
    m.add_template("a", cmd, args=args, cwd=wdir)
    time.sleep(0.2)
    infos = []
    infos2 = []
    m.walk(partial(collect_cb, infos))
    m.add_template("b", cmd, args=args, cwd=wdir)
    m.walk(partial(collect_cb, infos2))
    m.stop()
    m.run()

    assert len(infos) == 1
    assert len(infos2) == 2
    assert infos[0]['name'] == "a"
    assert infos2[0]['name'] == "a"
    assert infos2[1]['name'] == "b"

def test_monitor():
    m = Manager()
    monitored = []
    def cb(evtype, info):
        monitored.append((evtype, info))

    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("a", cmd, args=args, cwd=wdir)
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
    m.subscribe('start', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("a", cmd, args=args, cwd=wdir, start=False)
    m.add_template("d", cmd, args=args, cwd=wdir, start=False)
    m.add_template("b", cmd, args=args, cwd=wdir, start=False)

    # start all processes
    m.walk(lambda m, t: m.start_template(t.name, t.appname))

    def stop(handle):
        m.unsubscribe("start", cb)
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.4, 0.0)
    m.run()

    assert started == ["a", "d", "b"]

def test_application():
    m = Manager()
    started = []
    stopped = []
    def cb(evtype, info):
        print(info)
        if evtype == "start":
            started.append((info['appname'], info['name']))
        elif evtype == "stop":
            stopped.append((info['appname'], info['name']))

    m.start()
    m.subscribe('start', cb)
    m.subscribe('stop', cb)
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_template("a", cmd, appname="ga", args=args, cwd=wdir, start=False)
    m.add_template("b", cmd, appname="ga", args=args, cwd=wdir, start=False)
    m.add_template("a", cmd, appname="gb", args=args, cwd=wdir, start=False)

    apps = m.all_apps()

    ga1 = [name for name in m.get_templates('ga')]
    gb1 = [name for name in m.get_templates('gb')]

    start_app = lambda m, t: m.start_template(t.name, t.appname)
    stop_app = lambda m, t: m.stop_template(t.name, t.appname)


    m.walk_templates(start_app, "ga")
    m.walk_templates(start_app, "gb")

    ga2 = []
    def rem_cb(h):
        m.remove_template("a", "ga")
        [ga2.append(name) for name in m.get_templates('ga')]

    t0 = pyuv.Timer(m.loop)
    t0.start(rem_cb, 0.2, 0.0)
    m.walk_templates(stop_app, "gb")

    def stop(handle):
        m.unsubscribe("start", cb)
        m.unsubscribe("stop", cb)
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
    test_start_stop_template()
