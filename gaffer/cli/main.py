# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
usage: gaffer [--version] [-f procfile|--procfile procfile]
              [-d root|--root root] [-e path|--env path]...
              [--gafferd-http-address url] <command> [<args>...]

Options

    -h --help                           show this help message and exit
    --version                           show version and exit
    -f procfile,--procfile procfile     Specify an alternate Procfile to load
    -d root,--root root                 Specify an alternate application root
                                        This defaults to the  directory
                                        containing the Procfile [default: .]
    -e path,--env path                  Specify one or more .env files to load
    --gafferd-http-address url          gafferd node HTTP address to connect
                                        [default: http://127.0.0.1:5000]

"""
import os
import sys


from .. import __version__
from ..docopt import docopt, printable_usage
from ..httpclient import Server
from ..procfile import Procfile

from .commands import get_commands


class Config(object):

    def __init__(self, args):
        self.args = args

        # initialize the procfile
        self.procfile = self._init_procfile()

        # setup default server
        self.server = Server(self.args["--gafferd-http-address"])

    def get(self, *attrs):
        ret = []
        for name in attrs:
            ret.append(getattr(self, name))

        if len(ret) == 1:
            return ret[0]

        return tuple(ret)

    @property
    def use_procfile(self):
        return isinstance(self.procfile, Procfile)

    @property
    def gafferd_address(sef):
        return self.args["--gafferd-http-address"]

    def _init_procfile(self):
        if self.args["--env"]:
            envs = list(set(self.args["--env"]))
        else:
            envs = ['.env']

        procfile = "Procfile"

        if self.args['--procfile']:
            procfile = self.args['--procfile']

        if self.args['--root']:
            root = self.args['--root']
        else:
            root = os.path.dirname(procfile) or "."

        if not os.path.exists(procfile):
            if self.args['--procfile']:
                raise RuntimeError("procfile %r not found" % procfile)
            else:
                return None

        else:
            return Procfile(procfile, root=root, envs=envs)

class GafferCli(object):

    def __init__(self, argv=None):
        self.commands = get_commands()

        version_str = "gaffer version %s" % __version__
        self.doc_str = "%s%s" % (__doc__, self._commands_help())
        self.args = docopt(self.doc_str, argv=argv,  version=version_str,
                options_first=True)

    def run(self):
        if self.args['<command>'].lower() == "help":
            self.display_help()
        else:
            cmdname = self.args['<command>']
            if cmdname not in self.commands:
                print("Unknown command: %r" % cmdname)
                self.display_help()
                sys.exit(1)

            # parse command arguments
            cmd = self.commands[cmdname]
            cmd_argv = [cmdname] + self.args['<args>']
            cmd_args =  docopt(cmd.__doc__, argv=cmd_argv)

            try:
                config = Config(self.args)
            except RuntimeError as e:
                sys.stderr.write("config error: %s" % str(e))
                sys.exit(1)

            # finally launch the command
            cmd = self.commands[cmdname]
            try:
                return cmd.run(config, cmd_args)
            except Exception as e:
                sys.stderr.write(str(e))
                sys.exit(1)
        sys.exit(0)

    def display_help(self):
        if self.args['<args>']:
            name = self.args['<args>'][0]
            if name in self.commands:
                cmd = self.commands[name]
                print(printable_usage(self.commands[name].__doc__))
                return

        print(self.doc_str)

    def _commands_help(self):
        commands = [name for name in self.commands] + ["help"]
        max_len = len(max(commands, key=len))
        output = ["Commands",
                  " "]
        for name in commands:
            if name == "help":
                desc = "Get help on a command"
                output.append("    %-*s\t%s" % (max_len, name, desc))
            else:
                cmd = self.commands[name]
                # Command name is max_len characters.
                # Used by the %-*s formatting code
                output.append("    %-*s\t%s" % (max_len, name, cmd.short_descr))
        output.append("")
        return '\n'.join(output)


def main():
    cli = GafferCli()
    cli.run()

if __name__ == "__main__":
    main()
