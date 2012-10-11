# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import argparse
import fnmatch
try:
    import configparser
except ImportError:
    import ConfigParser as configparser
import os
import sys

from .http_handler import HttpHandler, HttpEndpoint
from .manager import Manager, FlappingInfo
from .pidfile import Pidfile
from .sig_handler import SigHandler
from .util import daemonize


ENDPOINT_DEFAULTS = dict(
        uri = None,
        backlog = 128,
        ssl_options = {})

PROCESS_DEFAULTS = dict(
        group = None,
        args = None,
        env = {},
        uid = None,
        gid = None,
        cwd = None,
        detach = False,
        shell = False,
        os_env = False,
        numprocesses = 1,
        start = True)

class DefaultConfigParser(configparser.ConfigParser):
    """ object overriding ConfigParser to return defaults values instead
    of raising an error if needed """

    def dget(self, section, option, default=None):
        if not self.has_option(section, option):
            return default
        return self.get(section, option)

    def dgetint(self, section, option, default=None):
        if not self.has_option(section, option):
            return default
        return self.getint(section, option)

    def dgetboolean(self, section, option, default=None):
        if not self.has_option(section, option):
            return default
        return self.getboolean(section, option)


class Server(object):
    """ Server object used for gafferd """

    def __init__(self, config_path):
        self.controllers, self.processes = self.get_config(config_path)
        self.manager = Manager()

    def run(self):
        self.manager.start(controllers=self.controllers)

        # add processes
        for name, cmd, params in self.processes:
            self.manager.add_process(name, cmd, **params)

        # run the main loop
        self.manager.run()

    def read_config(self, config_path):
        cfg = DefaultConfigParser()
        with open(config_path) as f:
            cfg.readfp(f)
        cfg_files_read = [config_path]

        # load included config files
        includes = []
        for include_file in cfg.dget('gaffer', 'include', '').split():
            includes.append(include_file)

        for include_dir in cfg.dget('gaffer', 'include_dir', '').split():
            for root, dirnames, filenames in os.walk(include_dir):
                for filename in fnmatch.filter(filenames, '*.ini'):
                    cfg_file = os.path.join(root, filename)
                    includes.append(cfg_file)

        cfg_files_read.extend(cfg.read(includes))

        return cfg, cfg_files_read

    def get_config(self, config_file):
        cfg, cfg_files_read = self.read_config(config_file)

        # you can setup multiple endpoints in the config
        endpoints_str = cfg.dget('gaffer', 'http_endpoints', '')
        endpoints_names = endpoints_str.split(",")

        endpoints = []
        processes = []
        for section in cfg.sections():
            if section.startswith('endpoint:'):
                name = section.split("endpoint:", 1)[1]
                if name in endpoints_names:
                    kwargs = ENDPOINT_DEFAULTS.copy()

                    for key, val in cfg.items(section):
                        if key == "bind":
                            kwargs['uri'] = val
                        elif key == "backlog":
                            kwargs = cfg.dgetint(section, key, 128)
                        elif key == "certfile":
                            kwargs['ssl_options'][key] = val
                        elif key == "keyfile":
                            kwargs['ssl_options'][key] = val

                    if not kwargs['ssl_options']:
                        kwargs['ssl_options'] = None
                    if kwargs.get('uri') is not None:
                        endpoints.append(HttpEndpoint(**kwargs))
            elif section.startswith('process:'):
                name = section.split("process:", 1)[1]
                cmd = cfg.dget(section, 'cmd', '')
                if cmd:
                    params = PROCESS_DEFAULTS.copy()
                    for key, val in cfg.items(section):
                        if key == "group":
                            params[key] = val
                        elif key == "args":
                            params[key] = val
                        elif key.startswith('env:'):
                            envname = key.split("env:", 1)[1]
                            params['env'][envname] = val
                        elif key == 'uid':
                            params[key] = val
                        elif key == 'gid':
                            params[key] = val
                        elif key == 'cwd':
                            params[key] = val
                        elif key == 'detach':
                            params[key] = cfg.dgetboolean(section, key,
                                    False)
                        elif key == 'shell':
                            params[key] = cfg.dgetboolean(section, key,
                                    False)
                        elif key == 'os_env':
                            params[key] = cfg.dgetboolean(section, key,
                                    False)
                        elif key == 'numprocesses':
                            params[key] = cfg.dgetint(section, key, 1)
                        elif key == 'start':
                            params[key] = cfg.dgetboolean(section, key,
                                    True)
                        elif key == 'flapping':
                            # flapping values are passed in order on one
                            # line
                            values_str = val.split(None)
                            try:
                                values = [float(val) for val in values_str]
                                params['flapping'] = FlappingInfo(*values)
                            except ValueError:
                                pass
                        elif key == "redirect_output":
                            params[key] = [v.strip() for v in val.split(",")]
                        elif key == "redirect_input":
                            params[key] = cfg.dgetboolean(section, key,
                                    False)


                    processes.append((name, cmd, params))

        if not endpoints:
            # we create a default endpoint
            endpoints = [HttpEndpoint()]

        controllers = [SigHandler(), HttpHandler(endpoints=endpoints)]
        return controllers, processes

def run():
    parser = argparse.ArgumentParser(description='Run some watchers.')
    parser.add_argument('config', help='configuration file')

    parser.add_argument('--daemon', dest='daemonize', action='store_true',
            help="Start gaffer in the background")
    parser.add_argument('--pidfile', dest='pidfile')

    args = parser.parse_args()

    if args.daemonize:
        daemonize()

    pidfile = None
    if args.pidfile:
        pidfile = Pidfile(args.pidfile)

        try:
            pidfile.create(os.getpid())
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

    s = Server(args.config)

    try:
        s.run()
    except KeyboardInterrupt:
        pass
    finally:
        if pidfile is not None:
            pidfile.unlink()

    sys.exit(0)

if __name__ == "__main__":
    run()
