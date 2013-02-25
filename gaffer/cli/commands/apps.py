# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command


class Apps(Command):
    """
    usage: gaffer apps

    """

    name = "apps"
    short_desc = "list of applications"

    def run(self, config, args):
        sessions = config.server.sessions()
        for session in sessions:
            print(session)
