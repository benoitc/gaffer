# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import signal

import pyuv
import six
from tornado import httpclient

from .tornado_pyuv import IOLoop

if six.PY3:
    import urllib.parse
    quote = urllib.parse.quote
    quote_plus = urllib.parse.quote_plus
    unquote = urllib.parse.unquote
    urlencode = urllib.parse.urlencode
else:
    import urllib
    quote = urllib.quote
    quote_plus = urllib.quote_plus
    unquote = urllib.unquote
    urlencode = urllib.urlencode


class GafferNotFound(Exception):
    """ exception raised on HTTP 404 """

class GafferConflict(Exception):
    """ exption raised on HTTP 409 """


class HTTPClient(object):
    """A blocking HTTP client.

    This interface is provided for convenience and testing; most applications
    that are running an IOLoop will want to use `AsyncHTTPClient` instead.
    Typical usage looks like this::

        http_client = httpclient.HTTPClient()
        try:
            response = http_client.fetch("http://www.google.com/")
            print response.body
        except httpclient.HTTPError, e:
            print "Error:", e
    """
    def __init__(self, async_client_class=None, loop=None, **kwargs):
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

class Server(object):

    def __init__(self, uri=None, loop=None, **options):
        self.loop = loop or pyuv.Loop()
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
                else:
                    raise
            else:
                if e.response is not None:
                    resp = e.response
                else:
                    raise

        return resp

    def json_body(self, resp):
        return json.loads(resp.body.decode('utf-8'))

    @property
    def version(self):
        resp = self.request("get", "/")
        return self.json_body(resp)['version']

    def processes(self):
        resp = self.request("get", "/processes")
        return self.json_body(resp)

    def running(self):
        resp = self.request("get", "/processes", running="true")
        return self.json_body(resp)

    def get_process(self, name_or_id):
        resp = self.request("get", "/processes/%s" % name_or_id)
        process = self.json_body(resp)

        if isinstance(name_or_id, int):
            return ProcessId(server=self, pid=name_or_id, process=process)

        return Process(server=self, process=process)

    def is_process(self, name):
        resp = self.request("head", "/processes/%s" % name)
        if resp.code == 200:
            return True
        return False

    def save_process(self, name, cmd, **kwargs):
        if "_force_update" in kwargs:
            force = kwargs.pop("_force_update")

        process = { "name": name, "cmd": cmd }
        process.update(kwargs)

        body = json.dumps(process)
        headers = {"Content-Type": "application/json" }

        if force:
            if self.is_process(name):
                self.request("put", "/processes/%s" % name, body=body,
                        headers=headers)
            else:
                self.request("post", "/processes", body=body,
                        headers=headers)
        else:
            self.request("post", "/processes", body=body,
                        headers=headers)

        return Process(server=self, process=process)

    def add_process(self, name, cmd, **kwargs):
        kwargs["_force_update"] = False
        return self.save_process(name, cmd, **kwargs)

    def update_process(self, name, cmd, **kwargs):
        kwargs["_force_update"] = True
        return self.save_process(name, cmd, **kwargs)

    def remove_process(self, name):
        self.request("delete", "/processes/%s" % name)
        return True

    def send_signal(self, name_or_id, num_or_str):
        if isinstance(num_or_str, six.string_types):
            signame = num_or_str.upper()
            if not signame.startswith('SIG'):
                signame = "SIG%s" % signame
            try:
                signum = getattr(signal, signame)
            except AttributeError:
                raise ValueError("invalid signal name")
        else:
            signum = num_or_str

        self.request('post', "/processes/%s/_signal/%s" % (name_or_id,
            signum))

        return True


class ProcessId(object):

    def __init__(self, server, pid, process):
        self.server = server
        self.pid = pid

        if isinstance(process, dict):
            self.process = process
        else:
            self.process = server.get_process(process)

    def __str__(self):
        return str(self.pid)

    @property
    def active(self):
        resp = self.server.head("get", "/processes/%s" % self.pid)
        if resp.code == 200:
            return True
        return False

    def stop(self):
        self.server.request("post", "/processes/%s/_stop" % self.pid)
        return True

    def signal(self, num_or_str):
        if isinstance(num_or_str, six.string_types):
            signame = num_or_str.upper()
            if not signame.startswith('SIG'):
                signame = "SIG%s" % signame
            try:
                signum = getattr(signal, signame)
            except AttributeError:
                raise ValueError("invalid signal name")
        else:
            signum = num_or_str

        self.server.request("post", "/processes/%s/_signal/%s" %
                (self.pid, signum))
        return True

class Process(object):

    def __init__(self, server, process):
        self.server = server

        if isinstance(process, dict):
            self.process = process
        else:
            self.process = server.get_process(process)

    def __str__(self):
        return self.process.get('name')

    def __getattr__(self, key):
        if key in self.process:
            return self.process[key]
        try:
            return self.__dict__[key]
        except KeyError as e:
            raise AttributeError(str(e))

    @property
    def active(self):
        status = self.status()
        return status['active']

    @property
    def running(self):
        status = self.status()
        return status['running']

    @property
    def numprocesses(self):
        status = self.status()
        return status['max_processes']

    @property
    def pids(self):
        resp = self.server.request("get", "/processes/%s/_pids" %
                self.process['name'])

        result = self.server.json_body(resp)
        return result['pids']

    def info(self):
        return self.process

    def status(self):
        resp = self.server.request("get", "/status/%s" % self.process['name'])
        return self.server.json_body(resp)


    def start(self):
        self.server.request("post", "/processes/%s/_start" %
                self.process['name'])
        return True

    def stop(self):
        self.server.request("post", "/processes/%s/_stop" %
                self.process['name'])
        return True

    def restart(self):
        self.server.request("post", "/processes/%s/_restart" %
                self.process['name'])
        return True

    def add(self, num=1):
        resp = self.server.request("post", "/processes/%s/_add/%s" %
                (self.process['name'], num))

        obj = self.server.json_body(resp)
        return obj['numprocesses']

    def sub(self, num=1):
        resp = self.server.request("post", "/processes/%s/_sub/%s" %
                (self.process['name'], num))

        obj = self.server.json_body(resp)
        return obj['numprocesses']

    def signal(self, num_or_str):
        if isinstance(num_or_str, six.string_types):
            signame = num_or_str.upper()
            if not signame.startswith('SIG'):
                signame = "SIG%s" % signame
            try:
                signum = getattr(signal, signame)
            except AttributeError:
                raise ValueError("invalid signal name")
        else:
            signum = num_or_str

        self.server.request("post", "/processes/%s/_signal/%s" %
                (self.process['name'], signum))
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
