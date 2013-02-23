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
        KNOWN_COMMANDS.append(new_class)
        return new_class


class Command(object):

    name = None
    short_descr = None
    order = 0

    def copy(self):
        return copy.copy(self)


    def run(self, args, opts):
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

Command = CommandMeta('Command', (Command,), {})
