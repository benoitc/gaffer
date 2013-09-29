# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import OrderedDict
import copy
import json
import os
import re
import sys

try:
    input = raw_input
except NameError:
    pass

KNOWN_COMMANDS = []
def get_commands():
    commands = OrderedDict()
    for c in KNOWN_COMMANDS:
        cmd = c()
        commands[c.name] = cmd.copy()
    return commands

class CommandMeta(type):

    def __new__(cls, name, bases, attrs):
        super_new = type.__new__
        parents = [b for b in bases if isinstance(b, CommandMeta)]
        if not parents:
            return super_new(cls, name, bases, attrs)
        attrs["order"] = len(KNOWN_COMMANDS)
        new_class = super_new(cls, name, bases, attrs)
        KNOWN_COMMANDS.append(new_class)
        return new_class

VALID_APPNAME = re.compile(r'^[a-z][a-z0-9_+-]*$')

class Command(object):

    name = None
    short_descr = None
    order = 0

    def copy(self):
        return copy.copy(self)

    def run(self, config, args):
        raise NotImplementedError

    def parse_concurrency(self, args):
        if not args["--concurrency"]:
            return {}

        settings = {}
        for setting in args["--concurrency"]:
            kv = setting.split("=")
            if len(kv) == 2:
                key = kv[0].strip()
                try:
                    val = int(kv[1].strip())
                except ValueError:
                    continue
                settings[key] = val
        return settings

    def default_appname(self, config, args):
        if args['--app']:
            appname = args['--app']

            # appname is relative to current dir
            if appname == ".":
                if config.use_procfile:
                    appname = config.procfile.get_appname()
                else:
                    appname = os.path.split(os.getcwd())[1]

        elif config.procfile is not None:
            appname = config.procfile.get_appname()
        else:
            appname = "default"

        if not VALID_APPNAME.match(appname):
            raise ValueError("Invalid APP name: %r" % appname)

        return appname

    def parse_name(self, name, default="default"):
        if "." in name:
            appname, name = name.split(".", 1)
        elif "/" in name:
            appname, name = name.split("/", 1)
        else:
            appname = default

        return appname, name

    def use_procfile(self, config, appname):
        return (config.use_procfile and
                appname == config.procfile.get_appname())

    def confirm(self, prompt, resp=True):
        if resp:
            prompt = '%s [%s]|%s: ' % (prompt, 'y', 'n')
        else:
            prompt = '%s [%s]|%s: ' % (prompt, 'n', 'y')

        while True:
            ret = input(prompt).lower()
            if not ret:
                return resp

            if ret not in ('y', 'n'):
                print('please enter y or n.')
                continue

            if ret == "y":
                return True

            return False

    def load_jsonconfig(self, fname):
        if fname == "-":
            content = []
            while True:
                data = sys.stdin.readline()
                if not data:
                    break
                content.append(data)
            content = ''.join(content)
        else:
            if not os.path.isfile(fname):
                raise RuntimeError("%r not found" % fname)

            with open(fname, 'rb') as f:
                content = f.read()

        if isinstance(content, bytes):
            content = content.decode('utf-8')

        # parse the config
        obj = json.loads(content)
        if "jobs" in obj:
            configs = obj['jobs']
        else:
            configs = [obj]

        return configs

Command = CommandMeta('Command', (Command,), {})
