# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import os
import json
import time

# patch tornado IOLoop
from gaffer.tornado_pyuv import IOLoop, install
install()

import pyuv
from tornado.web import Application, RequestHandler
from tornado.httpserver import HTTPServer
from tornado import netutil
from gaffer.manager import Manager
from gaffer.webhooks import WebHooks

from test_manager import dummy_cmd

TEST_HOST = '127.0.0.1'
TEST_PORT = (os.getpid() % 31000) + 1024

class TestHandler(RequestHandler):
    def post(self, *args):
        obj = json.loads(self.request.body.decode('utf-8'))
        received = self.settings.get('received')
        received.append((obj['event'], obj['name']))
        self.write("ok")

def get_server(loop, received):
    io_loop = IOLoop(_loop=loop)

    test_handlers = [
            (r'/([^/]+)', TestHandler)
    ]

    app = Application(test_handlers, received=received)
    server = HTTPServer(app, io_loop=io_loop)

    [sock] = netutil.bind_sockets(TEST_PORT, address=TEST_HOST)
    server.add_socket(sock)
    return server

def make_uri(path):
    return "http://%s:%s%s" % (TEST_HOST, TEST_PORT, path)

def create_hooks(events):
    test_hooks = []
    for ev in events:
        test_hooks.append((ev, make_uri('/%s' % ev)))
    return test_hooks

def test_manager_hooks():
    hooks = create_hooks(['create', 'start', 'update', 'stop',
        'delete', 'proc.dummy.start', 'proc.dummy.spawn',
        'proc.dummy.stop', 'proc.dummy.exit'])
    emitted = []
    loop = pyuv.Loop.default_loop()
    s = get_server(loop, emitted)
    s.start()
    m = Manager(loop=loop)
    m.start(apps=[WebHooks(hooks)])
    testfile, cmd, args, wdir = dummy_cmd()
    m.add_process("dummy", cmd, args=args, cwd=wdir, numprocesses=4)
    m.ttin("dummy", 1)
    m.remove_process("dummy")

    def on_stop(manager):
        s.stop()

    def do_stop(handle):
        handle.close()
        m.stop(on_stop)


    t = pyuv.Timer(loop)
    t.start(do_stop, 0.2, 0.0)

    m.run()
    assert ('create', 'dummy') in emitted
    assert ('start', 'dummy') in emitted
    assert ('update', 'dummy') in emitted
    assert ('stop', 'dummy') in emitted
    assert ('delete', 'dummy') in emitted
    assert ('proc.dummy.start', 'dummy') in emitted
    assert ('proc.dummy.spawn', 'dummy') in emitted
    assert ('proc.dummy.stop', 'dummy') in emitted
    assert ('proc.dummy.exit', 'dummy') in emitted
