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

import six

from ..console_output import ConsoleOutput
from ..http_handler import HttpHandler, HttpEndpoint
from ..manager import Manager
from ..pidfile import Pidfile
from ..sig_handler import SigHandler
from ..state import FlappingInfo
from ..util import daemonize, setproctitle_
from ..webhooks import WebHooks

from .plugins import PluginManager
from .util import user_path

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
        os_env = True,
        numprocesses = 1,
        start = True,
        priority = six.MAXSIZE)

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

    def __init__(self, args):
        self.args = args
        self.cfg = None

        config_file = args.config or args.config_file
        if not config_file:
            self.set_defaults()
        else:
            self.parse_config(config_file)

        self.manager = Manager()
        self.plugin_manager = PluginManager(self.plugins_dir)

    def default_endpoint(self):
        params = ENDPOINT_DEFAULTS.copy()

        if self.args.backlog:
            params['backlog'] = self.args.backlog

        if self.args.certfile:
            params['ssl_options']['certfile'] = self.args.certfile

        if self.args.keyfile:
            params['ssl_options']['keyfile'] = self.args.keyfile

        if not params['ssl_options']:
            del params['ssl_options']

        params['uri'] = self.args.bind or '127.0.0.1:5000'
        return HttpEndpoint(**params)

    def set_defaults(self):
        self.plugins_dir = self.args.plugins_dir
        self.webhooks = []
        self.endpoints = [self.default_endpoint()]
        self.processes = []

    def run(self):
        # check if any plugin dependancy is missing
        self.plugin_manager.check_mandatory()

        # setup the http api
        static_sites = self.plugin_manager.get_sites()
        http_handler = HttpHandler(endpoints=self.endpoints,
                handlers=static_sites)

        # setup gaffer apps
        apps = [SigHandler(),
                WebHooks(hooks=self.webhooks),
                http_handler]

        # extend with plugin apps
        plugin_apps = self.plugin_manager.get_apps(self.cfg)
        apps.extend(plugin_apps)

        # verbose mode
        if self.args.verboseful:
            apps.append(ConsoleOutput(actions=['.']))
        elif self.args.verbose:
            apps.append(ConsoleOutput(output_streams=False,
                actions=['.']))

        self.manager.start(apps=apps)

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

    def parse_config(self, config_file):
        cfg, cfg_files_read = self.read_config(config_file)
        self.cfg = cfg

        self.plugins_dir = cfg.dget('gaffer', 'plugins_dir',
                self.args.plugins_dir)

        # you can setup multiple endpoints in the config
        endpoints_str = cfg.dget('gaffer', 'http_endpoints', '')
        endpoints_names = endpoints_str.split(",")

        endpoints = []
        processes = []
        webhooks = []
        envs = {}
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
                        if key == "args":
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
                                    True)
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
                        elif key == "graceful_timeout":
                            params[key] = cfg.dgetint(section, key, 10)
                        elif key == "priority":
                            params[key] = cfg.dgetint(section, key,
                                    six.MAXSIZE)

                    processes.append((name, cmd, params))
            elif section == "webhooks":
                for key, val in cfg.items(section):
                    webhooks.append((key, val))
            elif section.startswith('env:'):
                pname = section.split("env:", 1)[1]
                kvs = [(key.upper(), val) for key, val in cfg.items(section)]
                envs[pname] = dict(kvs)

        # add environment variables
        for name, cmd, params in processes:
            if name in envs:
                params['env'] = envs[name]

        # sort processes by priority
        processes = sorted(processes, key=lambda p: p[2]['priority'])

        if not endpoints:
            # we create a default endpoint
            endpoints = [self.default_endpoint()]

        self.endpoints = endpoints
        self.webhooks = webhooks
        self.processes = processes

def run():
    # default plugins dir
    plugins_dir = os.path.join(user_path(), "plugins")

    # define the argument parser
    parser = argparse.ArgumentParser(description='Run some watchers.')
    parser.add_argument('config', help='configuration file',
            nargs='?')

    parser.add_argument('-c', '--config', dest='config_file',
            help='configuration file')
    parser.add_argument('-p', '--plugins-dir', dest='plugins_dir',
            help="default plugin dir", default=plugins_dir),

    parser.add_argument('-v', dest='verbose', action='store_true',
            help="verbose mode")
    parser.add_argument('-vv', dest='verboseful', action='store_true',
            help="like verbose mode but output stream too")
    parser.add_argument('--daemon', dest='daemonize', action='store_true',
            help="Start gaffer in the background")
    parser.add_argument('--pidfile', dest='pidfile')
    parser.add_argument('--bind', dest='bind',
            default='127.0.0.1:5000', help="default HTTP binding"),
    parser.add_argument('--certfile', dest='certfile',
            help="SSL certificate file for the default binding"),
    parser.add_argument('--keyfile', dest='keyfile',
            help="SSL key file for the default binding"),
    parser.add_argument('--backlog', dest='backlog', type=int,
            default=128, help="default backlog"),

    args = parser.parse_args()

    if args.daemonize:
        daemonize()

    setproctitle_("gafferd")

    pidfile = None
    if args.pidfile:
        pidfile = Pidfile(args.pidfile)

        try:
            pidfile.create(os.getpid())
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

    s = Server(args)

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
