# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import os
import ssl
import sys

import pyuv

from ..events import EventEmitter
from ..httpclient.base import BaseClient
from ..httpclient.util import make_uri
from ..httpclient.websocket import WebSocket
from ..util import is_ssl, parse_ssl_options

class LookupChannel(WebSocket):

    def __init__(self, server, url, **kwargs):
        self.server = server
        loop = server.loop

        try:
            self.heartbeat_timeout = kwargs.pop('heartbeat')
        except KeyError:
            self.heartbeat_timeout = 15.0

        self._heartbeat = pyuv.Timer(loop)
        self._emitter = EventEmitter(loop)

        super(LookupChannel, self).__init__(loop, url, **kwargs)

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self.server.url)

    def bind(self, event, callback):
        self._emitter.subscribe(event, callback)

    def unbind(self, event, callback):
        self._emitter.unsubscribe(event, callback)

    def bind_all(self, callback):
        self._emitter.subscribe(".", callback)

    def unbind_all(self, callback):
        self._emitter.unsubscribe(".", callback)

    def close(self):
        self._emitter.close()
        super(LookupChannel, self).close()

    ## websockets methods

    def on_open(self):
        # start the heartbeat
        self._heartbeat.start(self.on_heartbeat, self.heartbeat_timeout,
                self.heartbeat_timeout)
        self._heartbeat.unref()

    def on_close(self):
        self._heartbeat.stop()
        self._emitter.close()

    def on_message(self, message):
        try:
            event = json.loads(message)
        except ValueError:
            return

        if "event" in event:
            self._emitter.publish(event['event'], event)

    def on_heartbeat(self, h):
        self.ping()


class LookupServer(BaseClient):

    @property
    def version(self):
        """ get the lookupd server version """
        resp = self.request("get", "/")
        return self.json_body(resp)['version']

    def ping(self):
        """ ping the lookupd server """
        resp = self.request("get", "/ping")
        return resp.body == b'OK'

    def nodes(self):
        """ get the list of nodes registered to this lookupd server """
        resp = self.request("get", "/nodes")
        return self.json_body(resp)

    def sessions(self, by_node='*'):
        """ get all sessions registered to this lookupd server """
        path = "/sessions"
        if by_node != '*':
            path = "%s/%s" % (path, by_node)
        resp = self.request("get", path)
        return self.json_body(resp)

    def jobs(self):
        """ get all jobs registered to this lookupd server """
        resp = self.request("get", "/jobs")
        return self.json_body(resp)

    def find_job(self, job_name):
        """ find a job on this lookupd server """
        resp = self.request("get", "/findJob", name=job_name)
        return self.json_body(resp)

    def find_session(self, sessionid):
        """ find all jobs for a session on this lookupd server """
        resp = self.request("get", "/findSession", sessionid=sessionid)
        return self.json_body(resp)

    def lookup(self, heartbeat=None):
        """ return a direct websocket connection this node allowing you to
        listen on events.

        Events are:

        - add_node
        - remove_node
        - add_job
        - remove_job
        - add_process
        - remove_process
        """

        url0 = make_uri(self.uri, "/lookup/websocket")
        url = "ws%s" % url0.split("http", 1)[1]
        options = {}
        if heartbeat and heartbeat is not None:
            options['heartbeat'] = heartbeat

        if is_ssl(url):
            options['ssl_options'] = parse_ssl_options(self.options)

        channel = LookupChannel(self, url, **options)
        return channel
