# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import signal
import time

import pyuv

from gaffer.error import ProcessError, CommandError, CommandNotFound
from gaffer.controller import Controller, Command
from gaffer.manager import Manager
from gaffer.process import ProcessConfig

from test_manager import dummy_cmd

class TestCommand(Command):

    def __init__(self, name, args=None, kwargs=None):
        super(TestCommand, self).__init__(name, args=args, kwargs=kwargs)
        self.result = None
        self.error = None

    def reply(self, result):
        self.result = result

    def reply_error(self, error):
        self.error = error

def init():
    m = Manager()
    m.start()
    ctl = Controller(m)
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    return m, ctl, config

def init1():
    m = Manager()
    m.start()
    ctl = Controller(m)
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir)
    return m, ctl, testfile, config

def test_basic():
    m, ctl, conf = init()

    config = conf.to_dict()
    cmd = TestCommand("load", [config], {"start": False})
    ctl.process_command(cmd)

    state = m._get_locked_state("dummy")

    assert state.numprocesses == 1
    assert state.name == "default.dummy"
    assert state.cmd == config['cmd']
    assert state.config['args'] == config['args']
    assert state.config['cwd'] == config['cwd']

    cmd1 =  TestCommand("unload", ["dummy"])
    ctl.process_command(cmd1)

    assert m.jobs() == []

    m.stop()
    m.run()

    assert cmd.error == None
    assert cmd.result == {"ok": True}
    assert cmd1.error == None
    assert cmd1.result == {"ok": True}

def test_basic_error():
    m, ctl, config = init()

    cmd = TestCommand("info", ["dummy"])
    ctl.process_command(cmd)

    m.stop()
    m.run()

    assert cmd.result == None
    assert cmd.error == {"errno": 404, "reason": "not_found"}

def test_command_not_found():
    m, ctl, config = init()

    cmd = TestCommand("nocommand")
    ctl.process_command(cmd)

    m.stop()
    m.run()

    assert cmd.result == None
    assert cmd.error == {"errno": 404, "reason": "command_not_found"}

def test_bad_command():
    m, ctl, config = init()

    cmd = TestCommand("load")
    ctl.process_command(cmd)

    m.stop()
    m.run()

    assert cmd.result == None
    assert cmd.error['errno'] == 400

def test_jobs():
    m, ctl, config = init()
    m.load(config)
    cmd = TestCommand("jobs")
    ctl.process_command(cmd)

    cmd1 = TestCommand("jobs", ["default"])
    ctl.process_command(cmd1)

    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert "jobs" in cmd.result
    assert cmd.result['jobs'] == ["default.dummy"]
    assert isinstance(cmd1.result, dict)
    assert "jobs" in cmd1.result
    assert cmd1.result['jobs'] == ["default.dummy"]

def test_sessions():
    m, ctl, config = init()
    m.load(config)
    cmd = TestCommand("sessions")
    ctl.process_command(cmd)
    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert "sessions" in cmd.result
    assert cmd.result['sessions'] == ["default"]

def test_pids():
    m, ctl, config = init()
    m.load(config)
    cmd = TestCommand("pids")
    ctl.process_command(cmd)
    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert "pids" in cmd.result
    assert cmd.result['pids'] == [1]

def test_reload():
    m, ctl, config = init()
    m.load(config)

    pids = m.pids()
    cmd = TestCommand("reload", ["dummy"])
    ctl.process_command(cmd)

    pids1 = m.pids()
    jobs = m.jobs()
    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert cmd.result == {"ok": True}
    assert pids != pids1
    assert "default.dummy" in jobs

def test_update():
    m, ctl, config = init()
    m.load(config)

    pids = m.pids()
    config['numprocesses'] = 2
    cmd = TestCommand("update", [config.to_dict()])
    ctl.process_command(cmd)
    m.manage("dummy")
    pids1 = m.pids()
    jobs = m.jobs()
    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert cmd.result == {"ok": True}
    assert pids != pids1
    assert "default.dummy" in jobs
    assert len(pids) == 1
    assert len(pids1) == 2

def test_start_job():
    m, ctl, config = init()
    m.load(config, start=False)
    pids = m.pids()

    cmd = TestCommand("start_job", ["dummy"])
    ctl.process_command(cmd)
    pids1 = m.pids()

    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert cmd.result == {"ok": True}
    assert pids != pids1
    assert len(pids) == 0
    assert len(pids1) == 1


def test_stop_job():
    m, ctl, config = init()
    m.load(config)
    pids = m.pids()

    cmd = TestCommand("stop_job", ["dummy"])
    ctl.process_command(cmd)
    pids1 = m.pids()

    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert cmd.result == {"ok": True}
    assert pids != pids1
    assert len(pids) == 1
    assert len(pids1) == 0

def test_scale():
    m, ctl, config = init()
    m.load(config)
    pids = m.pids()

    cmd = TestCommand("scale", ["dummy", 1])
    ctl.process_command(cmd)
    time.sleep(0.1)

    pids1 = m.pids()


    cmd = TestCommand("scale", ["dummy", -1])
    ctl.process_command(cmd)
    time.sleep(0.1)

    pids2 = m.pids()


    cmd = TestCommand("scale", ["dummy", "+4"])
    ctl.process_command(cmd)
    time.sleep(0.1)

    pids3 = m.pids()

    cmd = TestCommand("scale", ["dummy", "-1"])
    ctl.process_command(cmd)
    time.sleep(0.1)

    pids4 = m.pids()


    cmd = TestCommand("scale", ["dummy", "=1"])
    ctl.process_command(cmd)
    time.sleep(0.1)

    pids5 = m.pids()


    m.stop()
    m.run()

    assert len(pids) == 1
    assert len(pids1) == 2
    assert len(pids2) == 1
    assert len(pids3) == 5
    assert len(pids4) == 4
    assert len(pids5) == 1


def test_info():
    m, ctl, config = init()
    m.load(config)

    cmd = TestCommand("info", ["dummy"])
    ctl.process_command(cmd)

    m.scale("dummy", 2)
    time.sleep(0.1)

    cmd1 = TestCommand("info", ["dummy"])
    ctl.process_command(cmd1)

    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert "info" in cmd.result
    info = cmd.result['info']
    assert info['name'] == "default.dummy"
    assert info['active'] == True
    assert info['running'] == 1
    assert info['max_processes'] == 1
    assert "config" in info
    assert info['config'] == config.to_dict()

    assert isinstance(cmd1.result, dict)
    assert "info" in cmd1.result
    info1 = cmd1.result['info']
    assert info1['name'] == "default.dummy"
    assert info1['running'] == 3
    assert info1['config'] == config.to_dict()

def test_stats():
    m, ctl, config = init()
    m.load(config)

    cmd = TestCommand("stats", ["dummy"])
    ctl.process_command(cmd)

    m.scale("dummy", 2)
    time.sleep(0.1)

    cmd1 = TestCommand("stats", ["dummy"])
    ctl.process_command(cmd1)

    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert "stats" in cmd.result
    stats = cmd.result['stats']
    assert isinstance(stats, dict)
    assert stats['name'] == "default.dummy"
    assert "stats" in stats
    assert len(stats['stats']) == 1
    assert stats['stats'][0]['pid'] == 1

    assert isinstance(cmd1.result, dict)
    stats = cmd1.result['stats']
    assert isinstance(stats, dict)
    assert stats['name'] == "default.dummy"
    assert "stats" in stats
    assert len(stats['stats']) == 3

def test_stopall():
    m, ctl, config = init()
    m.load(config)

    pids = m.pids()

    cmd = TestCommand("stopall", ["dummy"])
    ctl.process_command(cmd)

    jobs = m.jobs()
    pids1 = m.pids()

    m.stop()
    m.run()

    assert len(pids) == 1
    assert jobs == ['default.dummy']
    assert len(pids1) == 0

def test_killall():
    m, ctl, testfile, config = init1()
    m.load(config)

    time.sleep(0.1)
    cmd = TestCommand("killall", ["dummy", signal.SIGHUP])
    ctl.process_command(cmd)
    time.sleep(0.2)

    m.stop_job("dummy")
    time.sleep(0.1)

    m.stop()
    m.run()

    assert cmd.result == {"ok": True}
    with open(testfile, 'r') as f:
        res = f.read()
        assert res == 'STARTHUPQUITSTOP'

def test_process_info():
    m, ctl, config = init()
    m.load(config)

    cmd = TestCommand("process_info", [1])
    ctl.process_command(cmd)

    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert "info" in cmd.result
    info = cmd.result['info']
    assert info['name'] == "default.dummy"
    assert info['active'] == True
    assert info['pid'] == 1
    assert info['cmd'] == config['cmd']
    assert info['args'] == config['args']

def test_process_stats():
    m, ctl, config = init()
    m.load(config)

    cmd = TestCommand("process_stats", [1])
    ctl.process_command(cmd)

    m.stop()
    m.run()

    assert isinstance(cmd.result, dict)
    assert "stats" in cmd.result
    stats = cmd.result['stats']
    assert "cpu" in stats

def test_stop_process():
    m, ctl, config = init()
    m.load(config)

    pids = m.pids()

    cmd = TestCommand("stop_process", [1])
    ctl.process_command(cmd)

    result = []
    def wait(h):
        result.append((m.jobs(), m.pids()))
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(wait, 0.2, 0.0)

    m.run()

    assert len(result) == 1
    jobs, pids1 = result[0]

    assert len(pids) == 1
    assert jobs == ['default.dummy']
    assert pids != pids1
    assert len(pids1) == 1

def test_kill_process():
    m, ctl, testfile, config = init1()
    m.load(config)

    time.sleep(0.1)
    cmd = TestCommand("kill", [1, signal.SIGHUP])
    ctl.process_command(cmd)
    time.sleep(0.2)

    m.stop_job("dummy")

    t = pyuv.Timer(m.loop)
    t.start(lambda h: m.stop(), 0.2, 0.0)
    m.run()

    assert cmd.result == {"ok": True}
    with open(testfile, 'r') as f:
        res = f.read()
        assert res == 'STARTHUPQUITSTOP'

def test_process_commit():
    m, ctl, config = init()
    config['numprocesses'] = 0
    m.load(config, start=False)
    cmd = TestCommand("commit", ["dummy"])
    ctl.process_command(cmd)
    time.sleep(0.1)

    state = m._get_locked_state("dummy")
    assert len(state.running) == 0
    assert state.numprocesses == 0
    assert len(state.running_out) == 1
    assert m.pids() == [1]

    m.stop()
    m.run()

    assert cmd.result["pid"] == 1
