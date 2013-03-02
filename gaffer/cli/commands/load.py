# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os

from .base import Command
from ...httpclient import GafferConflict
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

        # load configs
        configs = self.load_jsonconfig(fname)

        for conf in configs:
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
            try:
                server.load(pconfig, sessionid=appname, start=start)
                print("%r has been loaded in %s" % (pname, server.uri))
            except GafferConflict:
                print("%r already loaded" % pname)

        print("%r has been loaded" % fname)

    def load_procfile(self, config, args):
        procfile, server = config.get("procfile", "server")
        appname = self.default_appname(config, args)

        # parse the concurrency settings
        concurrency = self.parse_concurrency(args)

        # finally send the processes
        for name, cmd_str in procfile.processes():
            if name in procfile.redirect_input:
                redirect_input = True
            else:
                redirect_input = False

            cmd, args = procfile.parse_cmd(cmd_str)
            params = dict(args=args, env=procfile.env,
                    numprocesses=concurrency.get(name, 1),
                    redirect_output=['out', 'err'],
                    redirect_input=redirect_input,
                    cwd=os.path.abspath(procfile.root))

            config = ProcessConfig(name, cmd, **params)
            try:
                server.load(config, sessionid=appname)
            except GafferConflict:
                print("%r already loaded" % name)

        print("==> %r has been loaded in %s" % (appname, server.uri))
