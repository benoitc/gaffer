# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy

from ...console_output import colored, GAFFER_COLORS
from ...httpclient import GafferNotFound
from ...lookupd.client import LookupServer
from .base import Command

import pyuv

class LookupSessions(Command):
    """
    usage: gaffer lookup:nodes (-L ADDR|--lookupd-address=ADDR)...

      -h, --help
      -L ADDR --lookupd-address=ADDR  lookupd HTTP address
    """

    name = "lookup:nodes"
    short_descr = "list all gaffer nodes"

    def run(self, config, args):
        lookupd_addresses = set(args['--lookupd-address'])

        loop = pyuv.Loop.default_loop()
        all_nodes = []
        for addr in lookupd_addresses:
            s = LookupServer(addr, loop=loop)
            resp = s.nodes()
            for node in resp['nodes']:
                if node not in all_nodes:
                    all_nodes.append(node)

        print("%s node(s) found\n" % len(all_nodes))

        balance = copy.copy(GAFFER_COLORS)
        for node in all_nodes:
            uri = "http://%s:%s" % (node['broadcast_address'], node['port'])
            line = "%s - hostname: %s, protocol: %s" % (uri, node['hostname'],
                    node['version'])

            color, balance = self.get_color(balance)
            print(colored(color, line))

    def get_color(self, balance):
        code = balance.pop(0)
        balance.append(code)
        return code, balance

