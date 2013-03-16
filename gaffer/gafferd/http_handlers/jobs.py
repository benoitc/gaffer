# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
from tornado.web import HTTPError

from ...error import ProcessError
from ...process import ProcessConfig
from .util import CorsHandler, CorsHandlerWithAuth


class SessionsHandler(CorsHandlerWithAuth):
    """ /sessions """

    def get(self, *args):
        self.preflight()

        if (not self.api_key.is_admin() and
                not self.api_key.can_manage_all()):
            raise HTTPError(403)

        m = self.settings.get('manager')
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({"sessions": m.sessions}))


class AllJobsHandler(CorsHandlerWithAuth):
    """ /jobs """

    def get(self, *args):
        self.preflight()

        if (not self.api_key.is_admin() and
                not self.api_key.can_manage_all()):
            raise HTTPError(403)

        m = self.settings.get('manager')
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({"jobs": m.jobs()}))

class JobsHandler(CorsHandlerWithAuth):
    """ /jobs/<sessionid> """

    def get(self, *args, **kwargs):
        self.preflight()
        m = self.settings.get('manager')
        sessionid = args[0]

        if not self.api_key.can_manage(sessionid):
            raise HTTPError(403)

        try:
            jobs = list(m.jobs(sessionid))
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())


        # send response
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({"sessionid": sessionid,
                               "jobs": jobs}))

    def post(self, *args, **kwargs):
        self.preflight()

        # extract the sessionid from the path.
        sessionid = args[0]

        if not self.api_key.can_manage(sessionid):
            raise HTTPError(403)

        self.set_header('Content-Type', 'application/json')
        try:
            name, cmd, settings = self.fetch_body()
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})
            return

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


class JobHandler(CorsHandlerWithAuth):
    """ /jobs/<sessionid>/<label> """

    def head(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        pname = "%s.%s" % (args[0], args[1])

        if not self.api_key.can_read(pname):
            raise HTTPError(403)

        try:
            m.get(pname)
        except ProcessError:
            return self.set_status(404)

        self.set_status(200)

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        pname = "%s.%s" % (args[0], args[1])

        if not self.api_key.can_read(pname):
            raise HTTPError(403)

        try:
            info = m.info(pname)
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

        if not self.api_key.can_manage("%s.%s" % (sessionid, name)):
            raise HTTPError(403)

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

        if not self.api_key.can_manage("%s.%s" % (sessionid, name)):
            raise HTTPError(403)

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
        config = json.loads(self.request.body.decode('utf-8'))
        if "cmd" not in config:
            raise ValueError("invalid process config")

        if 'name' in config:
            if config.get('name') != name:
                raise ValueError("template name conflict with the path")

            del config['name']

        cmd = config.pop("cmd")
        return cmd, config


class JobStatsHandler(CorsHandlerWithAuth):
    """ /jobs/<sessionid>/<label>/stats """

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        pname = "%s.%s" % (args[0], args[1])

        if not self.api_key.can_read(pname):
            raise HTTPError(403)
        try:
            stats = m.stats(pname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write(stats)


class ScaleJobHandler(CorsHandlerWithAuth):
    """ /jobs/<sessionid>/<label>/numprocesses """

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        pname = "%s.%s" % (args[0], args[1])

        if not self.api_key.can_read(pname):
            raise HTTPError(403)

        try:
            t = m._get_locked_state()
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"numprocesses": t.numprocesses})

    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        pname = "%s.%s" % (args[0], args[1])

        if not self.api_key.can_manage(pname):
            raise HTTPError(403)

        try:
            n = self.get_scaling_value()
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})

        try:
            ret = m.scale(pname, n)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"numprocesses": ret})

    def get_scaling_value(self):
        obj = json.loads(self.request.body.decode('utf-8'))
        if "scale" not in obj:
            raise ValueError("invalid scaling value")
        return obj['scale']


class PidsJobHandler(CorsHandlerWithAuth):
    """ /jobs/<sessionid>/<label>/pids """

    def get(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        pname = "%s.%s" % (args[0], args[1])

        if not self.api_key.can_read(pname):
            raise HTTPError(403)

        try:
            pids = m.pids(pname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"pids": pids})


class SignalJobHandler(CorsHandlerWithAuth):
    """ /<jobs>/<sessionid>/<label>/signal """


    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        pname = "%s.%s" % (args[0], args[1])

        if not self.api_key.can_manage(pname):
            raise HTTPError(403)

        try:
            m.kill(pname, self.get_signal_value())
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})
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


class StateJobHandler(CorsHandlerWithAuth):

    def get(self, *args):
        self.preflight()

        m = self.settings.get('manager')
        pname = "%s.%s" % (args[0], args[1])

        if not self.api_key.can_read(pname):
            raise HTTPError(403)

        try:
            t = m._get_locked_state(pname)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write(str(int(t.active)))

    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')
        pname = "%s.%s" % (args[0], args[1])

        if not self.api_key.can_manage(pname):
            raise HTTPError(403)

        try:
            do = self.get_action(m)
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})

        try:
            do(pname)
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


class CommitJobHandler(CorsHandlerWithAuth):
    """ /jobs/<sessionid>/<label>/commit """


    def post(self, *args):
        self.preflight()
        self.set_header('Content-Type', 'application/json')
        m = self.settings.get('manager')

        if not self.api_key.can_manage(args[0]):
            raise HTTPError(403)

        try:
            graceful_timeout, env = self.get_params()
        except ValueError:
            self.set_status(400)
            return self.write({"error": "bad_request"})

        try:
            pid = m.commit("%s.%s" % (args[0], args[1]),
                    graceful_timeout=graceful_timeout, env=env)
        except ProcessError as e:
            self.set_status(e.errno)
            return self.write(e.to_dict())

        self.write({"pid": pid})

    def get_params(self):
        obj = json.loads(self.request.body.decode('utf-8'))
        env = obj.get('env')
        graceful_timeout = obj.get('graceful_timeout')
        if graceful_timeout is not None:
            try:
                graceful_timeout = int(obj.get('graceful_timeout'))
            except TypeError as e:
                raise ValueError(str(e))
        return graceful_timeout, env
