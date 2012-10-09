# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

# -*- coding: utf-8 -

import getopt
import sys
import traceback

import pyuv

from .commands import get_commands
from .httpclient import Server, GafferNotFound, GafferConflict

globalopts = [
    ('', 'connect', "", "http endpoint"),
    ('', 'certfile', None, "SSL certificate file"),
    ('', 'keyfile', None, "SSL key file"),
    ('h', 'help', None, "display help and exit"),
    ('v', 'version', None, "display version and exit")
]


def _get_switch_str(opt):
    """
    Output just the '-r, --rev [VAL]' part of the option string.
    """
    if opt[2] is None or opt[2] is True or opt[2] is False:
        default = ""
    else:
        default = "[VAL]"
    if opt[0]:
        # has a short and long option
        return "-%s, --%s %s" % (opt[0], opt[1], default)
    else:
        # only has a long option
        return "--%s %s" % (opt[1], default)


class GafferCtl(object):

    def __init__(self, loop=None):
        self.loop = loop or pyuv.Loop.default_loop()
        self.commands = get_commands()

    def run(self, args):
        try:
            sys.exit(self.dispatch(args))
        except getopt.GetoptError as e:
            print("Error: %s\n" % str(e))
            self.display_help()
            sys.exit(2)
        except GafferConflict as e:
            sys.stderr.write("%s\n" % str(e))
            sys.exit(1)
        except GafferNotFound as e:
            sys.stderr.write("%s\n" % str(e))
            sys.exit(1)
        except KeyboardInterrupt:
            sys.exit(1)
        except RuntimeError as e:
            sys.stderr.write("%s\n" % str(e))
            sys.exit(1)
        except Exception as e:
            sys.stderr.write(traceback.format_exc())
            sys.exit(1)

    def dispatch(self, args):
        cmd, globalopts, opts, args = self._parse(args)

        if globalopts['help'] or cmd == "help":
            del globalopts["help"]
            return self.display_help(*args, **globalopts)
        elif globalopts['version'] or cmd == "version":
            return self.display_version()

        else:
            if cmd not in self.commands:
                raise RuntimeError('Unknown command %r' % cmd)

            cmd = self.commands[cmd]

        endpoint = globalopts.get('connect')
        if not endpoint:
            endpoint = 'http://127.0.0.1:5000'

        certfile = globalopts.get('certfile')
        keyfile = globalopts.get('keyfile')

        if not certfile or not keyfile:
            server_params = {}
        else:
            ssl_options = {"certfile": certfile, "keyfile": keyfile}
            server_params = {"ssl_options": ssl_options}
        server = Server(uri=endpoint, **server_params)

        ret = cmd.run(server, args, opts)
        if ret == True:
            print("ok")
        else:
            print(ret)

    def display_help(self, *args, **opts):
        if opts.get('version', False):
            self.display_version(*args, **opts)

        if len(args) >= 1:
            if args[0] in  self.commands:
                cmd = self.commands[args[0]]
                print(cmd.desc)
            return 0

        print("usage: gafferctl [--version] [--connect=<endpoint>]")
        print("                 [--certfile] [--keyfile]")
        print("                 [--help]")
        print("                 <command> [<args>]")
        print("")
        print("Commands:")
        commands = sorted([name for name in self.commands] + ["help"])

        max_len = len(max(commands, key=len))
        for name in commands:
            if name == "help":
                desc = "Get help on a command"
                print("\t%-*s\t%s" % (max_len, name, desc))
            else:
                cmd = self.commands[name]
                # Command name is max_len characters.
                # Used by the %-*s formatting code
                print("\t%-*s\t%s" % (max_len, name, cmd.short))

        return 0

    def display_version(self, *args, **opts):
        from gaffer import __version__

        print("gaffer (version %s)" % __version__)
        print("Available in the public domain.")
        print("")
        return 0


    def _parse(self, args):
        options = {}
        cmdoptions = {}
        args = self._parseopts(args, globalopts, options)

        if args:
            cmd, args = args[0], args[1:]
            cmd = cmd.lower()

            if cmd in self.commands:
                cmdopts = self.commands[cmd].options
            else:
                cmdopts = []
        else:
            cmd = "help"
            cmdopts = []

        for opt in globalopts:
            cmdopts.append((opt[0], opt[1], options[opt[1]], opt[3]))

        args = self._parseopts(args, cmdopts, cmdoptions)

        cmdoptions1 = cmdoptions.copy()
        for opt, val in cmdoptions1.items():
            if opt in options:
                options[opt] = val
                del cmdoptions[opt]

        return cmd, options, cmdoptions, args

    def _parseopts(self, args, options, state):
        namelist = []
        shortlist = ''
        argmap = {}
        defmap = {}

        for short, name, default, comment in options:
            oname = name
            name = name.replace('-', '_')
            argmap['-' + short] = argmap['--' + oname] = name
            defmap[name] = default

            if isinstance(default, list):
                state[name] = default[:]
            else:
                state[name] = default

            if not (default is None or default is True or default is False):
                if short:
                    short += ':'
                if oname:
                    oname += '='
            if short:
                shortlist += short
            if name:
                namelist.append(oname)

        opts, args = getopt.getopt(args, shortlist, namelist)
        for opt, val in opts:
            name = argmap[opt]
            t = type(defmap[name])
            if t is type(1):
                state[name] = int(val)
            elif t is type(''):
                state[name] = val
            elif t is type([]):
                state[name].append(val)
            elif t is type(None) or t is type(False):
                state[name] = True

        return args


def run():
    GafferCtl().run(sys.argv[1:])

if __name__ == '__main__':
    run()
