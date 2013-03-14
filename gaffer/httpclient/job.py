# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

from ..process import ProcessConfig
from ..util import parse_signal_value

class Job(object):
    """ Job object. Represent a remote job"""

    def __init__(self, server, config=None, sessionid=None):
        self.server = server
        self.sessionid = sessionid or 'default'
        if not isinstance(config, ProcessConfig):
            self.name = config
            self._config = None
        else:
            self.name = config['name']
            self._config = config

    @property
    def config(self):
        if not self._config:
            self._config = self.fetch_config()
        return self._config

    def fetch_config(self):
        resp = self.server.request("get", "/jobs/%s/%s" % (self.sessionid,
             self.name))
        config_dict = self.server.json_body(resp)['config']
        return ProcessConfig.from_dict(config_dict)

    def __str__(self):
        return self.name

    @property
    def active(self):
        """ return True if the process is active """
        resp = self.server.request("get", "/jobs/%s/%s/state" % (
            self.sessionid, self.name))
        if resp.body == b'1':
            return True
        return False

    @property
    def running(self):
        """ return the number of processes running for this template """
        info = self.info()
        return info['running']

    @property
    def running_out(self):
        """ return the number of processes running for this template """
        info = self.info()
        return info['running_out']

    @property
    def numprocesses(self):
        """ return the maximum number of processes that can be launched
        for this template """
        info = self.info()
        return info['max_processes']

    @property
    def pids(self):
        """ return a list of running pids """
        resp = self.server.request("get", "/jobs/%s/%s/pids" % (
            self.sessionid, self.name))
        result = self.server.json_body(resp)
        return result['pids']

    def info(self):
        """ return the process info dict """
        resp = self.server.request("get", "/jobs/%s/%s" % (self.sessionid,
            self.name))
        return self.server.json_body(resp)

    def stats(self):
        """ Return the template stats
        """
        resp = self.server.request("get", "/jobs/%s/%s/stats" %
                (self.sessionid, self.name))
        return self.server.json_body(resp)


    def start(self):
        """ start the process if not started, spawn new processes """
        self.server.request("post", "/jobs/%s/%s/state" % (self.sessionid,
            self.name), body="1")
        return True

    def stop(self):
        """ stop the process """
        self.server.request("post", "/jobs/%s/%s/state" % (self.sessionid,
            self.name), body="0")
        return True

    def restart(self):
        """ restart the process """
        self.server.request("post", "/jobs/%s/%s/state" % (self.sessionid,
            self.name), body="2")
        return True

    def scale(self, num=1):
        body = json.dumps({"scale": num})
        resp = self.server.request("post", "/jobs/%s/%s/numprocesses" % (
            self.sessionid, self.name), body=body)
        result = self.server.json_body(resp)
        return result['numprocesses']


    def commit(self, graceful_timeout=10.0, env=None):
        """ Like ``scale(1) but the process won't be kept alived at the end.
        It is also not handled uring scaling or reaping. """

        env = env or {}
        body = json.dumps({"graceful_timeout": graceful_timeout, "env": env})
        resp = self.server.request("post", "/jobs/%s/%s/commit" % (
            self.sessionid, self.name), body=body)
        result = self.server.json_body(resp)
        return result['pid']

    def kill(self, sig):
        """ send a signal to all processes of this template """

        # we parse the signal at the client level to reduce the time we pass
        # in the server.
        signum =  parse_signal_value(sig)

        body = json.dumps({"signal": signum})
        self.server.request("post", "/jobs/%s/%s/signal" % (self.sessionid,
            self.name), body=body)
        return True
