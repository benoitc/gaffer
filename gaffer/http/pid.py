# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

from .util import CorsHandler


class ProcessIdHandler(CorsHandler):

    def head(self, *args):
        self.preflight()
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        if pid in m.running:
            self.set_status(200)
        else:
            self.set_status(404)


    def get(self, *args):
        self.preflight()
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        if pid in m.running:
            p = m.running[pid]
            try:
                info = m.get_process_info(p.name)
            except KeyError:
                self.set_status(404)
                self.write({"error": "not_found"})
                return
            self.write(info)
        else:
            self.set_status(404)
            self.write({"error": "not_found"})

    def delete(self, *args):
        self.preflight()
        m = self.settings.get('manager')

        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return

        if pid in m.running:
            m.stop_process(pid)
            self.write({"ok": True})
        else:
            self.set_status(404)
            self.write({"error": "not_found"})

class ProcessIdManageHandler(CorsHandler):

    def post(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        try:
            pid = int(args[0])
        except ValueError:
            self.set_status(400)
            self.write({"error": "bad_value"})
            return
        if pid in m.running:
            p = m.running[pid]
            action = args[1]
            if action == "_stop":
                m.stop_process(pid)
            elif action == "_signal":
                if len(args) < 2:
                    self.set_status(400)
                    self.write({"error": "no_signal_number"})
                    return
                else:
                    try:
                        signum = int(args[2])
                    except ValueError:
                        self.set_status(400)
                        self.write({"error": "bad_value"})
                        return
                    m.send_signal(pid, signum)

            self.write({"ok": True})
        else:
            self.set_status(404)
            self.write({"error": "not_found"})
