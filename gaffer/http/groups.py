# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

from .util import CorsHandler


class GroupsHandler(CorsHandler):

    def get(self, *args, **kwargs):
        self.preflight()
        m = self.settings.get('manager')
        groups = m.get_groups()
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(groups))


class GroupHandler(CorsHandler):

    def get(self, *args, **kwargs):
        self.preflight()
        m = self.settings.get('manager')

        group = args[0]
        try:
            names = m.get_group(group)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(names))


    def post(self, *args, **kwargs):
        self.preflight()
        m = self.settings.get('manager')

        group = args[0]
        action = args[1].split('_')[1]

        if action not in ('start', 'stop', 'restart'):
            self.set_status(404)
            self.write({"error": "resource_not_found"})
            return

        func = getattr(m, "%s_group" % action)
        try:
            func(group)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write({"ok": True})

    def delete(self, *args, **kwargs):
        self.preflight()
        m = self.settings.get('manager')

        group = args[0]
        try:
            m.remove_group(group)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write({"ok": True})
