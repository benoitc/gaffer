# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import signal
import sys
import time
import socket

import pyuv
from gaffer.process import Process

from test_manager import dummy_cmd

if sys.version_info >= (3, 0):
    linesep = os.linesep.encode()
else:
    linesep = os.linesep

def test_simple():
    exit_res = []
    def exit_cb(process, return_code, term_signal):
        exit_res.append(process)


    loop = pyuv.Loop.default_loop()
    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd, on_exit_cb=exit_cb)

    assert p.pid == "someid"
    assert p.name == "dummy"
    assert p.cmd == cmd
    assert p.args == args
    assert cwd == cwd

    p.spawn()
    assert p.active == True

    time.sleep(0.2)
    p.stop()
    loop.run()
    assert p.active == False
    with open(testfile, 'r') as f:
        res = f.read()
        assert res == 'STARTQUITSTOP'

    assert len(exit_res) == 1
    assert exit_res[0].name == "dummy"
    assert exit_res[0].active == False


def test_signal():
    loop = pyuv.Loop.default_loop()
    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd)
    p.spawn()
    time.sleep(0.2)
    p.kill(signal.SIGHUP)
    time.sleep(0.2)
    p.stop()
    loop.run()
    with open(testfile, 'r') as f:
        res = f.read()
        assert res == 'STARTHUPQUITSTOP'


def test_info():
    loop = pyuv.Loop.default_loop()
    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd)
    p.spawn()
    time.sleep(0.2)
    info = p.info
    os_pid = p.os_pid
    p.stop()
    loop.run()

    assert info['os_pid'] == os_pid
    assert info['name'] == "dummy"
    assert info['pid'] == "someid"



def test_stats():
    loop = pyuv.Loop.default_loop()
    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd)
    p.spawn()
    time.sleep(0.2)
    stats = p.stats
    os_pid = p.os_pid
    p.stop()
    loop.run()

    assert "cpu" in stats
    assert "mem_info1" in stats


def test_stat_events():
    loop = pyuv.Loop.default_loop()
    monitored = []
    def cb(evtype, info):
        monitored.append((evtype, info))

    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd)
    p.spawn()
    time.sleep(0.2)
    os_pid = p.os_pid
    p.monitor(cb)

    def stop(handle):
        p.unmonitor(cb)
        assert p._process_watcher.active == False
        p.stop()

    t = pyuv.Timer(loop)
    t.start(stop, 0.3, 0.0)
    loop.run()

    assert len(monitored) >= 1
    res = monitored[0]
    assert res[0] == "stat"
    assert "cpu" in res[1]
    assert "mem_info1" in res[1]
    assert res[1]['os_pid'] == os_pid


def test_stat_events_refcount():
    loop = pyuv.Loop.default_loop()
    monitored = []
    def cb(evtype, info):
        monitored.append((evtype, info))

    def cb2(evtype, info):
        monitored.append((evtype, info))

    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd)
    p.spawn()
    time.sleep(0.2)
    os_pid = p.os_pid
    p.monitor(cb)
    p.monitor(cb2)
    def stop(handle):
        p.unmonitor(cb)
        assert p._process_watcher.active == True
        assert p._process_watcher._refcount == 1
        p.unmonitor(cb2)
        assert p._process_watcher.active == False
        p.stop()

    t = pyuv.Timer(loop)
    t.start(stop, 0.3, 0.0)
    loop.run()

    assert len(monitored) >= 2
    res = monitored[0]
    assert res[0] == "stat"
    assert "cpu" in res[1]


def test_redirect_output():
    loop = pyuv.Loop.default_loop()
    monitored1 = []
    monitored2 = []
    def cb(evtype, info):
        monitored1.append((evtype, info))

    def cb2(evtype, info):
        monitored2.append((evtype, info))

    testfile, cmd, args, cwd = dummy_cmd()
    p = Process(loop, "someid", "dummy", cmd, args=args,
        cwd=cwd, redirect_output=["stdout", "stderr"])
    p.spawn()
    time.sleep(0.2)
    os_pid = p.os_pid

    p.monitor_io("stdout", cb)
    p.monitor_io("stderr", cb2)

    p.stop()
    loop.run()

    assert len(monitored1) == 1
    assert len(monitored2) == 1

    ev1 = monitored1[0]
    ev2 = monitored2[0]

    assert ev1[0] == 'stdout'
    assert ev1[1] == {'data': b'hello out', 'pid': "someid", 'name': 'dummy',
            'event': 'stdout'}

    assert ev2[0] == 'stderr'
    assert ev2[1] == {'data': b'hello err', 'pid': "someid", 'name': 'dummy',
            'event': 'stderr'}

def test_redirect_input():
    loop = pyuv.Loop.default_loop()
    monitored = []
    def cb(evtype, info):
        monitored.append(info['data'])

    if sys.platform == 'win32':
        p = Process(loop, "someid", "echo", "cmd.exe",
                args=["/c", "proc_stdin_stdout.py"],
                redirect_output=["stdout"], redirect_input=True)

    else:
        p = Process(loop, "someid", "echo", "./proc_stdin_stdout.py",
            cwd=os.path.dirname(__file__),
            redirect_output=["stdout"], redirect_input=True)
    p.spawn()
    time.sleep(0.2)
    p.monitor_io("stdout", cb)
    p.write(b"ECHO" + linesep)

    def stop(handle):
        p.unmonitor_io("stdout", cb)
        p.stop()

    t = pyuv.Timer(loop)
    t.start(stop, 0.3, 0.0)
    loop.run()

    assert len(monitored) == 1
    assert monitored == [b'ECHO\n\n']

def test_custom_stream():
    loop = pyuv.Loop.default_loop()
    monitored = []
    def cb(evtype, info):
        monitored.append(info['data'])

    if sys.platform == 'win32':
        p = Process(loop, "someid", "echo", "cmd.exe",
                args=["/c", "proc_custom_stream.py"],
                custom_streams=['ctrl'])

    else:
        p = Process(loop, "someid", "echo", "./proc_custom_stream.py",
                cwd=os.path.dirname(__file__),
                custom_streams=['ctrl'])
    p.spawn()
    time.sleep(0.2)
    stream = p.streams['ctrl']
    assert stream.id == 3
    stream.subscribe(cb)
    stream.write(b"ECHO" + linesep)

    def stop(handle):
        stream.unsubscribe(cb)
        p.stop()

    t = pyuv.Timer(loop)
    t.start(stop, 0.3, 0.0)
    loop.run()

    assert len(monitored) == 1
    assert monitored == [b'ECHO\n']

def test_custom_channel():
    if sys.platform == 'win32':
        return

    loop = pyuv.Loop.default_loop()
    sockets = socket.socketpair(socket.AF_UNIX)
    pipes = []
    for sock in sockets:
        pipe = pyuv.Pipe(loop)
        pipe.open(sock.fileno())
        pipes.append(pipe)
    channel = pipes[0]
    monitored = []
    def cb(handle, data, error):
        if not data:
            return
        monitored.append(data)

    p = Process(loop, "someid", "echo", "./proc_custom_stream.py",
            cwd=os.path.dirname(__file__),
            custom_channels=[pipes[1]])

    p.spawn()
    channel.start_read(cb)
    time.sleep(0.2)
    channel.write(b"ECHO" + linesep)

    def stop(handle):
        channel.stop_read()
        p.stop()

    t = pyuv.Timer(loop)
    t.start(stop, 0.3, 0.0)
    loop.run()

    assert len(monitored) == 1
    assert monitored == [b'ECHO\n']

def test_substitue_env():
    loop = pyuv.Loop.default_loop()

    cmd = 'echo "test" > $NULL_PATH'
    env = {"NULL_PATH": "/dev/null"}
    p = Process(loop, "someid", "null", cmd, env=env,
            cwd=os.path.dirname(__file__),
            redirect_output=["stdout"], redirect_input=True)

    cmd2 = "echo"
    args = ["test", ">", "$NULL_PATH"]
    p2 = Process(loop, "someid", "null", cmd2, args=args,
            env=env, cwd=os.path.dirname(__file__),
            redirect_output=["stdout"], redirect_input=True)


    assert "/dev/null" in p.args
    assert "$NULL_PATH" not in p.args
    assert "/dev/null" in p2.args
    assert "$NULL_PATH" not in p2.args
