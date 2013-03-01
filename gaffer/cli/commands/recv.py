# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import copy
from datetime import datetime
import sys

from .base import Command
from ...console_output import colored, GAFFER_COLORS
from ...httpclient import GafferNotFound

class Recv(Command):

    """
    usage: gaffer recv <pid> [<stream>] [--app APP]

      --app APP     name of the procfile application.
    """

    name = "recv"
    short_descr = "read a stream from a pid"

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

        socket = server.socket()
        socket.start()

        # subscribe to the event
        if not args['<stream>']:
            event = "STREAM:%s" % args['<pid>']
        else:
            event = "STREAM:%s.%s" % (args['<pid>'], args['<stream>'])

        channel = socket.subscribe(event)
        channel.bind_all(self._on_event)

        while True:
            try:
                if not server.loop.run_once():
                    break
            except KeyboardInterrupt:
                break

    def _on_event(self, event, msg):
        sys.stdout.write(msg['data'])
        sys.stdout.flush()
