# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import signal
import sys
import time
from tempfile import mkstemp

from gaffer.manager import get_manager
from gaffer.process import Process

class DummyProcess(object):

    def __init__(self, testfile):
        self.alive = True
        self.testfile = testfile
        import signal
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

def test_simple():
    m = get_manager(background=True)
    m.start()
    assert m.manager.started == True
    m.stop()
    assert m.manager.started == False

def test_simple_process():
    m = get_manager(background=True)
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

def test_start_stop_process():
    m = get_manager(background=True)
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir)
    state = m.get_process_state("dummy")

    assert len(state.running) == 1

    m.stop_process("dummy")
    assert len(state.running) == 0

    m.stop()


def test_start_multiple():
    m = get_manager(background=True)
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=2)
    state = m.get_process_state("dummy")

    assert len(state.running) == 2

    m.stop()

def test_ttin():
    m = get_manager(background=True)
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


def test_ttou():
    m = get_manager(background=True)
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

def test_numprocesses():
    m = get_manager(background=True)
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

def test_process_id():
    m = get_manager(background=True)
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

def test_restart():
    m = get_manager(background=True)
    m.start()
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    state = m.get_process_state("dummy")

    a = state.list_processes()
    m.restart_process("dummy")
    b = state.list_processes()
    assert a != b

    m.stop()

def test_send_signal():
    m = get_manager(background=True)
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
