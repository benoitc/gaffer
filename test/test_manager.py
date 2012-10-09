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


def CrashProcess(object):

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

    m.stop()
    m.run()

