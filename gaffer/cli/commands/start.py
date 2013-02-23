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
    usage: gaffer start [-c proctype=value|--concurrency proctype=value]...
                        [<appname>]

      -c proctype=value,--concurrency proctype=value  Specify the number of
                                                      each process type to
                                                      run.
    """

    name = "start"
    short_descr = "start a process"

    def run(self, config, args):
        concurrency = self.parse_concurrency(args)

        m = Manager()
        m.start(apps=[SigHandler(), ConsoleOutput()])

        if len(args) == 1:
            name = args[0]
            cmd_str = procfile.cfg[name]
            cmd, args = procfile.parse_cmd(cmd_str)
            appname = procfile.get_appname()
            params = dict(args=args, env=procfile.env,
                    numprocesses=concurrency.get(name, 1),
                    redirect_output=['out', 'err'])

            config = ProcessConfig(name, cmd, **params)
            m.load(config, sessionid=appname)
        else:
            appname = procfile.get_appname()

            # add processes
            for name, cmd_str in procfile.processes():
                cmd, args = procfile.parse_cmd(cmd_str)
                params = dict(args=args, env=procfile.env,
                        numprocesses=concurrency.get(name, 1),
                        redirect_output=['out', 'err'])
                config = ProcessConfig(name, cmd, **params)
                m.load(config, sessionid=appname)
        m.run()
