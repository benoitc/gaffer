# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json


from ..error import ProcessError
from ..process import ProcessConfig
from .util import CorsHandler


class SessionsHandler(CorsHandler):
    """ /sessions """

    def get(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({"sessions": m.sessions}))


class AllJobsHandler(CorsHandler):
    """ /jobs """

    def get(self, *args):
        self.preflight()
        m = self.settings.get('manager')
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({"jobs": m.jobs()}))

class JobsHandler(CorsHandler):
    """ /jobs/<sessionid> """

    def get(self, *args, **kwargs):
        self.preflight()
        m = self.settings.get('manager')
        sessionid = args[0]
        jobs = list(m.jobs(sessionid))

        # send response
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({"sessionid": sessionid,
                               "jobs": jobs}))

    def post(self, *args, **kwargs):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        try:
            name, cmd, settings = self.fetch_body()
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})
            return

        # extract the sessionid from the path.
        sessionid = args[0]

        # do we start the job once the config is loaded? True by default.
        if "start" in settings:
            start = settings.pop("start")
        else:
            start = True

        config = ProcessConfig(name, cmd, **settings)

        # load the config
        m = self.settings.get('manager')
        try:
            m.load(config, sessionid=sessionid, start=start)
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


class JobHandler(CorsHandler):
    """ /jobs/<sessionid>/<label> """

    def head(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            m.get("%s.%s" % (args[0], args[1]))
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
            info = m.info("%s.%s" % (args[0], args[1]))
        except ProcessError:
            self.set_status(404)
            return self.write({"error": "not_found"})

        self.write(info)

    def delete(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        sessionid = args[0]
        name = args[1]

        try:
            m.unload(name, sessionid)
        except ProcessError:
            self.set_status(404)
            return self.write({"error": "not_found"})

        self.write({"ok": True})

    def put(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        sessionid = args[0]
        name = args[1]

        try:
            cmd, settings = self.fetch_body(name)
        except ValueError as e:
            self.set_status(400)
            return self.write({"error": "bad_request", "reason": str(e)})

        # do we start the job once the config is loaded? True by default.
        if "start" in settings:
            start = settings.pop("start")
        else:
            start = True

        # create config object
        config = ProcessConfig(name, cmd, **settings)

        try:
            m.update(config, sessionid=sessionid, start=start)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.set_status(201)
        self.write({"ok": True})


    def fetch_body(self, name):
        settings = json.loads(self.request.body.decode('utf-8'))
        if "cmd" not in settings:
            raise ValueError("invalid process config")

        if 'name' in settings:
            if settings.get('name') != name:
                raise ValueError("template name conflict with the path")

            del settings['name']

        cmd = settings.pop("cmd")
        return cmd, config


class JobStatsHandler(CorsHandler):
    """ /jobs/<sessionid>/<label>/stats """

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            stats = m.stats("%s.%s" % (args[0], args[1]))
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write(stats)


class ScaleJobHandler(CorsHandler):
    """ /jobs/<sessionid>/<label>/numprocesses """

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            t = m._get_locked_state("%s.%s" % (args[0], args[1]))
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"numprocesses": t.numprocesses})

    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            n = self.get_scaling_value()
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})

        try:
            ret = m.scale("%s.%s" % (args[0], args[1]), n)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"numprocesses": ret})

    def get_scaling_value(self):
        obj = json.loads(self.request.body.decode('utf-8'))
        if "scale" not in obj:
            raise ValueError("invalid scaling value")
        return obj['scale']


class PidsJobHandler(CorsHandler):
    """ /jobs/<sessionid>/<label>/pids """

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        appname = args[0]
        name = args[1]

        try:
            pids = m.pids("%s.%s" % (args[0], args[1]))
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"pids": pids})


class SignalJobHandler(CorsHandler):
    """ /<jobs>/<sessionid>/<label>/signal """


    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        try:
            sig = self.get_signal_value()
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})

        try:
             m.kill("%s.%s" % (args[0], args[1]), sig)
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


class StateJobHandler(CorsHandler):

    def get(self, *args):
        self.preflight()

        m = self.settings.get('manager')
        try:
            t = m._get_locked_state("%s.%s" % (args[0], args[1]))
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write(str(int(t.active)))

    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        try:
            do = self.get_action(m)
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})

        try:
            do("%s.%s" % (args[0], args[1]))
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.set_status(202)
        self.write({"ok": True})

    def get_action(self, m):
        state = self.request.body
        if state == b'1':
            do = m.start_job
        elif state == b'0':
            do = m.stop_job
        elif state == b'2':
            do = m.reload
        else:
            raise ValueError("invalid state")
        return do
