# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import sys

import pyuv

from .base import Command
from ...httpclient import GafferNotFound

from .send import SigHandler

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

        self.socket = p.socket(mode=pyuv.UV_READABLE, stream=stream)
        self.socket.start()
        self.socket.start_read(self._on_read)

        self.sig_handler = SigHandler(self)
        self.sig_handler.start(server.loop)

        # then listen
        server.loop.run()

    def stop(self):
        self.socket.close()


    def _on_read(self, channel, data):
        sys.stdout.write(data.decode('utf-8'))
        sys.stdout.flush()
