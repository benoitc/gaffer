# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
Gaffer provides you a simple Client to control a gaffer node via HTTP.

Example of usage::

    import pyuv

    from gaffer.httpclient import Server

    # initialize a loop
    loop = pyuv.Loop.default_loop()

    s = Server("http://localhost:5000", loop=loop)

    # add a process without starting it
    process = s.add_process("dummy", "/some/path/to/dummy/script", start=False)

    # start a process
    process.start()

    # increase the number of process by 2 (so 3 will run)
    process.add(2)

    # stop all processes
    process.stop()

    loop.run()

"""


import json

import six
from tornado import httpclient

from .eventsource import Watcher
from .loop import patch_loop, get_loop
from .process import ProcessConfig
from .tornado_pyuv import IOLoop
from .util import (quote, quote_plus, parse_signal_value, is_ssl,
        parse_ssl_options)
from .websocket import GafferSocket, IOChannel


class GafferNotFound(Exception):
    """ exception raised on HTTP 404 """

class GafferConflict(Exception):
    """ exption raised on HTTP 409 """

class GafferUnauthorized(Exception):
    """ exception raised on HTTP 401 """

class GafferForbidden(Exception):
    """ exception raised on HTTP 403 """


class HTTPClient(object):
    """A blocking HTTP client.

    This interface is provided for convenience and testing; most applications
    that are running an IOLoop will want to use `AsyncHTTPClient` instead.
    Typical usage looks like this::

        http_client = httpclient.HTTPClient()
        try:
            response = http_client.fetch("http://www.friendpaste.com/")
            print response.body
        except httpclient.HTTPError as e:
            print("Error: %s" % e)
    """
    def __init__(self, async_client_class=None, loop=None, **kwargs):
        self.loop = patch_loop(loop)
        self._io_loop = IOLoop(_loop=loop)
        if async_client_class is None:
            async_client_class = httpclient.AsyncHTTPClient
        self._async_client = async_client_class(self._io_loop, **kwargs)
        self._response = None
        self._closed = False

    def __del__(self):
        self.close()

    def close(self):
        """Closes the HTTPClient, freeing any resources used."""
        if not self._closed:
            self._async_client.close()
            self._io_loop.close(True)
            self._closed = True

    def fetch(self, request, **kwargs):
        """Executes a request, returning an `HTTPResponse`.

        The request may be either a string URL or an `HTTPRequest` object.
        If it is a string, we construct an `HTTPRequest` using any additional
        kwargs: ``HTTPRequest(request, **kwargs)``

        If an error occurs during the fetch, we raise an `HTTPError`.
        """
        def callback(response):
            self._response = response
            self._io_loop.stop()
        self._async_client.fetch(request, callback, **kwargs)
        self._io_loop.start()
        response = self._response
        self._response = None
        response.rethrow()
        return response

class BaseClient(object):
    """ base resource object used to abstract request call and response
    retrieving """

    def __init__(self, uri, loop=None, **options):
        if loop is not None:
            self.loop = patch_loop(loop)
        else:
            self.loop = get_loop()

        self.uri = uri
        self.options = options
        self.client = HTTPClient(loop=loop)

    def request(self, method, path, headers=None, body=None, **params):
        headers = headers or {}
        headers.update({"Accept": "application/json"})
        url = make_uri(self.uri, path, **params)
        method = method.upper()
        if (body is None) and method in ("POST", "PATCH", "PUT"):
            body = ""

        try:
            resp = self.client.fetch(url, method=method, headers=headers,
                    body=body, **self.options)
        except httpclient.HTTPError as e:
            if method != "HEAD":
                # only raise on non head method since we are using head to
                # check status and so on.

                if e.code == 404:
                    raise GafferNotFound(self.json_body(e.response))
                elif e.code == 409:
                    raise GafferConflict(self.json_body(e.response))
                elif e.code == 401:
                    raise GafferUnauthorized(self.json_body(e.response))
                elif e.code == 403:
                    raise GafferForbidden(self.json_body(e.response))
                else:
                    raise
            else:
                if e.response is not None:
                    resp = e.response
                else:
                    raise
        return resp

    def json_body(self, resp):
        respbody = resp.body.decode('utf-8')
        try:
            return json.loads(respbody)
        except ValueError:
            return respbody


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

    def get_watcher(self, heartbeat="true"):
        """ return a watcher to listen on /watch """
        url =  make_uri(self.uri, '/watch', feed='eventsource',
                heartbeat=str(heartbeat))

        return Watcher(self.loop, url, **self.options)

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

# ----------- helpers

def url_quote(s, charset='utf-8', safe='/:'):
    """URL encode a single string with a given encoding."""
    if isinstance(s, six.text_type):
        s = s.encode(charset)
    elif not isinstance(s, str):
        s = str(s)
    return quote(s, safe=safe)


def url_encode(obj, charset="utf8", encode_keys=False):
    items = []
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            items.append((k, v))
    else:
        items = list(items)

    tmp = []
    for k, v in items:
        if encode_keys:
            k = encode(k, charset)

        if not isinstance(v, (tuple, list)):
            v = [v]

        for v1 in v:
            if v1 is None:
                v1 = ''
            elif six.callable(v1):
                v1 = encode(v1(), charset)
            else:
                v1 = encode(v1, charset)
            tmp.append('%s=%s' % (quote(k), quote_plus(v1)))
    return '&'.join(tmp)

def encode(v, charset="utf8"):
    if isinstance(v, six.text_type):
        v = v.encode(charset)
    else:
        v = str(v)
    return v


def make_uri(base, *args, **kwargs):
    """Assemble a uri based on a base, any number of path segments,
    and query string parameters.

    """

    # get encoding parameters
    charset = kwargs.pop("charset", "utf-8")
    safe = kwargs.pop("safe", "/:")
    encode_keys = kwargs.pop("encode_keys", True)

    base_trailing_slash = False
    if base and base.endswith("/"):
        base_trailing_slash = True
        base = base[:-1]
    retval = [base]

    # build the path
    _path = []
    trailing_slash = False
    for s in args:
        if s is not None and isinstance(s, six.string_types):
            if len(s) > 1 and s.endswith('/'):
                trailing_slash = True
            else:
                trailing_slash = False
            _path.append(url_quote(s.strip('/'), charset, safe))

    path_str =""
    if _path:
        path_str = "/".join([''] + _path)
        if trailing_slash:
            path_str = path_str + "/"
    elif base_trailing_slash:
        path_str = path_str + "/"

    if path_str:
        retval.append(path_str)

    params_str = url_encode(kwargs, charset, encode_keys)
    if params_str:
        retval.extend(['?', params_str])

    return ''.join(retval)
