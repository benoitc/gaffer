# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import argparse
from io import StringIO
import json
import os
import sys

from .. import __version__
from ..manager import Manager
from ..procfile import Procfile
from ..console_output import ConsoleOutput
from ..sig_handler import SigHandler


COMMANDS = [
    ('start', 'start [name]', 'start a process'),
    ('run', 'run <cmd>', 'run one-off commands'),
    ('export', 'export [format]',  'export'),
]

CHOICES = [c[0] for c in COMMANDS]


class ProcfileManager(object):

    def __init__(self):
        self.parser = self._init_parser()
        self.procfile = None
        self.concurrency_settings = {}
        self.root = "."
        self.envs = [".env"]
        self.procfile_name = "Procfile"


    def run(self):
        self.args = args = self.parser.parse_args()

        if not args.command:
            self.parser.print_version()
            self.parser.print_help()
        else:
            self._init_procfile()
            self._build_concurrency()

            try:
                getattr(self, "handle_%s" % args.command)()
            except Exception as e:
                sys.stdout.write(str(e))
                sys.exit(1)

        sys.exit(0)


    def handle_start(self):
        args = self.args.args

        m = Manager()
        m.start(apps=[SigHandler(), ConsoleOutput()])

        if len(args) == 1:
            name = args[0]
            cmd_str = self.procfile.cfg[name]
            cmd, args = self.procfile.parse_cmd(cmd_str)
            params = dict(args=args, env=self.procfile.env,
                    numprocesses=self.concurrency_settings.get(name, 1),
                    redirect_output=['out', 'err'])
            m.add_process(name, cmd, **params)
        else:
            # add processes
            for name, cmd_str in self.procfile.processes():
                cmd, args = self.procfile.parse_cmd(cmd_str)
                params = dict(args=args, env=self.procfile.env,
                        numprocesses=self.concurrency_settings.get(name, 1),
                        redirect_output=['out', 'err'])
                m.add_process(name, cmd, **params)
        m.run()

    def handle_run(self):
        args = self.args.args
        m = Manager()
        m.start(apps=[SigHandler(), ConsoleOutput()])
        if not args:
            raise RuntimeError("command is missing")

        if self.args.concurrency and self.args.concurrency is not None:
            numprocesses = int(self.args.concurrency)
        else:
            numprocesses = 1

        cmd_str = args[0]
        cmd, args = self.procfile.parse_cmd(cmd_str)
        name = os.path.basename(cmd)
        params = dict(args=args, env=self.procfile.env,
                numprocesses=numprocesses,
                redirect_output=['out', 'err'])
        m.add_process(name, cmd, **params)
        m.run()

    def handle_export(self):
        args = self.args.args

        if len(args) < 1:
            raise RuntimeError("format is missing")

        if args[0] == "json":
            if len(args) < 2:
                raise RuntimeError("procname is missing")
            try:
                obj = self.procfile.as_dict(args[1],
                        self.concurrency_settings)
            except KeyError:
                raise KeyError("%r is not found" % args[1])

            if len(args) == 3:
                with open(args[2], 'w') as f:
                    json.dump(obj, f, indent=True)

            else:
                print(json.dumps(obj, indent=True))
        else:
            config = self.procfile.as_configparser(self.concurrency_settings)
            if len(args) == 2:
                with open(args[1], 'w') as f:
                    config.write(f, space_around_delimiters=True)
            else:
                buf = StringIO()
                config.write(buf, space_around_delimiters=True)
                print(buf.getvalue())


    def _build_concurrency(self):
        if not self.args.concurrency:
            return

        settings = {}
        lsettings = self.args.concurrency.split(",")
        for setting in lsettings:
            kv = setting.split("=")
            if len(kv) == 2:
                key = kv[0].strip()
                try:
                    val = int(kv[1].strip())
                except ValueError:
                    continue
                settings[key] = val
        self.concurrency_settings = settings.copy()

    def _init_procfile(self):
        if self.args.root:
            self.root = self.args.root

        if self.args.procfile:
            self.procfile_name = self.args.procfile

        if self.args.envs:
            self.envs = self.args.envs

        fname = os.path.join(self.root, self.procfile_name)
        self.procfile = Procfile(fname, self.envs)


    def _init_parser(self):
        version_str = "%(prog)s " + __version__

        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description='manage Procfiles applications.',
            usage='%(prog)s [options] command [args]',
            epilog=self._commands_help())

        # initialize arguments
        parser.add_argument('command', nargs="?", choices=CHOICES,
                help=argparse.SUPPRESS)
        parser.add_argument('args', nargs="*", help=argparse.SUPPRESS)

        parser.add_argument('-c', '--concurrency', dest='concurrency',
                help="""Specify the number of each process type to
                run. The value passed in should be in the format
                process=num,process=num""")
        parser.add_argument('-e', '--env', dest='envs', nargs="+",
                help='Specify one or more .env files to load')

        parser.add_argument('-f', '--procfile', dest='procfile',
                metavar='FILE', default='Procfile',
                help='Specify an alternate Procfile to load')

        parser.add_argument('-d', '--directory', dest='root',
                default='.',
                help="""Specify an alternate application root. This
                defaults to the  directory containing the
                Procfile""")
        parser.add_argument('--version', action='version',
                version=version_str)
        return parser

    def _commands_help(self):
        max_len = max([len(c[1]) for c in COMMANDS])
        output = ['Commands:', '']
        for name, cmd, short_descr in COMMANDS:
            output.append('\t%-*s\t%s' % (max_len, cmd, short_descr))

        output.append('')
        return '\n'.join(output)

def main():
    ProcfileManager().run()

if __name__ == "__main__":
    main()
