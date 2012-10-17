# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command

from ...manager import Manager
from ...console_output import ConsoleOutput
from ...sig_handler import SigHandler


class Start(Command):
    """\
        Start a process
        ===============

        Start a process or all process from the Procfile.

        Command line
        ------------

        ::

            $ gaffer start [name]


        Gaffer will run your application directly from the command line.

        If no additional parameters are passed, gaffer  run one instance
        of each type of process defined in your Procfile.

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

    name = "start"

    def run(self, procfile, pargs):
        args = pargs.args
        concurrency = self.parse_concurrency(pargs)

        m = Manager()
        m.start(apps=[SigHandler(), ConsoleOutput()])

        if len(args) == 1:
            name = args[0]
            cmd_str = procfile.cfg[name]
            cmd, args = procfile.parse_cmd(cmd_str)
            params = dict(args=args, env=procfile.env,
                    numprocesses=concurrency.get(name, 1),
                    redirect_output=['out', 'err'])
            m.add_process(name, cmd, **params)
        else:
            # add processes
            for name, cmd_str in procfile.processes():
                cmd, args = procfile.parse_cmd(cmd_str)
                params = dict(args=args, env=procfile.env,
                        numprocesses=concurrency.get(name, 1),
                        redirect_output=['out', 'err'])
                m.add_process(name, cmd, **params)
        m.run()
