# -*- coding: utf-8 -

import os
import time

import pyuv
import tornado.web
from tornado.httpserver import HTTPServer
from tornado import netutil
from gaffer import sockjs
from gaffer.tornado_pyuv import IOLoop
from gaffer.httpclient.websocket import WebSocket

TEST_PORT = (os.getpid() % 31000) + 1024
TEST_HOST = "127.0.0.1"
TEST_URL = "ws://%s:%s/echo/websocket" % (TEST_HOST, str(TEST_PORT))

h_opened = []
h_messages = []

c_opened = []
c_messages = []


class HelloConnection(sockjs.SockJSConnection):

    def on_open(self, info):
        h_opened.append(True)

    def on_message(self, message):
        h_messages.append(message)
        self.send(message)


class HelloClient(WebSocket):

    def on_open(self):
        c_opened.append(True)

    def on_message(self, message):
        c_messages.append(message)


def test_basic():
    loop = pyuv.Loop.default_loop()
    io_loop = IOLoop(_loop=loop)

    HelloRouter = sockjs.SockJSRouter(HelloConnection, '/echo',
            io_loop=io_loop)

    ws = HelloClient(loop, TEST_URL)
    app = tornado.web.Application(HelloRouter.urls)
    server = HTTPServer(app, io_loop=io_loop)

    [sock] = netutil.bind_sockets(TEST_PORT, address=TEST_HOST)
    server.add_socket(sock)

    server.start()
    ws.start()

    t = pyuv.Timer(loop)
    t1 = pyuv.Timer(loop)

    start = time.time()
    def do_stop(handle):
        handle.close()
        server.stop()
        ws.close()
        io_loop.close()

    def init(handle):
        handle.close()
        ws.write_message("hello")
        t1.start(do_stop, 0.2, 0.0)

    t.start(init, 0.2, 0.0)
    loop.run()

    assert h_opened == [True]
    assert c_opened == [True]
    assert h_messages == ["hello"]
    assert c_messages == ["hello"]

if __name__ == "__main__":
    import logging
    logging.getLogger().setLevel(logging.DEBUG)
    test_basic()
