# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
usage: gafferd [--version] [-v | -vv] [-c CONFIG|--config=CONFIG]
               [-p PLUGINS_DIR|--plugin-dir=PLUGINS_DIR]
               [--daemon] [--pidfile=PIDFILE]
               [--bind=ADDRESS] [--lookupd-address=LOOKUP]...
               [--broadcast-address=ADDR]
               [--certfile=CERTFILE] [--keyfile=KEYFILE]
               [--cacert=CACERT]
               [--client-certfile=CERTFILE] [--client-keyfile=KEYFILE]
               [--backlog=BACKLOG]

Args

    CONFIG                    configuration file path

Options

    -h --help                   show this help message and exit
    --version                   show version and exit
    -v -vv                      verbose mode
    -c CONFIG --config=CONFIG   configuration dir
    -p DIR --plugin-dir=DIR     plugin dir
    --daemon                    Start gaffer in daemon mode
    --pidfile=PIDFILE
    --bind=ADDRESS              default HTTP binding (default: 0.0.0.0:5000)
    --lookupd-address=LOOKUP    lookupd HTTP address
    --broadcast-address=ADDR    the address for this node. This is registered
                                with gaffer_lookupd (defaults to OS hostname)
    --broadcast-port=PORT       The port that will be registered with
                                gaffer_lookupd (defaults to local port)
    --certfile=CERTFILE         SSL certificate file for the default binding
    --keyfile=KEYFILE           SSL key file
    --client-certfile=CERTFILE  SSL client certificate file (to connect to the
                                lookup server)
    --client-keyfile=KEYFILE    SSL client key file
    --cacert=CACERT             SSL CA certificate
    --backlog=BACKLOG           default backlog (default: 128).

"""



import fnmatch
try:
    import configparser
except ImportError:
    import ConfigParser as configparser
import os
import sys


import six

from .. import __version__
from ..console_output import ConsoleOutput
from ..docopt import docopt
from ..manager import Manager
from ..pidfile import Pidfile
from ..process import ProcessConfig
from ..sig_handler import SigHandler
from ..state import FlappingInfo
from ..util import daemonize, setproctitle_
from ..webhooks import WebHooks
from .http import HttpHandler
from .plugins import PluginManager
from .util import user_path, system_path, default_path, is_admin

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

        self.config_dir = self.find_configdir()
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        elif not os.path.isdir(self.config_dir):
            raise RuntimeError("%r isn't a directory" % self.config_dir)

        # set default configuration
        self.set_defaults()

        # maybe load the config file
        config_file = os.path.join(self.config_dir, "gaffer.ini")
        if os.path.isfile(config_file):
            self.parse_config(config_file)

        # if the plugin dir hasn't been set yet, set it to the default path
        if not self.plugin_dir:
            if 'GAFFER_PLUGIN_DIR' in os.environ:
                self.plugin_dir = os.environ.get('GAFFER_PLUGIN_DIR')
            else:
                self.plugin_dir = os.path.join(self.config_dir, "plugins")

        # initialize the plugin manager
        self.manager = Manager()
        self.plugin_manager = PluginManager(self.plugin_dir)

    def set_defaults(self):
        self.plugin_dir = self.args["--plugin-dir"]
        self.webhooks = []
        self.processes = []
        self.ssl_options = {}
        self.client_ssl_options = {}
        self.bind = "0.0.0.0:5000"
        self.lookupd_address = []
        self.broadcast_address = None
        self.backlog = 128

    def run(self):
        # check if any plugin dependancy is missing
        self.plugin_manager.check_mandatory()

        # bind address
        bind = self.args['--bind'] or self.bind

        #lookupd address
        lookupd_address = self.args['--lookupd-address']
        if not lookupd_address:
            lookupd_address = self.lookupd_address

        # broadcast address
        broadcast_address = self.args['--broadcast-address']
        if not broadcast_address:
            broadcast_address = self.broadcast_address

        if (broadcast_address is not None and
                not broadcast_address.startswith("http://") and
                not broadcast_address.startswith("https://")):
            raise RuntimeError("invalid broadcast address")



        # setup the http api
        static_sites = self.plugin_manager.get_sites()

        # set the backlog
        if self.args["--backlog"]:
            try:
                backlog = int(self.args["--backlog"])
            except ValueError:
                raise RuntimeError("backlog should be an integer")
        else:
            backlog = self.backlog

        # parse SSL options
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
        self.ssl_options.update(ssl_options)
        self.client_ssl_options.update(client_ssl_options)

        if not self.ssl_options:
            self.ssl_options = None

        http_handler = HttpHandler(uri=bind, lookupd_addresses=lookupd_address,
                broadcast_address=broadcast_address, backlog=backlog,
                ssl_options=self.ssl_options,
                client_ssl_options=self.client_ssl_options,
                handlers=static_sites)

        # setup gaffer apps
        apps = [SigHandler(),
                WebHooks(hooks=self.webhooks),
                http_handler]

        # extend with plugin apps
        plugin_apps = self.plugin_manager.get_apps(self.cfg)
        apps.extend(plugin_apps)

        # verbose mode
        if self.args["-v"] == 2:
            apps.append(ConsoleOutput(actions=['.']))
        elif self.args["-v"] == 1:
            apps.append(ConsoleOutput(output_streams=False))

        self.manager.start(apps=apps)

        # add processes
        for name, sessionid, cmd, params in self.processes:
            if "start" in params:
                start = params.pop("start")
            else:
                start = True

            config = ProcessConfig(name, cmd, **params)
            self.manager.load(config, sessionid=sessionid, start=start)

        # run the main loop
        self.manager.run()

    def find_configdir(self):
        if self.args.get('--config') is not None:
            return self.args.get('--config')

        if 'GAFFER_CONFIG' in os.environ:
            return os.environ.get('GAFFER_CONFIG')

        if is_admin():
            default_paths = system_path()
        else:
            default_paths = user_path()

        for path in default_paths:
            if os.path.isdir(path):
                return path

        return default_path()

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


    def parse_config(self, config_file):
        cfg, cfg_files_read = self.read_config(config_file)
        self.cfg = cfg

        plugin_dir = cfg.dget('gaffer', 'plugins_dir', "")
        if plugin_dir:
            self.plugin_dir = plugin_dir

        address = cfg.dget('gaffer', 'bind', "0.0.0.0")
        port = cfg.dget('gaffer', 'port', "5000")
        self.bind = "%s:%s" % (address, port)

        self.broadcast_address = cfg.dget('gaffer', 'broadcast_address')
        self.backlog = cfg.dgetint('gaffer', 'backlog', 128)

        # parse lookupd addresses
        addresses = {}
        ports = {}

        # Collect lookupd addresses
        # they are put in the gaffer section undert the form:
        #
        #    lookupd_address1 = http://127.0.0.1:5010
        #
        self.lookupd_address = []
        for k, v in cfg.items('gaffer'):
            if k.startswith('lookupd_address'):
                self.lookupd_address.append(v)

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

def run():
    args = docopt(__doc__, version=__version__)

    if args["--daemon"]:
        daemonize()

    setproctitle_("gafferd")

    pidfile = None
    if args["--pidfile"]:
        pidfile = Pidfile(args["--pidfile"])

        try:
            pidfile.create(os.getpid())
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

    try:
        s = Server(args)
        s.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("error: %s" % str(e))
        sys.exit(1)
    finally:
        if pidfile is not None:
            pidfile.unlink()

    sys.exit(0)

if __name__ == "__main__":
    run()
