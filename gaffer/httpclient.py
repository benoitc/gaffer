# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import signal

from tornado import httpclient

import six

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


class Server(object):

    def __init__(self, uri=None, **options):
        self.uri = uri
        self.options = options
        self.client = httpclient.HTTPClient()

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

    def get_process(self, name):
        resp = self.request("get", "/processes/%s" % name)
        process = self.json_body(resp)
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
                resp = self.request("put", "/%s %name", body=body,
                        headers=headers)
            else:
                resp = self.request("post", "/processes", body=body,
                        headers=headers)
        else:
            resp = self.request("post", "/processes", body=body,
                        headers=headers)

        return Process(server=self, process=process)

    def add_process(self, name, cmd, **kwargs):
        kwargs["_force_update"] = False
        return self.save_process(name, cmd, **kwargs)

    def update_process(self, name, cmd, **kwargs):
        kwargs["_force_update"] = True
        return self.save_process(name, cmd, **kwargs)

    def remove_process(self, name):
        resp = self.request("delete", "/processes/%s" % name)
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

    def info(self):
        return self.process

    def status(self):
        resp = self.server.request("get", "/status/%s" % self.process['name'])
        return self.server.json_body(resp)

    def start(self):
        resp = self.server.request("post", "/processes/%s/_start" %
                (self.process['name'],))
        return True

    def stop(self):
        resp = self.server.request("post", "/processes/%s/_stop" %
                self.process['name'])
        return True

    def restart(self):
        resp = self.server.request("post", "/processes/%s/_restart" %
                self.process['name'])
        return True

    def add(self, num=1):
        resp = self.server.request("post", "/processes/%s/_add/%s" %
                (self.process['name'], num))
        return True

    def sub(self, num=1):
        resp = self.server.request("post", "/processes/%s/_sub/%s" %
                (self.process['name'], num))
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

        resp = self.server.request("post", "/processes/%s/_signal/%s" %
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
