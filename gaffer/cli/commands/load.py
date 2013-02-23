# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import os
import sys

from .base import Command
from ...process import ProcessConfig


class Load(Command):
    """
    usage: gaffer load [-c concurrency|--concurrency concurrency]...
                       [--app APP] [<file>]

    Args

        <file>  Path to a job configuration  or stdin ``-``

    Options

    -h, --help
    -c concurrency,--concurrency concurrency  Specify the number processesses
                                              to run.
    --app APP                                 application name
    """

    name = "load"
    short_descr = "load a Procfile application"

    def run(self, config, args):
        if args['<file>']:
            self.load_file(config, args)
        elif config.use_procfile:
            self.load_procfile(config, args)
        else:
            raise RuntimeError("procfile or job file is missing")

    def load_file(self, config, args):
        fname = args['<file>']
        server = config.get("server")

        # load raw config
        if fname == "-":
            content = []
            while True:
                data = sys.stdin.readline()
                if not data:
                    break
                content.append(data)
            content = ''.join(content)
        else:
            if not os.path.isfile(fname):
                raise RuntimeError("%r not found")

            with open(fname, 'rb') as f:
                content = f.read()

        if isinstance(content, bytes):
            content = content.decode('utf-8')

        # parse the config
        conf = json.loads(content)
        try:
            name = conf.pop('name')
            cmd = conf.pop('cmd')
        except KeyError:
            raise ValueError("invalid job config")

        # parse job name and eventually extract the appname
        appname, name = self.parse_name(name, self.default_appname(config,
            args))

        # always force the appname if specified
        if args['--app']:
            appname = args['--app']


        # finally load the config
        pname = "%s.%s" % (appname, name)
        start = conf.get('start', True)
        pconfig = ProcessConfig(name, cmd, **conf)
        server.load(pconfig, sessionid=appname, start=start)
        print("%r has been loaded in %s" % (pname, server.uri))

    def load_procfile(self, config, args):
        procfile, server = config.get("procfile", "server")
        appname = self.default_appname(config, args)

        # manage appname conflicts
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
