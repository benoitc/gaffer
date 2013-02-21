# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import json
import os
import time

import pyuv

from gaffer import __version__
from gaffer.http_handler import HttpEndpoint, HttpHandler
from gaffer.httpclient import (Server, Job, Process,
        GafferNotFound, GafferConflict)
from gaffer.manager import Manager
from gaffer.process import ProcessConfig
from gaffer.websocket import WebSocket

from test_manager import dummy_cmd


TEST_HOST = '127.0.0.1'
TEST_PORT = (os.getpid() % 31000) + 1024
TEST_URL = "ws://%s:%s/channel/websocket" % (TEST_HOST, str(TEST_PORT))


def start_manager():
    http_endpoint = HttpEndpoint(uri="%s:%s" % (TEST_HOST, TEST_PORT))
    http_handler = HttpHandler(endpoints=[http_endpoint])
    m = Manager()
    m.start(apps=[http_handler])
    time.sleep(0.5)
    return m

def get_server(loop):
    return Server("http://%s:%s" % (TEST_HOST, TEST_PORT), loop=loop)

def test_basic():
    """ test using a basic websocket client

    to make sure we don't close the websocket client before fetching the event
    we are closing the connection and server after 0.8s.
    """
    opened = [] # used to collect open connection success
    messages = [] # collect events
    success = [] # collect subscription success

    # define a basic websocket client handler to collect message
    class TestClient(WebSocket):

        def on_open(self):
            opened.append(True)

        def on_message(self, raw):
            msg = json.loads(raw)

            # each gaffer message should contain an event property
            assert "event" in msg
            event = msg['event']
            if event == "gaffer:subscription_success":
                success.append(True)
            elif event == "gaffer:event":
                # if message type is an event then it should contain a data
                # property
                assert "data" in msg
                data = msg['data']

                # for `EVENTS` topic we are waiting norrmal events and data
                # should at least contain the `event` and `name` properties
                assert "event" in data
                assert "name" in data

                # we only collect `(eventtype, joblabel)` tuples
                messages.append((data['event'], data['name']))


    m = start_manager()
    ws = TestClient(m.loop, TEST_URL)
    ws.start()
    s = get_server(m.loop)
    assert s.version == __version__


    submsg = json.dumps({"event": "SUB", "data": {"topic": "EVENTS"}})
    ws.write_message(submsg)
    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=4)


    def do_events(h):
        m.load(config)
        print("scale")
        m.scale("dummy", 1)
        m.unload("dummy")

    def stop(h):
        h.close()
        ws.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(do_events, 0.4, 0.0)
    t1 = pyuv.Timer(m.loop)
    t1.start(stop, 0.8, 0.0)

    m.run()

    assert opened == [True]
    assert success == [True]
    assert ('load', 'default.dummy') in messages
    assert ('start', 'default.dummy') in messages
    assert ('update', 'default.dummy') in messages
    assert ('stop', 'default.dummy') in messages
    assert ('unload', 'default.dummy') in messages


def test_basic_socket():
    m = start_manager()
    s = get_server(m.loop)

    # get a gaffer socket
    socket = s.socket()
    socket.start()

    assert s.version == __version__

    messages =[]
    def cb(event, data):
        messages.append((event, data['name']))

    # bind to all events
    socket.subscribe('EVENTS')
    socket['EVENTS'].bind_all(cb)

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("dummy", cmd, args=args, cwd=wdir, numprocesses=4)

    def do_events(h):
        m.load(config)
        m.scale("dummy", 1)
        m.unload("dummy")

    def stop(h):
        h.close()
        socket.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(do_events, 0.4, 0.0)
    t1 = pyuv.Timer(m.loop)
    t1.start(stop, 0.8, 0.0)

    m.run()

    assert ('load', 'default.dummy') in messages
    assert ('start', 'default.dummy') in messages
    assert ('update', 'default.dummy') in messages
    assert ('stop', 'default.dummy') in messages
    assert ('unload', 'default.dummy') in messages


def test_stats():
    m = start_manager()
    s = get_server(m.loop)

    # get a gaffer socket
    socket = s.socket()
    socket.start()

    assert s.version == __version__

    monitored = []
    def cb(event, info):
        print(event)
        monitored.append(info)

    testfile, cmd, args, wdir = dummy_cmd()
    config = ProcessConfig("a", cmd, args=args, cwd=wdir)

    # bind to all events
    socket.subscribe("STATS:default.a")
    socket["STATS:default.a"].bind_all(cb)


    m.load(config)
    os_pid = m.running[1].os_pid


    def stop(handle):
        socket.close()
        m.stop()

    t = pyuv.Timer(m.loop)
    t.start(stop, 0.3, 0.0)

    m.run()

    assert len(monitored) >= 1
    res = monitored[0]
    assert "cpu" in res
    assert res["os_pid"] == os_pid
