# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os

from .base import Command

from ...manager import Manager
from ...console_output import ConsoleOutput
from ...process import ProcessConfig
from ...sig_handler import SigHandler


class Run(Command):
    """
    usage: gaffer run [-c concurrency|--concurrency concurrency] [<args>...]

      -h, --help
      -c concurrency,--concurrency concurrency  Specify the number processesses
                                                to run.
    """

    name = "run"
    short_descr = "run one-off commands"

    def run(self, config, args):

        m = Manager()
        m.start(apps=[SigHandler(), ConsoleOutput()])

        if not args['--concurrency']:
            numprocesses = 1
        else:
            numprocesses = int(args['--concurrency'])

        cmd_str = " ".join(args['<args>'])
        cmd, args = procfile.parse_cmd(cmd_str)
        name = os.path.basename(cmd)
        appname = procfile.get_appname()
        params = dict(args=args, env=procfile.env,
                numprocesses=numprocesses,
                redirect_output=['out', 'err'])

        config = ProcessConfig(name, cmd, **params)
        m.load(config, sessionid=appname)
        m.run()
