# -*- coding: utf-8 -*-

import sys

import pyuv
from tornado import ioloop

from gaffer.httpclient import WebSocket


class Input(object):

    def __init__(self, chat):
        self.chat = chat
        self.tty = pyuv.TTY(chat.loop, True)
        self.tty.start_read(self.on_input)
        self.tty.unref()

    def stop(self):
        self.tty.stop()

    def on_input(self, handle, data, err):
        self.chat.write_message(data)


class ChatReader(WebSocket):

    def on_open(self):
        print("connection openned")
        self.console = Input(self)

    def on_message(self, data):
        print("received %s" % data)

    def on_close(self):
        print('closed')
        self.console.stop()

loop = pyuv.Loop.default_loop()

ws = ChatReader(loop, "ws://localhost:8080/chat/websocket")
ws.start()

try:
    while True:
        try:
            if not loop.run(pyuv.UV_RUN_ONCE):
                break
        except KeyboardInterrupt:
            break

finally:
    ws.close()
