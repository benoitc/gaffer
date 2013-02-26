# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command

from ...manager import Manager
from ...console_output import ConsoleOutput
from ...process import ProcessConfig
from ...sig_handler import SigHandler


class Start(Command):
    """
    usage: gaffer dev:start [-v] [-c job=v|--concurrency job=v]...
                            [<job>]

      -c job=v,--concurrency job=v  Specify the number of each process
                                    type to run.
      -v  verbose
    """

    name = "dev:start"
    short_descr = "start a process locally from a procfile"

    def run(self, config, args):
        if not config.use_procfile:
            raise RuntimeError("procfile not found")

        concurrency = self.parse_concurrency(args)
        m = Manager()
        m.start(apps=[SigHandler(), ConsoleOutput()])

        # if verbose the display stdout/stderr
        if args['-v']:
            redirect_output = ['out', 'err']
        else:
            redirect_output = []

        # load job configs
        if args['<job>']:
            name = args['<job>']
            cmd_str = config.procfile.cfg[name]
            cmd, cmd_args = config.procfile.parse_cmd(cmd_str)
            appname = config.procfile.get_appname()
            params = dict(args=cmd_args, env=config.procfile.env,
                    numprocesses=concurrency.get(name, 1),
                    redirect_output=redirect_output)

            pconfig = ProcessConfig(name, cmd, **params)
            m.load(pconfig, sessionid=appname)
        else:
            appname = config.procfile.get_appname()

            # add processes
            for name, cmd_str in config.procfile.processes():
                cmd, cmd_args = config.procfile.parse_cmd(cmd_str)
                params = dict(args=cmd_args, env=config.procfile.env,
                        numprocesses=concurrency.get(name, 1),
                        redirect_output=redirect_output)
                pconfig = ProcessConfig(name, cmd, **params)
                m.load(pconfig, sessionid=appname)

        # run the gaffer manager
        m.run()
