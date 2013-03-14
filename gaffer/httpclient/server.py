# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import base64
import json

from ..process import ProcessConfig
from ..util import is_ssl, parse_ssl_options
from .base import  BaseClient
from .process import Process
from .job import Job
from .util import make_uri
from .websocket import GafferSocket


class Server(BaseClient):
    """ Server, main object to connect to a gaffer node. Most of the
    calls are blocking. (but running in the loop) """

    def __init__(self, uri, loop=None, api_key=None, **options):
        super(Server, self).__init__(uri, loop=loop, **options)
        self.api_key = api_key

    def request(self, method, path, headers=None, body=None, **params):
        headers = headers or {}
        # if we have an api key, pass it to the headers
        if self.api_key is not None:
            headers['X-Api-Key'] = self.api_key

        # continue the request
        return super(Server, self).request(method, path, headers=headers,
                body=body, **params)

    def authenticate(self, username, password):
        """ authenticate against a gafferd node to retrieve an api key """
        # set the basic auth header
        auth_hdr = "%s:%s" % (username, password)
        auth_hdr = b"Basic " + base64.b64encode(auth_hdr.encode("utf-8"))
        headers = {"Authorization": auth_hdr.decode("utf-8")}

        # make the request
        resp = self.request("get", "/auth", headers=headers)

        # set the server api key
        self.api_key = self.json_body(resp)["api_key"]

        # return the api key. useful for clients that store it for later.
        return self.api_key

    @property
    def version(self):
        """ get gaffer version """
        resp = self.request("get", "/")
        return self.json_body(resp)['version']

    def running(self):
        resp = self.request("get", "/pids")
        return self.json_body(resp)['pids']

    pids = running

    def ping(self):
        resp = self.request("get", "/ping")
        return resp.body == b'OK'

    def sessions(self):
        """ get list of current sessions """
        resp = self.request("get", "/sessions")
        obj = self.json_body(resp)
        return obj['sessions']

    def jobs(self, sessionid=None):
        if sessionid is None:
            resp = self.request("get", "/jobs")
        else:
            resp = self.request("get", "/jobs/%s" % sessionid)

        return self.json_body(resp)["jobs"]

    def jobs_walk(self, callback, sessionid=None):
        jobs = self.jobs(sessionid)
        for job in jobs:
            sessionid, name = self._parse_name(job)
            callback(self, Job(self, config=name, sessionid=sessionid))

    def job_exists(self, name):
        sessionid, name = self._parse_name(name)
        resp = self.request("head", "/jobs/%s/%s" % (sessionid, name))
        if resp.code == 200:
            return True
        return False


    def load(self, config, sessionid=None, start=True, force=False):
        """  load a process config object.

        Args:

        - **config**: dict or a ``process.ProcessConfig`` instance
        - **sessionid**: Some processes only make sense in certain contexts.
          this flag instructs gaffer to maintain this process in the sessionid
          context. A context can be for example an application. If no session
          is specified the config will be attached to the ``default`` session.
        """

        sessionid = self._sessionid(sessionid)
        headers = {"Content-Type": "application/json" }

        # build config body
        config_dict = config.to_dict()
        config_dict.update({'start': start})
        body = json.dumps(config_dict)

        name = "%s.%s" % (sessionid, config.name)

        if force:
            if self.job_exists(name):
                self.request("put", "/jobs/%s/%s" % (sessionid, config.name),
                        body=body, headers=headers)
            else:
                self.request("post", "/jobs/%s" % sessionid, body=body,
                        headers=headers)
        else:
            self.request("post", "/jobs/%s" % sessionid, body=body,
                        headers=headers)

        return Job(server=self, config=config, sessionid=sessionid)

    def unload(self, name, sessionid=None):
        sessionid = self._sessionid(sessionid)
        self.request("delete", "/jobs/%s/%s" % (sessionid, name))
        return True

    def reload(self, name, sessionid=None):
        sessionid = self._sessionid(sessionid)
        self.request("post", "/jobs/%s/%s/state" % (sessionid, name),
                body="2")
        return True

    def get_job(self, name):
        sessionid, name = self._parse_name(name)
        resp = self.request("get", "/jobs/%s/%s" % (sessionid, name))
        config_dict = self.json_body(resp)['config']
        return Job(server=self, config=ProcessConfig.from_dict(config_dict),
                sessionid=sessionid)

    def get_process(self, pid):
        return Process(server=self, pid=pid)

    def socket(self, heartbeat=None):
        """ return a direct websocket connection to gaffer """
        url0 =  make_uri(self.uri, '/channel/websocket')
        url = "ws%s" % url0.split("http", 1)[1]

        options = {}
        if heartbeat and heartbeat is not None:
            options['heartbeat'] = heartbeat

        if is_ssl(url):
            options['ssl_options'] = parse_ssl_options(self.options)

        return GafferSocket(self.loop, url, api_key=self.api_key, **options)

    def _parse_name(self, name):
        if "." in name:
            sessionid, name = name.split(".", 1)
        elif "/" in name:
            sessionid, name = name.split("/", 1)
        else:
            sessionid = "default"

        return sessionid, name

    def _sessionid(self, session=None):
        if not session:
            return "default"
        return session
