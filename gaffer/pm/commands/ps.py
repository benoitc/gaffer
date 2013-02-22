# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy
import os

from .base import Command
from ...httpclient import Server
from ...console_output import colored, GAFFER_COLORS

class Ps(Command):
    """
    usage: gaffer ps [<appname>]
    """

    name = "ps"
    short_descr = "list your processes informations"

    def run(self, procfile, server, args):
        balance = copy.copy(GAFFER_COLORS)

        appname = args['<appname>']
        if not appname or appname == ".":
            # get the default groupname
            appname = procfile.get_appname()

        for name, cmd_str in procfile.processes():
            try:
                job = server.get_job("%s.%s" % (appname, name))
            except:
                # we just ignore
                continue

            color, balance = self.get_color(balance)
            stats = job.stats()

            lines = ["=== %s: `%s`" % (name, cmd_str),
                     "Total CPU: %.2f Total MEM: %.2f" % (stats['cpu'],
                         stats['mem']),
                     ""]

            for info in stats['stats']:
                lines.append("%s.%s: up for %s" % (name, info['pid'],
                    info['ctime']))

            print(colored(color, '\n'.join(lines)))

    def get_color(self, balance):
        code = balance.pop(0)
        balance.append(code)
        return code, balance
