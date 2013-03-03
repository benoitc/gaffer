# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import copy
from datetime import datetime
import sys

import pyuv

from .base import Command
from ...console_output import colored, GAFFER_COLORS
from ...httpclient import GafferNotFound


class Recv(Command):

    """
    usage: gaffer recv <pid> [<stream>] [--app APP]

      <pid>     process ID or can be in the form of <pid.stream>
      <stream>  name of the stream to receive from

      --app APP     name of the procfile application.
    """

    name = "recv"
    short_descr = "read a stream from a pid"

    def run(self, config, args):
        appname = self.default_appname(config, args)
        server  = config.get("server")

        # get the stream and pid from the command line
        stream = args["<stream>"]
        if "." in args['<pid>']:
            pid, stream = args['<pid>'].split(".", 1)
        else:
            pid = args['<pid>']


        if not pid.isdigit():
            raise RuntimeError("invalid <pid> value")

        # open the process
        try:
            p = server.get_process(int(pid))
        except GafferNotFound:
            print("process %r not found" % pid)
            return

        # test if the stream exist before sending anything to the server
        if stream is not None:
            if (stream not in p.redirect_output and
                    stream not in p.custom_streams):
                raise RuntimeError("can't read on %r" % stream)

        socket = p.socket(mode=pyuv.UV_READABLE, stream=stream)
        socket.start()
        socket.start_read(self._on_read)

        # then listen
        while True:
            try:
                if not server.loop.run_once():
                    break
            except KeyboardInterrupt:
                break

    def _on_read(self, channel, data):
        sys.stdout.write(data.decode('utf-8'))
        sys.stdout.flush()
