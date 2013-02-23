# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os

from .base import Command
from ...process import ProcessConfig


class Load(Command):
    """
    usage: gaffer load [-c concurrency|--concurrency concurrency]...
                       [<appname>]

    <appname>  name of the application recorded in hafferd. By default it
                 will be the name of your project folder.You can use ``.`` to specify the
                 current folder.

    -h, --help
    -c concurrency,--concurrency concurrency  Specify the number processesses
                                                to run.

    """

    name = "load"
    short_descr = "load a Procfile application"

    def run(self, config, args):
        procfile, server = config.get("procfile", "server")
        appname = args['<appname>']
        if not appname or appname == ".":
            # get the default appname
            appname = procfile.get_appname()

        # replace all "." from the appname
        appname = appname.replace(".", "-")

        # finally manage group conflicts
        appname = self.find_appname(appname, server)

        # parse the concurrency settings
        concurrency = self.parse_concurrency(args)

        # finally send the processes
        for name, cmd_str in procfile.processes():
            cmd, args = procfile.parse_cmd(cmd_str)
            params = dict(args=args, env=procfile.env,
                    numprocesses=concurrency.get(name, 1),
                    redirect_output=['out', 'err'],
                    cwd=os.path.abspath(procfile.root))

            config = ProcessConfig(name, cmd, **params)
            server.load(config, sessionid=appname)
        print("%r has been loaded in %s" % (appname, server.uri))

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
                a = "%s-%s" % (a, i)
                if a not in sessions:
                    break
            tries += 1
            return a
