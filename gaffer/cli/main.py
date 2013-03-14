# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
usage: gaffer [--version] [-f procfile|--procfile procfile]
              [-d root|--root root] [-e path|--env path]...
              [--certfile=CERTFILE] [--keyfile=KEYFILE] [--cacert=CACERT]
              [-g url|--gafferd-http-address url]
              [--api-key API_KEY] <command> [<args>...]

Options

    -h --help                           show this help message and exit
    --version                           show version and exit
    -f procfile,--procfile procfile     Specify an alternate Procfile to load
    -d root,--root root                 Specify an alternate application root
                                        This defaults to the  directory
                                        containing the Procfile [default: .]
    -e path,--env path                  Specify one or more .env files to load
    -g url --gafferd-http-address url   gafferd node HTTP address to connect
                                        [default: http://127.0.0.1:5000]
    --api-key API_KEY                   API Key to access to gaffer
    --certfile=CERTFILE                 SSL certificate file
    --keyfile=KEYFILE                   SSL key file
    --cacert=CACERT                     SSL CA certificate

"""
try:
    import configparser
except ImportError:
    import ConfigParser as configparser
import os
import sys

import tornado

from .. import __version__
from ..docopt import docopt, printable_usage
from ..gafferd.util import user_path, default_user_path
from ..httpclient import Server, GafferUnauthorized, GafferForbidden
from ..procfile import Procfile, get_env
from ..util import is_ssl

from .commands import get_commands


class Config(object):

    def __init__(self, args):
        self.args = args

        if self.args["--env"]:
            self.envs = list(set(self.args["--env"]))
        else:
            self.envs = ['.env']

        # initialize the env object
        self.env = get_env(self.envs)

        # initialize the procfile
        self.procfile = self._init_procfile()

        # get user config path
        self.user_config_path = self.get_user_config()

         # load config
        self.user_config = configparser.RawConfigParser()
        if os.path.isfile(self.user_config_path):
            with open(self.user_config_path) as f:
                self.user_config.readfp(f)

        # node config section
        node_section = "node \"%s\"" % args["--gafferd-http-address"]
        if not self.user_config.has_section(node_section):
            self.user_config.add_section(node_section)

        # parse ssl options
        self.parse_ssl_options(node_section)

        # setup default server
        api_key = self.args['--api-key']
        if (api_key is None and
                self.user_config.has_option(node_section, "key")):
            api_key = self.user_config.get(node_section, "key")

        self.server = Server(self.args["--gafferd-http-address"],
                api_key=api_key, **self.client_options)

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
    def gafferd_address(self):
        return self.args["--gafferd-http-address"]

    def _init_procfile(self):
        procfile = "Procfile"

        if self.args['--procfile']:
            procfile = self.args['--procfile']

        if self.args['--root']:
            root = self.args['--root']
        else:
            root = os.path.dirname(procfile) or "."

        if not os.path.isfile(procfile):
            if self.args['--procfile'] is not None:
                raise RuntimeError("procfile %r not found" % procfile)
            else:
                return None
        else:
            return Procfile(procfile, root=root, envs=self.envs)

    def parse_ssl_options(self, node_section):
        self.client_options = {}
        # get client options from the config file
        if self.user_config.has_option(node_section, "certfile"):
            self.client_options['client_cert'] = self.user_config.get(
                    node_section, "cerfile")

        if self.user_config.has_option(node_section, "keyfile"):
            self.client_options['client_key'] = self.user_config.get(
                    node_section, "keyfile")

        if self.user_config.has_option(node_section, "cacert"):
            self.client_options['ca_certs'] = self.user_config.get(
                    node_section, "cacert")

        # override the ssl options from the command line

        if self.args["--certfile"] is not None:
            self.client_options["client_cer"] = self.args["--certfile"]

        if self.args["--keyfile"] is not None:
            self.client_options["client_key"] = self.args["--keyfile"]

        if self.args["--cacert"] is not None:
            self.client_options = {"ca_certs": self.args["--cacert"]}

    def get_user_config(self):
        if 'GAFFER_CONFIG' in os.environ:
            return os.environ.get('GAFFER_CONFIG')

        for path in user_path():
            config_file = os.path.join(path, "gaffer.ini")
            if os.path.isfile(config_file):
                return config_file

        config_dir = default_user_path()
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        return os.path.join(config_dir, "gaffer.ini")

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
            except GafferUnauthorized:
                print("Unauthorized access. You need an API key")
                sys.exit(1)
            except GafferForbidden:
                print("Forbidden access. API key permissions aren't enough")
                sys.exit(1)
            except tornado.httpclient.HTTPError as e:
                print("HTTP Error: %s\n" % str(e))
                sys.exit(1)

            except RuntimeError as e:
                sys.stderr.write("%s\n" % str(e))
                sys.exit(1)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                sys.stderr.write("%s\n" % str(e))
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
