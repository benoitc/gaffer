# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import sys

from .base import Command
from ...httpclient import Server

class UnLoad(Command):
    """\
        Unload a Procfile application to gafferd
        ========================================

        This command allows you to unload your Procfile application
        in gafferd.

        Command line
        ------------

            $ gaffer unload [name] [url]

        Arguments
        +++++++++

        *name* is the name of the group of process recoreded in gafferd.
        By default it will be the name of your project folder.You can use
        ``.`` to specify the current folder.

        *uri*  is the url to connect to a gaffer node. By default
        'http://127.0.0.1:5000'

        Options
        +++++++

        **--endpoint**

            Gaffer node URL to connect.


    """

    name = "unload"

    def run(self, procfile, pargs):
        args = pargs.args

        # get args
        uri = None
        if len(args) == 2:
            group = args[0]
            uri = args[1]
        elif len(args) == 1:
            group = args[0]
        else:
            group = "."

        if pargs.endpoint:
            uri = pargs.endpoint

        if not uri:
            uri = "http://127.0.0.1:5000"

        # get the default groupname
        if group == ".":
            group = procfile.get_groupname()

        # create a server instance
        s = Server(uri)

        groups = s.groups()
        if group not in groups:
            raise RuntimeError("%r not found" % group)

        # remove the group
        s.remove_group(group)
        print("%r unloaded" % group)
