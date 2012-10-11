# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

from .util import CorsHandler

class ProcessesHandler(CorsHandler):

    def get(self, *args, **kwargs):
        self.preflight()
        m = self.settings.get('manager')
        running = self.get_argument('running', default="")

        if running.lower() == "1" or running == "true":
            processes = [pid for pid in m.running]
        else:
            processes = [name for name in m.processes]

        # send response
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(processes))

    def post(self, *args, **kwargs):
        self.preflight()
        try:
            obj = json.loads(self.request.body.decode('utf-8'))
        except ValueError:
            self.set_status(400)
            self.write({"error": "invalid_json"})
            return

        if not "name" or not "cmd" in obj:
            self.set_status(400)
            self.write({"error": "invalid_process_info"})
            return

        name = obj.pop("name")
        cmd = obj.pop("cmd")

        m = self.settings.get('manager')
        try:
            m.add_process(name, cmd, **obj)
        except KeyError:
            self.set_status(409)
            self.write({"error": "conflict"})
            return

        self.write({"ok": True})

class ProcessHandler(CorsHandler):

    def head(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        name = args[0]
        if name in m.processes:
            self.set_status(200)
        else:
            self.set_status(404)

    def get(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        name = args[0]

        try:
            info = m.get_process_info(name)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write(info)

    def delete(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        name = args[0]

        try:
            m.remove_process(name)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write({"ok": True})

    def put(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        name = args[0]

        try:
            obj = json.loads(self.request.body.decode('utf-8'))
        except ValueError:
            self.set_status(400)
            self.write({"error": "invalid_json"})
            return

        if not "cmd" in obj:
            self.set_status(400)
            self.write({"error": "invalid_process_info"})
            return

        if "name" in obj:
            del obj['name']

        cmd = obj.pop("cmd")
        try:
            m.update(name, cmd, **obj)
        except KeyError:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        self.write({"ok": True})

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

class ProcessManagerHandler(CorsHandler):

    def get(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        name = args[0]

        if name not in m.processes:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        action = args[1]
        extra = {}
        if action == "_pids":
            state = m.processes[name]
            pids = [p.id for p in state.running]
            extra = {"pids": pids}
        else:
            self.set_status(404)
            self.write({"error": "resource_not_found"})
            return

        json_obj = {"ok": True}
        json_obj.update(extra)
        self.write(json_obj)

    def post(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        name = args[0]

        if name not in m.processes:
            self.set_status(404)
            self.write({"error": "not_found"})
            return

        action = args[1]
        extra = {}
        if action == "_start":
            m.start_process(name)
        elif action == "_stop":
            m.stop_process(name)
        elif action == "_add":
            if len(args) > 2:
                i = int(args[2])
            else:
                i = 1
            ret = m.ttin(name, i)
            extra = {"numprocesses": ret}
        elif action == "_sub":
            if len(args) > 2:
                i = int(args[2])
            else:
                i = 1
            ret = m.ttou(name, i)
            extra = {"numprocesses": ret}
        elif action == "_restart":
            m.restart_process(name)
        elif action == "_signal":
            if len(args) < 2:
                self.set_status(400)
                self.write({"error": "no_signal_number"})
                return
            else:
                signum = int(args[2])
            m.send_signal(name, signum)
        else:
            self.set_status(404)
            self.write({"error": "resource_not_found"})
            return

        json_obj = {"ok": True}
        json_obj.update(extra)
        self.write(json_obj)
