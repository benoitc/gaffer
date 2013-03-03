# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
module to parse and manage a Procfile
"""

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

from collections import OrderedDict
import os
import re
import shlex

RE_LINE = re.compile(r'^([A-Za-z0-9_]+):\s*(.+)$')

class Procfile(object):
    """ Procfile object to parse a procfile and a list of given
    environnment files. """

    def __init__(self, procfile, root=None, envs=None):
        """ main constructor

        Attrs:

        - **procfile**: procfile path
        - **evs**: list of .envs paths, each envs will be added tho the
          global procfile environment"""

        self.procfile = procfile

        if not root:
            self.root = os.path.dirname(procfile) or "."
        else:
            self.root = root

        # set default env
        default_env = os.path.join(self.root, '.env')
        self.envs = [default_env]
        if envs is not None:
            self.envs.extend(envs)

        # initialize value
        self.cfg = self.parse(self.procfile)
        self.env = get_env(self.envs)

        self.redirect_input = []
        self.uid = None
        self.gid = None

        for k, v in self.env.items():
            if k == "GAFFER_UID":
                self.uid = v
            elif k == "GAFFER_GID":
                self.gid = v
            elif k == "GAFFER_REDIRECT_INPUT":
                self.redirect_input = v.split()

        # used to cache the appname
        self._appname = None

    def processes(self):
        """ iterator over the configuration """
        return self.cfg.items()

    def parse(self, procfile):
        """ main function to parse a procfile. It returns a dict """
        cfg = OrderedDict()
        with open(procfile) as f:
            lines = f.readlines()
            for line in lines:
                m = RE_LINE.match(line)
                if m:
                    cfg[m.group(1)] = m.group(2)
        return cfg

    def get_appname(self):
        if not self._appname:
            if self.root == ".":
                path = os.getcwd()
            else:
                path = self.root
            self._appname = os.path.split(path)[1]

        return self._appname

    def as_dict(self, name, concurrency_settings=None):
        """ return a procfile line as a JSON object usable with
        the command ``gafferctl load`` . """

        cmd, args = self.parse_cmd(self.cfg[name])
        concurrency_settings = concurrency_settings or {}

        return OrderedDict([("name", name),("cmd",  cmd),
            ("args", args),("env", self.env),
            ('numprocesses', concurrency_settings.get(name, 1))])

    def as_configparser(self, concurrency_settings=None):
        """ return a ConfigParser object. It can be used to generate a
        gafferd setting file or a configuration file that can be
        included. """

        parser = configparser.ConfigParser()
        concurrency_settings = concurrency_settings or {}

        ln = 0
        dconf = OrderedDict()
        for k, v in self.cfg.items():
            cmd, args = self.parse_cmd(v)
            name = "%s:%s" % (self.get_appname(), k)

            dconf["process:%s" % name] = OrderedDict([("cmd", cmd),
                ("args", " ".join(args)), ("priority", ln),
                ('numprocesses', concurrency_settings.get(k, 1))])
            ln += 1

        parser.read_dict(dconf)
        return parser

    def parse_cmd(self, v):
        args_ = shlex.split(v)
        cmd = args_[0]
        if len(args_) > 1:
            args = args_[1:]
        else:
            args = []
        return cmd, args


def get_env(envs=[]):
    env = {}
    for path in envs:
        if os.path.isfile(path):
            with open(path, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    p = line.split('=', 1)
                    if len(p) == 2:
                        k, v = p
                        # remove double quotes
                        v = v.strip('\n').replace('\"','')
                        env[k] = v
    return env
