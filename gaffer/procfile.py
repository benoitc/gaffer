# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

try:
    from collections import OrderedDict
except ImportError:
    from .datastructures import OrderedDict

import os
import re
import shlex

RE_LINE = re.compile(r'^([A-Za-z0-9_]+):\s*(.+)$')

class Procfile(object):

    def __init__(self, procfile, envs=None):
        self.procfile = procfile
        self.root = os.path.dirname(procfile) or "."

        # set default env
        default_env = os.path.join(self.root, '.env')
        self.envs = [default_env]
        if envs is not None:
            self.envs.extend(envs)

        # initialize value
        self.cfg = self.parse(self.procfile)
        self.env = self.get_env(self.envs)

    def processes(self):
        return self.cfg.items()

    def parse(self, procfile):
        cfg = OrderedDict()
        with open(procfile) as f:
            lines = f.readlines()
            for line in lines:
                m = RE_LINE.match(line)
                if m:
                    cfg[m.group(1)] = m.group(2)
        return cfg

    def get_env(self, envs=[]):
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

    def as_dict(self, name):
        cmd, args = self.parse_cmd(self.cfg[name])
        return OrderedDict([("name", name),("cmd",  cmd), ("args", args),
                ("env", self.env)])

    def as_configparser(self):
        """ return a ConfigParser  """

        parser = configparser.ConfigParser()

        ln = 0
        dconf = OrderedDict()
        for k, v in self.cfg.items():
            cmd, args = self.parse_cmd(v)
            dconf["process:%s" % k] = OrderedDict([("name", k), ("cmd", cmd),
                ("args", " ".join(args)), ("priority", ln)])
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
