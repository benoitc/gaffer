# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy

from ...console_output import colored, GAFFER_COLORS
from ...lookupd.client import LookupServer
from .base import Command

import pyuv

class LookupJob(Command):
    """
    usage: gaffer lookup:job <job> (-L ADDR|--lookupd-address=ADDR)...

      -h, --help
      -L ADDR --lookupd-address=ADDR  lookupd HTTP address
    """

    name = "lookup:job"
    short_descr = "find a job on different lookupd servers"


    def run(self, config, args):
        lookupd_addresses = set(args['--lookupd-address'])
        job_name = args['<job>']

        sources = []
        loop = pyuv.Loop.default_loop()
        for addr in lookupd_addresses:
            s = LookupServer(addr, loop=loop, **config.client_options)
            resp = s.find_job(job_name)
            new_sources = resp.get('sources', [])
            if not new_sources:
                continue
            sources.extend(new_sources)

        loop.run()
        if not sources:
            print("no job found")
            return

        balance = copy.copy(GAFFER_COLORS)
        for source in sources:
            name = source['node_info']['name']
            version = source['node_info']['version']

            pids = [str(pid) for pid in source['pids']]
            lines = ["=== %s (Protocol: %s)" % (name, version),
                    "Origin: %s" % source['node_info']['origin'],
                    "Pids: %s" % (",".join(pids)), ""]
            color, balance = self.get_color(balance)
            print(colored(color, "\n".join(lines)))

    def get_color(self, balance):
        code = balance.pop(0)
        balance.append(code)
        return code, balance
