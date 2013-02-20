# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os

from .base import Command
from ...httpclient import Server
from ...process import ProcessConfig


class Load(Command):
    """\
        Load a Procfile application to gafferd
        ======================================

        This command allows you to load your Procfile application
        in gafferd.

        Command line
        ------------

            $ gaffer load [name] [url]

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

    name = "load"

    def run(self, procfile, pargs):
        args = pargs.args

        # get args
        uri = None
        if len(args) == 2:
            appname = args[0]
            uri = args[1]
        elif len(args) == 1:
            appname = args[0]
        else:
            appname = "."

        if pargs.endpoint:
            uri = pargs.endpoint

        if not uri:
            uri = "http://127.0.0.1:5000"

        # get the default appname
        if appname == ".":
            appname = procfile.get_appname()

        # create a server instance
        s = Server(uri)

        # finally manage group conflicts
        appname = self.find_appname(appname, s)

        # parse the concurrency settings
        concurrency = self.parse_concurrency(pargs)

        # finally send the processes
        for name, cmd_str in procfile.processes():
            cmd, args = procfile.parse_cmd(cmd_str)
            params = dict(args=args, env=procfile.env,
                    numprocesses=concurrency.get(name, 1),
                    redirect_output=['out', 'err'],
                    cwd=os.path.abspath(procfile.root))

            config = ProcessConfig(name, cmd, **params)
            s.add_template(config, sessionid=appname)
        print("%r has been loaded in %s" % (appname, uri))

    def find_appname(self, a, s):
        tries = 0
        while True:
            sessions = s.sessions()
            if a not in sessions:
                return a

            if tries > 3:
                raise RuntimeError(
                        "%r is conflicting, try to pass a new one" % a
                      )

            i = 0
            while True:
                a = "%s.%s" % (a, i)
                if a not in sessions:
                    break
            tries += 1
            return a
