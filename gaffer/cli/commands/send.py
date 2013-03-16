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
    usage: gaffer send [--app APP] [-s STREAM|--stream STREAM] <pid> <data>...

      <data>  file inpur or data input

      --app APP                  name of the procfile application or session.
      -s STREAM --stream STREAM  name of the stream where to send the data
    """

    name = "send"
    short_descr = "send some data to a pid"

    def run(self, config, args):
        server  = config.get("server")

        stream = args["--stream"]
        if stream == "stdin":
            stream = None

        if "." in args['<pid>']:
            pid, stream = args['<pid>'].split(".", 1)
        else:
            pid = args['<pid>']


        if not pid.isdigit():
            raise RuntimeError("invalid <pid> value")

        try:
            p = server.get_process(int(pid))
        except GafferNotFound:
            print("process %r not found" % pid)
            return

        # make sure we can send some data before sending it.
        if not stream:
            if not p.redirect_input:
                raise RuntimeError("can't write on this process, (no stdin)")
        elif stream not in p.custom_streams:
            raise RuntimeError("stream %r not found" % stream)

        # make pid & stream available in the instance
        self.pid = int(pid)
        self.stream = stream

        self.socket = p.socket(mode=pyuv.UV_WRITABLE, stream=stream)
        self.socket.start()

        data = " ".join(args["<data>"])
        self.args = args
        self.tty = None
        self.should_close = False

        if data.strip() == "-":
            self.tty = pyuv.TTY(server.loop, sys.stdin.fileno(), True)
            self.tty.start_read(self._on_tty_read)
            self.sig_handler = SigHandler(self)
            self.sig_handler.start(server.loop)
        else:
            data = data.strip()
            if not data.endswith('\n'):
                data = data + os.linesep

            self.socket.write(data, self._on_done)

        server.loop.run()

    def _on_done(self, channel, result, error):
        if error is not None:
            print("Error (%s): %s" % (error['errno'], error['reason']))
        self.stop()

    def _on_tty_done(self, channel, result, error):
        if error is not None:
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
            self.socket.write(data, self._on_tty_done)

    def stop(self):
        if self.tty is not None and not self.tty.closed:
            self.tty.close()
            pyuv.TTY.reset_mode()
        self.socket.close()
