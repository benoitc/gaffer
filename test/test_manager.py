# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import signal
import sys
import time
from tempfile import mkstemp

import pyuv

from gaffer.manager import Manager, FlappingInfo
from gaffer.process import Process

class DummyProcess(object):

    def __init__(self, testfile):
        self.alive = True
        self.testfile = testfile
        signal.signal(signal.SIGHUP, self.handle_hup)
        signal.signal(signal.SIGQUIT, self.handle_quit)
        signal.signal(signal.SIGTERM, self.handle_quit)
        signal.signal(signal.SIGCHLD, self.handle_chld)

    def _write(self, msg):
        with open(self.testfile, 'a+') as f:
            f.write(msg)

    def handle_quit(self, *args):
        self._write('QUIT')
        self.alive = False

    def handle_chld(self, *args):
        self._write('CHLD')

    def handle_hup(self, *args):
        self._write('HUP')

    def run(self):
        self._write('START')

        # write to std
        sys.stdout.write("hello out")
        sys.stdout.flush()
        sys.stderr.write("hello err")
        sys.stderr.flush()

        while self.alive:
            time.sleep(0.001)
        self._write('STOP')


def run_dummy(test_file):
    dummy = DummyProcess(test_file)
    dummy.run()
    return 1

def tmpfile():
     fd, testfile = mkstemp()
     os.close(fd)
     return testfile

def dummy_cmd():
    fd, testfile = mkstemp()
    os.close(fd)
    cmd = sys.executable
    args = ['generic.py', "test_manager.run_dummy", testfile]
    wdir = os.path.dirname(__file__)
    return (testfile, cmd, args, wdir)


class CrashProcess(object):

    def __init__(self):
        self.alive = True

    def run(self):
        while self.alive:
            time.sleep(0.1)
            break

def run_crashprocess():
    c = CrashProcess()
    c.run()
    return 1


def crash_cmd():
    cmd = sys.executable
    args = ['generic.py', "test_manager.run_crashprocess"]
    wdir = os.path.dirname(__file__)
    return (cmd, args, wdir)

class EchoProcess(object):

    def __init__(self, *args):
        self.alive = True
        signal.signal(signal.SIGQUIT, self.handle_quit)
        signal.signal(signal.SIGTERM, self.handle_quit)
        signal.signal(signal.SIGINT, self.handle_quit)
        signal.signal(signal.SIGCHLD, self.handle_chld)

    def handle_quit(self, *args):
        self.alive = False

    def handle_chld(self, *args):
        pass



    def run(self):
        while self.alive:
            c = sys.stdin.readline()
            print(c)
            sys.stdout.flush()
            if c == "exit\n":
                break

def run_echocmd():
    c = EchoProcess()
    c.run()
    return 1

def echo_cmd():
    fd, testfile = mkstemp()
    os.close(fd)
    cmd = sys.executable
    args = ['generic.py', "test_manager.run_echocmd", testfile]
    wdir = os.path.dirname(__file__)
    print(cmd, " ".join(args))
    return (cmd, args, wdir)



def test_simple():
    m = Manager()
    m.start()
    assert m.started == True

    def on_stop(manager):
        assert manager.started == False

    m.stop(on_stop)
    m.run()

def test_simple_process():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, start=False)
    state = m.get_process_state("dummy")

    assert state.numprocesses == 1
    assert state.name == "dummy"
    assert state.cmd == cmd
    assert state.settings['args'] == args
    assert state.settings['cwd'] == wdir

    m.remove_process("dummy")
    assert m.get_process_state("dummy") == None
    m.stop()
    m.run()

def test_start_stop_process():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir)
    state = m.get_process_state("dummy")

    assert len(state.running) == 1

    m.stop_process("dummy")
    assert len(state.running) == 0

    m.stop()
    m.run()


def test_start_multiple():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=2)
    state = m.get_process_state("dummy")

    assert len(state.running) == 2

    m.stop()

    m.run()

def test_ttin():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=1)
    state = m.get_process_state("dummy")

    assert len(state.running) == 1
    ret = m.ttin("dummy", 1)
    assert ret == 2

    time.sleep(0.2)
    assert len(state.running) == 2

    ret = m.ttin("dummy", 1)
    assert ret == 3

    time.sleep(0.2)
    assert len(state.running) == 3


    ret = m.ttin("dummy", 3)
    assert ret == 6

    time.sleep(0.2)
    assert len(state.running) == 6

    m.stop()
    m.run()

def test_ttou():
    m = Manager()
    m.start()

    testfile, cmd, args, wdir = dummy_cmd()

    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    state = m.get_process_state("dummy")

    assert len(state.running) == 4
    ret = m.ttou("dummy", 1)
    assert ret == 3

    time.sleep(0.2)
    assert len(state.running) == 3

    ret = m.ttou("dummy", 2)
    assert ret == 1

    time.sleep(0.2)
    assert len(state.running) == 1
    m.stop()
    m.run()

def test_numprocesses():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    state = m.get_process_state("dummy")

    assert len(state.running) == 4
    state.numprocesses = 0
    assert state.numprocesses == 0

    m.manage_process("dummy")
    time.sleep(0.2)
    assert len(state.running) == 0
    m.stop()

    m.run()

def test_process_id():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    state = m.get_process_state("dummy")

    processes = state.list_processes()
    assert isinstance(processes, list)

    p = processes[0]
    assert isinstance(p, Process)
    assert p.id == 1

    p = processes[2]
    assert p.id == 3

    m.stop()

    m.run()

def test_restart():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    state = m.get_process_state("dummy")

    a = state.list_processes()
    m.restart_process("dummy")
    b = state.list_processes()
    assert a != b

    def on_restart(manager):
        state = m.get_process_state("dummy")
        c = state.list_processes()
        assert b != c
        m.stop()

    m.restart(on_restart)
    m.run()

def test_send_signal():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir)
    state = m.get_process_state("dummy")
    processes = state.list_processes()

    time.sleep(0.2)
    m.send_signal("dummy", signal.SIGHUP)
    time.sleep(0.2)
    m.send_signal(processes[0].id, signal.SIGHUP)
    m.stop_process("dummy")
    time.sleep(0.2)
    with open(testfile, 'r') as f:
        res = f.read()
        assert res == 'STARTHUPHUPQUITSTOP'

    m.stop()

    m.run()

def test_flapping():
    m = Manager()
    m.start()

    cmd, args, wdir = crash_cmd()
    flapping = FlappingInfo(attempts=1, window=1, retry_in=0.1, max_retry=2)
    m.add_process("crashing", cmd, args=args, cwd=wdir, flapping=flapping)
    state = m.get_process_state("crashing")

    def cb(handle):
        handle.stop()
        assert state.stopped == True

    t = pyuv.Timer(m.loop)
    t.start(cb, 0.8, 0.8)


    m.add_process("crashing2", cmd, args=args, cwd=wdir)
    state = m.get_process_state("crashing2")

    def cb1(handle):
        handle.stop()
        assert state.stopped == False

    t = pyuv.Timer(m.loop)
    t.start(cb1, 0.8, 0.8)

    m.stop()
    m.run()


def test_events():
    emitted = []
    m = Manager()
    m.start()

    def cb(ev, msg):
        emitted.append((ev, msg['name']))

    # subscribe to all events
    m.on('.', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    m.ttin("dummy", 1)
    m.remove_process("dummy")

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
    m.on('proc.dummy', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir)
    m.stop_process("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()


    assert 'proc.dummy.start' in emitted
    assert 'proc.dummy.spawn' in emitted
    assert 'proc.dummy.stop' in emitted
    assert 'proc.dummy.exit' in emitted


def test_process_exit_event():
    emitted = []
    m = Manager()
    m.start()

    def cb(ev, msg):
        emitted.append(msg)

    # subscribe to all events
    m.on('proc.dummy.exit', cb)

    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir)
    m.stop_process("dummy")

    time.sleep(0.2)
    m.stop()
    m.run()

    assert len(emitted) == 1
    assert len(emitted[0]) == 5

    msg = emitted[0]
    assert "exit_status" in msg

def test_process_stats():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir)
    time.sleep(0.2)
    info = m.get_process_stats("dummy")
    info_by_id = m.get_process_stats(1)
    pid = m.running[1].pid
    m.stop()
    m.run()

    assert isinstance(info, dict)
    assert isinstance(info_by_id, dict)
    assert "pid" in info_by_id
    assert info_by_id["pid"] == pid
    assert info['name'] == "dummy"
    assert len(info['stats']) == 1
    assert info['stats'][0]['pid'] == info_by_id['pid']

def test_processes_stats():
    m = Manager()
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    testfile1, cmd1, args1, wdir1 = dummy_cmd()
    m.add_process("a", cmd, args=args, cwd=wdir)
    time.sleep(0.2)
    infos = list(m.processes_stats())
    pid = m.running[1].pid
    m.add_process("b", cmd, args=args, cwd=wdir)
    infos2 = list(m.processes_stats())
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
    m.add_process("a", cmd, args=args, cwd=wdir)
    time.sleep(0.2)
    pid = m.running[1].pid
    m.monitor("a", cb)

    def stop(handle):
        m.unmonitor("a", cb)
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.3, 0.0)

    m.run()
    assert len(monitored) >= 1
    res = monitored[0]
    assert res[0] == "stat"
    assert "cpu" in res[1]
    assert res[1]["pid"] == pid
