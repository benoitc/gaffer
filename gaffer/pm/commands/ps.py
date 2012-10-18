# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy
import os

from .base import Command
from ...httpclient import Server
from ...console_output import colored, GAFFER_COLORS

class Ps(Command):
    """\
        List your process informations
        ------------------------------

        Ps allows you to retrieve some process informations


        .. image:: ../_static/gaffer_ps.png

        Command line
        ------------

        ::

            $ gaffer ps [group]

        Args
        ++++

        *group*  is the name of the group of process recoreded in gafferd.
        By default it will be the name of your project folder.You can use
        ``.`` to specify the current folder.

        *name* is the name of one process

    """

    name = "ps"

    def run(self, procfile, pargs):
        args = pargs.args
        uri = pargs.endpoint or "http://127.0.0.1:5000"
        balance = copy.copy(GAFFER_COLORS)
        s = Server(uri)


        group = "."
        if len(args) == 1:
            group = args[0]

        # get the default groupname
        if group == ".":
            group = procfile.get_groupname()

        for name, cmd_str in procfile.processes():
            pname = "%s:%s" % (group, name)

            try:
                p = s.get_process(pname)
            except:
                # we just ignore
                continue


            color, balance = self.get_color(balance)
            stats = p.stats()

            lines = ["=== %s: `%s`" % (name, cmd_str),
                     "Total CPU: %2f Total MEM: %.2f" % (stats['cpu'],
                         stats['mem']),
                     ""]

            for info in stats['stats']:
                lines.append("%s.%s: up for %s" % (name, info['id'],
                    info['ctime']))

            print(colored(color, '\n'.join(lines)))


    def get_color(self, balance):
        code = balance.pop(0)
        balance.append(code)
        return code, balance
