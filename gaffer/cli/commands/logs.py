# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import copy
from datetime import datetime
import sys

import pyuv

from .base import Command
from ...console_output import colored, GAFFER_COLORS

class Logs(Command):

    """
    usage: gaffer logs  [--ps JOB] [--app APP] [--no-color]

      --ps JOB      job name
      --app APP     name of the procfile application.
      --no-color    return with colors
    """

    name = "logs"
    short_descr = "Get logs for an app"

    def run(self, config, args):
        appname = self.default_appname(config, args)
        server  = config.get("server")

        self.nocolor = args["--no-color"]
        self._balance = copy.copy(GAFFER_COLORS)
        self._process_colors = {}

        socket = server.socket()
        socket.start()

        socket.subscribe('EVENTS')

        if args['--ps']:
            pattern = "job.%s.%s." % (appname, args['--ps'])
        else:
            pattern = "job.%s." % appname

        socket['EVENTS'].bind(pattern, self._on_event)

        while True:
            try:
                if not server.loop.run(pyuv.UV_RUN_ONCE):
                    break
            except KeyboardInterrupt:
                break

    def _on_event(self, event, msg):
        name = msg['name']
        if not 'pid' in msg:
            line = self._print(name, '%s %s' % (event, name))
        else:
            line = self._print(name, '%s process with pid %s' % (event,
                msg['pid']))

        self._write(name, line)

    def _write(self, name, lines):
        if not self.nocolor:
            sys.stdout.write(colored(self._get_process_color(name), lines))
        else:
            if not isinstance(lines, list):
                lines = [lines]

            sys.stdout.write(''.join(lines))
        sys.stdout.flush()

    def _print(self, name, line):
        now = datetime.now().strftime('%H:%M:%S')
        prefix = '{time} {name} | '.format(time=now, name=name)
        return ''.join([prefix, line, '\n'])

    def _set_process_color(self, name):
        code = self._balance.pop(0)
        self._process_colors[name] = code
        self._balance.append(code)

    def _get_process_color(self, name):
        if name not in self._process_colors:
            self._set_process_color(name)
        return self._process_colors[name]
