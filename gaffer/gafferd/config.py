# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy
import fnmatch
import os
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

import six

from ..gafferd.util import user_path
from ..state import FlappingInfo

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


class ConfigError(Exception):
    """ exception raised on config error """


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


class Config(object):
    """ main gafferd config object """

    def __init__(self, args, config_dir):
        self.args = args
        self.config_dir = config_dir
        self.cfg = None

        # set defaulut
        self.set_defaults()

    def load(self):
        """ load the config """

        # maybe load config from a config file
        config_file = os.path.join(self.config_dir, "gafferd.ini")
        if os.path.isfile(config_file):
            self.parse_config(config_file)

        # if the plugin dir hasn't been set yet, set it to the default path
        if not self.plugin_dir:
            if 'GAFFER_PLUGIN_DIR' in os.environ:
                self.plugin_dir = os.environ.get('GAFFER_PLUGIN_DIR')
            else:
                self.plugin_dir = os.path.join(self.config_dir, "plugins")

        # bind address
        self.bind = self.args['--bind'] or self.bind

        #lookupd address
        if self.args['--lookupd-address'] is not None:
            self.lookupd_addresses = self.args['--lookupd-address']

        # broadcast address
        if self.args['--broadcast-address']:
            self.broadcast_address = self.args['--broadcast-address']

        if (self.broadcast_address is not None and
                not self.broadcast_address.startswith("http://") and
                not self.broadcast_address.startswith("https://")):
            raise ConfigError("invalid broadcast address")

        # set the backlog
        if self.args["--backlog"]:
            try:
                self.backlog = int(self.args["--backlog"])
            except ValueError:
                raise ConfigError("backlog should be an integer")

        # parse SSL options
        self.parse_ssl_options()

        # pidfile
        if self.args["--pidfile"] is not None:
            self.pidfile = self.args["--pidfile"]

        if self.args["--daemon"]:
            self.daemonize = True

        if self.args['-v'] > 0:
            self.logfile = "-"

        if self.args['--error-log'] is not None:
            self.logfile = self.args['--error-log']

        if self.args['--log-level'] is not None:
            self.loglevel = self.args['--log-level']

        if self.args['--require-key']:
            self.require_key = True


    def reload(self):
        """ like reload but track removed processes and webhhoks """
        # store the old processes webhooks list
        old_processes = set([(n, s) for n, s, c, p in self.processes])
        old_webhooks = set(self.webhooks)

        # reload the config
        self.load()

        # get all processes & webhooks to remove
        new_processes = set([(n, s) for n, s, c, p in self.processes])
        removed_processes = old_processes.difference(new_processes)
        removed_webhooks = old_webhooks.difference(set(self.webhooks))

        return (removed_processes, removed_webhooks)

    def set_defaults(self):
        self.plugin_dir = self.args["--plugin-dir"]
        self.webhooks = []
        self.processes = []
        self.ssl_options = {}
        self.client_ssl_options = {}
        self.bind = "0.0.0.0:5000"
        self.lookupd_addresses = []
        self.broadcast_address = None
        self.backlog = 128
        self.daemonize = False
        self.pidfile = None
        self.logfile = None
        self.loglevel = "info"

        # auth(z) API
        self.require_key = False
        self.auth_backend = "default"
        self.keys_backend = "default"
        self.auth_dbname = None
        self.keys_dbname = None

    def parse_ssl_options(self):
        ssl_options = {}
        client_ssl_options = {}
        if self.args["--certfile"] is not None:
            ssl_options['certfile'] = self.args["--certfile"]

        if self.args["--keyfile"] is not None:
            ssl_options["keyfile"] = self.args["--keyfile"]

        client_ssl_options = {}
        if self.args["--client-certfile"] is not None:
            ssl_options['certfile'] = self.args["--client-certfile"]

        if self.args["--keyfile"] is not None:
            client_ssl_options["keyfile"] = self.args["--client-keyfile"]

        if self.args.get("--cacert") is not None:
            client_ssl_options["ca_certs"] = self.args["--cacert"]

        # update the SSL configuration previously loaded in the config file
        if self.ssl_options is not None:
            self.ssl_options.update(ssl_options)
        self.client_ssl_options.update(client_ssl_options)

        # no ssl options
        if not self.ssl_options:
            self.ssl_options = None

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

        plugin_dir = cfg.dget('gaffer', 'plugins_dir', "")
        if plugin_dir:
            self.plugin_dir = plugin_dir

        self.bind = cfg.dget('gaffer', 'bind', "0.0.0.0:5000")
        self.broadcast_address = cfg.dget('gaffer', 'broadcast_address')
        self.backlog = cfg.dgetint('gaffer', 'backlog', 128)
        self.daemonize = cfg.dgetboolean('gaffer', 'daemonize', False)
        self.pidfile = cfg.dget('gaffer', 'pidfile')
        self.logfile =  cfg.dget('gaffer', 'error_log', self.logfile)
        self.loglevel = cfg.dget('gaffer', 'log_level', self.loglevel)

        # Collect lookupd addresses
        # they are put in the gaffer section undert the form:
        #
        #    lookupd_address1 = http://127.0.0.1:5010
        #
        self.lookupd_addresses = []
        for k, v in cfg.items('gaffer'):
            if k.startswith('lookupd_address'):
                self.lookupd_addresses.append(v)

        # parse AUTH api
        self.require_key = cfg.dgetboolean('gaffer', 'require_key', True)
        self.auth_backend = cfg.dget('auth', 'auth_backend', 'default')
        self.keys_backend = cfg.dget('auth', 'keys_backend', 'default')
        self.auth_dbname = cfg.dget('auth', 'auth_dbname', None)
        self.keys_dbname = cfg.dget('auth', 'keys_dbname', None)

        processes = []
        webhooks = []
        envs = {}
        for section in cfg.sections():
            if section.startswith('process:') or section.startswith('job:'):
                if section.startswith('process:'):
                    prefix = "process:"
                else:
                    prefix = "job:"

                name = section.split(prefix, 1)[1]
                name, sessionid = self._split_name(name)
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

                    processes.append((name, sessionid, cmd, params))
            elif section == "webhooks":
                for key, val in cfg.items(section):
                    webhooks.append((key, val))
            elif section.startswith('env:'):
                pname = section.split("env:", 1)[1]
                name, sessionid = self._split_name(pname)
                kvs = [(key.upper(), val) for key, val in cfg.items(section)]
                envs[(sessionid, name)] = dict(kvs)
            elif section == "ssl":
                for key, val in cfg.items(section):
                    self.ssl_options[key] = val
            elif section == "lookup_ssl":
                for key, val in cfg.items(section):
                    self.client_ssl_options[key] = val

        # add environment variables
        for name, sessionid, cmd, params in processes:
            if (sessionid, name) in envs:
                params['env'] = envs[(sessionid, name)]

        # sort processes by priority
        processes = sorted(processes, key=lambda p: p[3]['priority'])

        self.webhooks = webhooks
        self.processes = processes

    def _split_name(self, name):
        if "/" in name:
            name, sessionid = name.split("/", 1)
        elif ":" in name:
            name, sessionid = name.split(":", 1)
        elif "." in name:
            name, sessionid = name.split(".", 1)
        else:
            sessionid = "default"
        return name, sessionid
