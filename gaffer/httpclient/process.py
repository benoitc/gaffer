# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

from ..util import (is_ssl, parse_ssl_options, parse_signal_value)
from .websocket import IOChannel
from .util import make_uri

class Process(object):
    """ Process Id object. It represent a pid """

    def __init__(self, server, pid):
        self.server = server
        self.pid = pid

        # get info
        resp = server.request("get", "/%s" % pid)
        self.info = self.server.json_body(resp)


    def __str__(self):
        return str(self.pid)

    def __getattr__(self, key):
        if key in self.info:
            return self.info[key]

        return object.__getattribute__(self, key)

    @property
    def active(self):
        """ return True if the process is active """
        resp = self.server.request("head", "/%s" % self.pid)
        if resp.code == 200:
            return True
        return False

    @property
    def stats(self):
        resp = self.server.request("get", "/%s/stats" % self.pid)
        obj = self.server.json_body(resp)
        return obj['stats']

    def stop(self):
        """ stop the process """
        self.server.request("delete", "/%s" % self.pid)
        return True

    def kill(self, sig):
        """ Send a signal to the pid """

        # we parse the signal at the client level to reduce the time we pass
        # in the server.
        signum =  parse_signal_value(sig)

        # make the request
        body = json.dumps({"signal": signum})
        headers = {"Content-Type": "application/json"}
        self.server.request("post", "/%s/signal" % self.pid, body=body,
                headers=headers)
        return True

    def socket(self, mode=3, stream=None, heartbeat=None):
        """ return an IO channel to a PID stream. This channek allows you to
        read and write to a stream if the operation is available

        Args:

          - **mode**: Mask of events that will be detected. The possible events
            are pyuv.UV_READABLE or pyuv.UV_WRITABLE.
          - **stream**: stream name as a string. By default it is using STDIO.
          - **hearbeat**: heartbeat in seconds to maintain the connection alive
            [default 15.0s]
        """
        # build connection url
        if stream is None:
            url = make_uri(self.server.uri, '/%s/channel' % self.pid,
                mode=mode)
        else:
            url = make_uri(self.server.uri, '/%s/channel/%s' % (self.pid,
                stream), mode=mode)
        url = "ws%s" % url.split("http", 1)[1]

        # build connection options
        options = {}
        if heartbeat and heartbeat is not None:
            options['heartbeat'] = heartbeat

        # eventually add sll options
        if is_ssl(url):
            options['ssl_options'] = parse_ssl_options(self.server.options)

        return IOChannel(self.server.loop, url, mode=mode,
                api_key=self.server.api_key, **options)
