# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json


from ..error import ProcessError
from .util import CorsHandler


class AllApplicationsHandler(CorsHandler):
    """ /apps """

    def get(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({"apps": m.all_apps()}))


class TemplatesHandler(CorsHandler):
    """ /<apps>/<appname> """

    def get(self, *args, **kwargs):
        self.preflight()
        m = self.settings.get('manager')
        appname = args[0]
        templates = list(m.get_templates(appname))

        # send response
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({"appname": appname,
                               "templates": templates}))

    def post(self, *args, **kwargs):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        try:
            name, cmd, settings = self.fetch_body()
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})
            return

        # set the application name
        settings['appname'] = args[0]

        # store the template
        m = self.settings.get('manager')
        try:
            m.add_template(name, cmd, **settings)
        except ProcessError as e :
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"ok": True})

    def fetch_body(self):
        obj = json.loads(self.request.body.decode('utf-8'))
        if not "name" or not "cmd" in obj:
            raise ValueError

        name = obj.pop("name")
        cmd = obj.pop("cmd")
        return name, cmd, obj


class TemplateHandler(CorsHandler):
    """ /<apps>/<appname>/<template> """

    def head(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        appname = args[0]
        name = args[1]

        try:
            m.get_template(name, appname)
        except ProcessError:
            return self.set_status(404)

        self.set_status(200)

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        appname = args[0]
        name = args[1]


        try:
            info = m.get_template_info(name, appname)
        except ProcessError:
            self.set_status(404)
            return self.write({"error": "not_found"})

        self.write(info)

    def delete(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            m.remove_template(name, appname)
        except ProcessError:
            self.set_status(404)
            return self.write({"error": "not_found"})

        self.write({"ok": True})

    def put(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            cmd, settings = self.fetch_body(name, appname)
        except ValueError as e:
            self.set_status(400)
            return self.write({"error": "bad_request", "reason": str(e)})

        try:
            m.update(name, cmd, appname=appname, **settings)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.set_status(201)
        self.write({"ok": True})


    def fetch_body(self, name, appname):
        obj = json.loads(self.request.body.decode('utf-8'))
        if "cmd" not in obj:
            raise ValueError("invalid template")

        if obj.get('appname') !=  appname:
            raise ValueError("application name conflict with the path")

        if obj.get('name') != name:
            raise ValueError("template name conflict with the path")

        del obj['name']
        del obj['appname']

        cmd = obj.pop("cmd")
        return cmd, obj


class TemplateStatsHandler(CorsHandler):
    """ /<apps>/<appname>/<template>/stats """

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            stats = m.get_template_stats(name, appname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write(stats)


class ScaleTemplateHandler(CorsHandler):
    """ /<apps>/<appname>/<template>/numprocesses """

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            t = m.get_template(name, appname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"numprocesses": t.numprocesses})

    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            n = self.get_scaling_value()
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})

        try:
            ret = m.scale(name, n, appname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"numprocesses": n})

    def get_scaling_value(self):
        obj = json.loads(self.request.body.decode('utf-8'))
        if "scale" not in obj:
            raise ValueError("invalid scaling value")
        return obj['scale']


class PidsTemplateHandler(CorsHandler):
    """ /<apps>/<appname>/<template>/pids """

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            t = m.get_template(name, appname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"pids": t.pids})


class SignalTemplateHandler(CorsHandler):
    """ /<apps>/<appname>/<template>/signal """


    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            sig = self.get_signal_value()
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})

        try:
             m.send_signal(name, sig, appname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())


        self.send_status(202)
        self.write({"ok": True})

    def get_signal_value(self):
        obj = json.loads(self.request.body.decode('utf-8'))
        if "signal" not in obj:
            raise ValueError("invalid signal value")
        return obj['signal']


class StateTemplateHandler(CorsHandler):

    def get(self, *args):
        self.preflight()

        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            t = m.get_template(name, appname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write(str(int(t.active)))

    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            do = self.get_action(m)
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})

        try:
            do(name, appname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.set_status(202)
        self.write({"ok": True})

    def get_action(self, m):
        state = self.request.body
        if state == b'1':
            do = m.start_template
        elif state == b'0':
            do = m.stop_template
        elif state == b'2':
            do = m.restart_template
        else:
            raise ValueError("invalid state")
        return do
