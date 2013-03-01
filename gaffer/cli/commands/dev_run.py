# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os

from .base import Command

from ...manager import Manager
from ...console_output import ConsoleOutput
from ...process import ProcessConfig
from ...sig_handler import SigHandler


class DevRun(Command):
    """
    usage: gaffer dev:run [-v] [-c concurrency|--concurrency concurrency]
                          (<args>...)

      -h, --help
      -c concurrency,--concurrency concurrency  Specify the number processesses
                                                to run.
      -v  verbose
    """

    name = "dev:run"
    short_descr = "run one-off commands locally"

    def run(self, config, args):
        if not config.use_procfile:
            raise RuntimeError("procfile not found")

        m = Manager()
        m.start(apps=[SigHandler(), ConsoleOutput()])

        if not args['--concurrency']:
            numprocesses = 1
        else:
            numprocesses = int(args['--concurrency'])

        # parse command
        cmd_str = " ".join(args['<args>'])
        cmd, cmd_args = config.procfile.parse_cmd(cmd_str)
        name = os.path.basename(cmd)

        appname = config.procfile.get_appname()

        # if verbose the display stdout/stderr
        if args['-v']:
            redirect_output = ['out', 'err']
        else:
            redirect_output = []

        params = dict(args=cmd_args, env=config.procfile.env,
                numprocesses=numprocesses,
                redirect_output=redirect_output)

        config = ProcessConfig(name, cmd, **params)
        m.load(config, sessionid=appname)
        m.run()
