# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy

from .base import Command
from ...console_output import colored, GAFFER_COLORS

class Ps(Command):
    """
    usage: gaffer ps [--app APP]


      -h, --help
      --app APP  application name
    """

    name = "ps"
    short_descr = "list your processes informations"

    def run(self, config, args):
        balance = copy.copy(GAFFER_COLORS)
        appname = self.default_appname(config, args)
        server = config.get("server")

        if not appname in server.sessions():
            raise RuntimeError("%r not loaded" % appname)

        for pname in server.jobs(appname):
            lines = []
            try:
                job = server.get_job(pname)
            except:
                # we just ignore
                continue

            if not job.active:
                continue

            appname, name = self.parse_name(pname)

            color, balance = self.get_color(balance)
            stats = job.stats()

            # recreate cmd line
            args = job.config.get('args') or []
            cmd = " ".join([job.config['cmd']] + args)
            lines = ["=== %s: `%s`" % (name, cmd),
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
