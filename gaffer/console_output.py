# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
module to return all streams from the managed processes to the
console. This application is subscribing to the manager to know when a
process is created or killed and display the information. When an OS process
is spawned it then subscribe to its streams if any are redirected and
print the output on the console. This module is used by
:doc:`gafferp <commands>` .


.. note::

    if colorize is set to true, each templates will have a different
    colour
"""

import copy
from datetime import datetime
import sys

from colorama import  Fore, Style, init
init()


GAFFER_COLORS = ['cyan', 'yellow', 'green', 'magenta', 'red', 'blue',
'intense_cyan', 'intense_yellow', 'intense_green', 'intense_magenta',
'intense_red', 'intense_blue']


class Color(object):
    """ wrapper around colorama to ease the output creation. Don't use
    it directly, instead, use the ``colored(name_of_color, lines)`` to
    return the colored ouput.

    Colors are: cyan, yellow, green, magenta, red, blue,
    intense_cyan, intense_yellow, intense_green, intense_magenta,
    intense_red, intense_blue.

    lines can be a list or a string.
    """

    def __init__(self):
        # intialize colors code
        colors = {}
        for color in GAFFER_COLORS:
            c = color.upper()
            if color.startswith('intense_'):
                code = getattr(Fore, c.split('_')[1])
                colors[color] = code + Style.BRIGHT
            else:
                code = getattr(Fore, c)
                colors[color] = code
        self.colors = colors

    def output(self, color_name, lines):
        if not isinstance(lines, list):
            lines = [lines]

        lines.insert(0, self.colors[color_name])
        lines.append(Fore.RESET)
        return ''.join(lines)

_color = Color()
colored = _color.output


class ConsoleOutput(object):
    """ The application that need to be added to the gaffer manager """

    DEFAULT_ACTIONS = ['spawn', 'reap', 'exit', 'stop_pid']

    def __init__(self, colorize=True, output_streams=True, actions=None):
        self.output_streams = output_streams
        self.colorize = colorize

        self.subscribed = actions or self.DEFAULT_ACTIONS

        self._balance = copy.copy(GAFFER_COLORS)
        self._process_colors = {}

    def start(self, loop, manager):
        self.loop = loop
        self.manager = manager

        for action in self.subscribed:
            self.manager.subscribe(action, self._on_process)

    def stop(self):
        for action in self.subscribed:
            self.manager.unsubscribe(".", self._on_process)

    def restart(self, start):
        self.stop()
        for action in self.subscribed:
            self.manager.subscribe(action, self._on_process)

    def _on_process(self, event, msg):
        if not 'os_pid' in msg:
            name = msg['name']
            line = self._print(name, '%s %s' % (event, name))
            return

        os_pid = msg['os_pid']
        name = msg['name']

        if event == "spawn":
            p = self.manager.get_process(msg['pid'])
            line = self._print(name, 'spawn process with pid %s' % os_pid)

            if p.redirect_output and self.output_streams:
                for output in p.redirect_output:
                    p.monitor_io(output, self._on_output)
        else:
            line = self._print(name,
                    '%s process with pid %s' % (event, os_pid))
        self._write(name, line)

    def _on_output(self, event, msg):
        data =  msg['data'].decode('utf-8')
        lines = []
        for line in data.splitlines():
            line = line.strip()
            if line:
                lines.append(self._print(msg['name'], line))
        self._write(msg['name'], lines)

    def _write(self, name, lines):
        if self.colorize:
            sys.stdout.write(colored(self._get_process_color(name), lines))
        else:
            sys.stdout.write(''.joint(lines))
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
