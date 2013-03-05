# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from datetime import datetime
import copy
import sys

from ...console_output import colored, GAFFER_COLORS
from ...lookupd.client import LookupServer
from ...sig_handler import BaseSigHandler
from .base import Command

import pyuv

class SigHandler(BaseSigHandler):

    def __init__(self, channel):
        super(SigHandler, self).__init__()
        self.channel = channel

    def handle_quit(self, h, *args):
        self.stop()
        self.channel.close()

    def handle_reload(self, h, *args):
        return

class Lookup(Command):
    """
    usage: gaffer lookup (-L ADDR|--lookupd-address=ADDR) [--no-color]


      -h, --help
      --no-color  return with colors
      -L ADDR --lookupd-address=ADDR  lookupd HTTP address
    """

    name = "lookup"
    short_descr = "watch lookup events on one lookupd server"


    def run(self, config, args):
        self.nocolor = args["--no-color"]
        self._balance = copy.copy(GAFFER_COLORS)
        self._event_colors = {}

        loop = pyuv.Loop.default_loop()

        # connect to the lookupd server channel
        s = LookupServer(args['--lookupd-address'], loop=loop,
                **config.client_options)
        channel = self.channel = s.lookup()

        # initialize the signal handler
        self._sig_handler = SigHandler(channel)
        self._sig_handler.start(loop)

        # bind to all events

        channel.bind_all(self._on_event)
        channel.start()

        loop.run()

    def _on_event(self, event, msg):
        if event == "add_node":
            line = self._print(event, "add node")
        elif event == "identify":
            line = self._print(event, "%s: %s" % (msg['name'],
                msg['origin']))
        elif event == "remove_node":
            line = self._print(event, "%s: node %s" % (msg['name'],
                msg['origin']))
        else:
            uri = msg['node']['origin']
            if event == "add_job":
                line = "load %s in %s" % (msg["job_name"], uri)
            elif event == "remove_job":
                line = "unload %s in %s" % (msg["job_name"], uri)
            elif event == "add_process":
                line = "%s: process id %s spanwned on %s" % (msg["job_name"],
                        msg["pid"], uri)
            elif event == "remove_process":
                line = "%s: process %s exited on %s" % (msg["job_name"],
                        msg["pid"], uri)

            line = self._print(event, line)

        self._write(event, line)

    def _write(self, event, lines):
        if not isinstance(lines, list):
            lines = [lines]

        if not self.nocolor:
            sys.stdout.write(colored(self._get_event_color(event), lines))
        else:
            sys.stdout.write(''.join(lines))
        sys.stdout.flush()

    def _print(self, event, line):
        now = datetime.now().strftime('%H:%M:%S')
        prefix = '{time} {event} | '.format(time=now, event=event)
        return ''.join([prefix, line, '\n'])

    def _set_event_color(self, event):
        code = self._balance.pop(0)
        self._event_colors[event] = code
        self._balance.append(code)

    def _get_event_color(self, event):
        if event not in self._event_colors:
            self._set_event_color(event)
        return self._event_colors[event]
