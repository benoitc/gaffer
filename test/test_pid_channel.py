# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import sys
import time

import pytest
import pyuv

from gaffer.gafferd.http import HttpHandler
from gaffer.httpclient import Server, Process
from gaffer.httpclient.websocket import IOChannel
from gaffer.manager import Manager
from gaffer.process import ProcessConfig

from test_manager import dummy_cmd
from test_http import MockConfig

TEST_HOST = '127.0.0.1'
TEST_PORT = (os.getpid() % 31000) + 1024
TEST_URI = "%s:%s" % (TEST_HOST, TEST_PORT)


if sys.version_info >= (3, 0):
    linesep = os.linesep.encode()
else:
    linesep = os.linesep

def start_manager():
    http_handler = HttpHandler(MockConfig(bind=TEST_URI))
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


def test_stdio():
    m, s = init()

    emitted = []
    def cb(ch, data):
        emitted.append(data)

    responses = []
    def cb2(ch, result, error):
        responses.append((result, error))

    if sys.platform == 'win32':
        config =  ProcessConfig("echo",  "cmd.exe",
                args=["/c", "proc_stdin_stdout.py"],
                redirect_output=["stdout"], redirect_input=True)

    else:
        config = ProcessConfig("echo", "./proc_stdin_stdout.py",
            cwd=os.path.dirname(__file__), redirect_output=["stdout"],
            redirect_input=True)

    # load the process
    m.load(config)
    time.sleep(0.2)

    # start a channel
    p = s.get_process(1)
    channel = p.socket()
    channel.start()

    # subscribe to remote events
    channel.start_read(cb)

    # write to STDIN
    channel.write(b"ECHO" + linesep, cb2)

    def stop(handle):
        channel.stop_read()
        channel.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.3, 0.0)
    m.run()

    assert len(emitted) == 1
    assert emitted == [b'ECHO\n\n']
    assert responses == [(b"OK", None)]

def test_mode_readable():
    m, s = init()

    if sys.platform == 'win32':
        config =  ProcessConfig("echo",  "cmd.exe",
                args=["/c", "proc_stdin_stdout.py"],
                redirect_output=["stdout"], redirect_input=True)

    else:
        config = ProcessConfig("echo", "./proc_stdin_stdout.py",
            cwd=os.path.dirname(__file__), redirect_output=["stdout"],
            redirect_input=True)

    # load the process
    m.load(config)
    time.sleep(0.2)

    # start a channel
    p1 = s.get_process(1)
    channel = p1.socket(mode=pyuv.UV_READABLE)
    channel.start()

    # subscribe to remote events
    channel.start_read(lambda ch, d: None)

    with pytest.raises(IOError):
        channel.write(b"ECHO" + linesep)

    def stop(handle):
        channel.stop_read()
        channel.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.3, 0.0)
    m.run()

def test_mode_writable():
    m, s = init()

    responses = []
    def cb2(ch, result, error):
        responses.append((result, error))

    if sys.platform == 'win32':
        config =  ProcessConfig("echo",  "cmd.exe",
                args=["/c", "proc_stdin_stdout.py"],
                redirect_output=["stdout"], redirect_input=True)

    else:
        config = ProcessConfig("echo", "./proc_stdin_stdout.py",
            cwd=os.path.dirname(__file__), redirect_output=["stdout"],
            redirect_input=True)

    # load the process
    m.load(config)
    time.sleep(0.2)

    # start a channel
    p1 = s.get_process(1)
    channel = p1.socket(mode=pyuv.UV_WRITABLE)
    channel.start()

    # subscribe to remote events
    with pytest.raises(IOError):
        channel.start_read(lambda ch, d: None)


    channel.write(b"ECHO" + linesep, cb2)

    def stop(handle):
        channel.stop_read()
        channel.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.3, 0.0)
    m.run()

    assert responses == [(b"OK", None)]

def test_custom_stream():
    m, s = init()

    emitted = []
    def cb(ch, data):
        emitted.append(data)

    responses = []
    def cb2(ch, result, error):
        responses.append((result, error))

    if sys.platform == 'win32':
        config =  ProcessConfig("echo",  "cmd.exe",
                args=["/c", "proc_custom_stream.py"],
                custom_streams=["ctrl"])
    else:
        config = ProcessConfig("echo", "./proc_custom_stream.py",
            cwd=os.path.dirname(__file__), custom_streams=["ctrl"])

    m.load(config)

    # start a channel
    p = s.get_process(1)
    channel = p.socket(stream="ctrl")
    channel.start()

    # subscribe to remote events
    channel.start_read(cb)

    # write to STDIN
    channel.write(b"ECHO" + linesep, cb2)

    def stop(handle):
        channel.stop_read()
        channel.close()
        m.stop()


    t = pyuv.Timer(m.loop)
    t.start(stop, 0.4, 0.0)
    m.loop.run()

    assert len(emitted) == 1
    assert emitted == [b'ECHO\n']
    assert responses == [(b"OK", None)]

if __name__ == "__main__":
    test_custom_stream()
