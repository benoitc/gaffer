# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import argparse
import os
import sys

from .. import __version__
from ..procfile import Procfile
from .commands import get_commands

COMMANDS = [
    ('start', 'start [name]', 'start a process'),
    ('run', 'run <cmd>', 'run one-off commands'),
    ('export', 'export [format]',  'export'),
]

CHOICES = [c[0] for c in COMMANDS]


class ProcfileManager(object):

    def __init__(self):

        self.commands = get_commands()
        self.parser = self._init_parser()
        self.procfile = None
        self.concurrency_settings = {}
        self.root = "."
        self.envs = [".env"]
        self.procfile_name = "Procfile"


    def run(self):
        self.args = args = self.parser.parse_args()

        if not args.command:
            self.display_help()
        elif args.command.lower() == "help":
            if args.args[0] in self.commands:
                cmd = self.commands[args.args[0]]
                print(cmd.desc)
        else:
            self._init_procfile()
            cmd = self.commands[args.command]
            try:
                return cmd.run(self.procfile, args)
            except Exception as e:
                sys.stdout.write(str(e))
                sys.exit(1)
        sys.exit(0)

    def display_help(self):
        self.parser.print_help()

    def display_version(self):
        from gaffer import __version__

        return "\n".join([
            "%(prog)s (version " +  __version__ + ")\n"
            "Available in the public domain.", ""])


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
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description='manage Procfiles applications.',
            usage='%(prog)s [options] command [args]',
            epilog=self._commands_help())

        commands = sorted([name for name in self.commands] + ["help"])

        # initialize arguments
        parser.add_argument('command', nargs="?", choices=commands,
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

        parser.add_argument('--endpoint', dest='endpoint',
                default='http://127.0.0.1:5000',
                help="Gaffer node URL to connect")

        parser.add_argument('--version', action="version",
                version=self.display_version())
        return parser

    def _commands_help(self):
        commands = [name for name in self.commands] + ["help"]
        max_len = len(max(commands, key=len))
        output = ["Commands:",
                  "---------",
                  " "]
        for name in commands:
            if name == "help":
                desc = "Get help on a command"
                output.append("\t%-*s\t%s" % (max_len, name, desc))
            else:
                cmd = self.commands[name]
                # Command name is max_len characters.
                # Used by the %-*s formatting code
                output.append("\t%-*s\t%s" % (max_len, name, cmd.short))
        output.append("")
        return '\n'.join(output)

def main():
    pm = ProcfileManager()
    pm.run()

if __name__ == "__main__":
    main()
