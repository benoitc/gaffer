# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os

from .base import Command

from ...manager import Manager
from ...console_output import ConsoleOutput
from ...sig_handler import SigHandler


class Run(Command):
    """\
        Run one-off command
        -------------------

        gaffer run is used to run one-off commands using the same
        environment as your defined processes.

        Command line:
        -------------

        ::

            $ gaffer run /some/script



        Options
        +++++++

        **-c**, **--concurrency**:

            Specify the number of each process type to run. The value
            passed in should be in the format process=num,process=num

        **--env**
            Specify one or more .env files to load

        **-f**, **--procfile**:
            Specify an alternate Procfile to load

        **-d**, **--directory**:

            Specify an alternate application root. This defaults to the
            directory containing the Procfile
    """

    name = "run"

    def run(self, procfile, pargs):
        args = pargs.args

        m = Manager()
        m.start(apps=[SigHandler(), ConsoleOutput()])
        if not args:
            raise RuntimeError("command is missing")

        if pargs.concurrency and pargs.concurrency is not None:
            numprocesses = int(pargs.concurrency)
        else:
            numprocesses = 1

        cmd_str = " ".join(args)
        cmd, args = procfile.parse_cmd(cmd_str)
        name = os.path.basename(cmd)
        params = dict(args=args, env=procfile.env,
                numprocesses=numprocesses,
                redirect_output=['out', 'err'])
        m.add_process(name, cmd, **params)
        m.run()
