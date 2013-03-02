# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import os
import sys

import pyuv

from .base import Command
from ...httpclient import GafferNotFound
from ...sig_handler import BaseSigHandler


class SigHandler(BaseSigHandler):

    def __init__(self, command):
        super(SigHandler, self).__init__()
        self.command = command

    def handle_quit(self, h, *args):
        self.stop()
        self.command.stop()

    def handle_reload(self, h, *args):
        return

class Send(Command):

    """
    usage: gaffer send [--app APP] <pid> <data>

      <data>  file inpur or data input

      --app APP     name of the procfile application.
    """

    name = "send"
    short_descr = "send some data to a pid"

    def run(self, config, args):
        appname = self.default_appname(config, args)
        server  = config.get("server")

        if not args['<pid>'].isdigit():
            raise RuntimeError("invalid <pid> value")

        try:
            p = server.get_process(int(args['<pid>']))
        except GafferNotFound:
            print("process %r not found" % args['<pid>'])
            return


        self.socket = server.socket()
        self.socket.start()
        data = args["<data>"]
        self.args = args
        self.tty = None
        self.should_close = False

        if data.strip() == "-":
            self.tty = pyuv.TTY(server.loop, sys.stdin.fileno())
            self.tty.start_read(self._on_tty_read)
            self.sig_handler = SigHandler(self)
            self.sig_handler.start(server.loop)
        else:
            data = data.strip()
            if not data.endswith('\n'):
                data = data + os.linesep
            cmd = self.socket.send_command("send", int(args['<pid>']), data)
            cmd.add_done_callback(self._on_done)

        server.loop.run()

    def _on_done(self, cmd):
        if cmd.error():
            error = cmd.error()
            print("Error (%s): %s" % (error['errno'], error['reason']))
        self.stop()

    def _on_tty_done(self, cmd):
        if cmd.error():
            error = cmd.error()
            print("Error (%s): %s" % (error['errno'], error['reason']))
            self.stop()
        elif self.should_close:
            self.stop()

    def _on_tty_read(self, handle, data, error):
        if not data:
            self.should_close = True
            return

        data = data.strip()
        if data == b".":
            self.stop()
        else:
            data = data.decode('utf-8') + os.linesep
            cmd = self.socket.send_command("send", int(self.args['<pid>']),
                    data)
            cmd.add_done_callback(self._on_tty_done)

    def stop(self):
        if self.tty is not None and not self.tty.closed:
            self.tty.close()
            pyuv.TTY.reset_mode()
        self.socket.close()
