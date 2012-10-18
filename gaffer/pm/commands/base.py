# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy
import textwrap

try:
    from collections import OrderedDict
except ImportError:
    from ...datastructures import OrderedDict

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
        new_class.fmt_desc()
        KNOWN_COMMANDS.append(new_class)
        return new_class

    def fmt_desc(cls):
        desc = textwrap.dedent(cls.__doc__).strip()
        setattr(cls, "desc",  desc)
        setattr(cls, "short", desc.splitlines()[0])

class Command(object):

    name = None
    options = []
    properties = []
    order = 0

    def copy(self):
        return copy.copy(self)


    def run(self, args, opts):
        raise NotImplementedError

    def parse_concurrency(self, pargs):
        if not pargs.concurrency:
            return {}

        settings = {}
        lsettings = pargs.concurrency.split(",")
        for setting in lsettings:
            kv = setting.split("=")
            if len(kv) == 2:
                key = kv[0].strip()
                try:
                    val = int(kv[1].strip())
                except ValueError:
                    continue
                settings[key] = val
        return settings

Command = CommandMeta('Command', (Command,), {})
