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
import signal

import six
from tornado import httpclient

from .events import EventEmitter
from .loop import patch_loop, get_loop
from .tornado_pyuv import IOLoop
from .util import quote, quote_plus

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

class EventsourceClient(object):
    """ simple client to fetch Gaffer streams using the eventsource
    stream.

    Example of usage::

        loop = pyuv.Loop.default_loop()

        def cb(event, data):
            print(data)

        # create a client
        url = http://localhost:5000/streams/1/stderr?feed=continuous'
        client = EventSourceClient(loop, url)

        # subscribe to the stderr event
        client.subscribe("stderr", cb)

        # start the client
        client.start()

    """

    def __init__(self, loop, url, **kwargs):
        self.loop = patch_loop(loop)
        self._io_loop = IOLoop(_loop=loop)
        self.url = url
        self._emitter = EventEmitter(self.loop)
        self.client = httpclient.AsyncHTTPClient(self._io_loop, **kwargs)
        self.active = False
        self.stopped = False

    def start(self):
        self.active = True
        headers = {"Content-Type": "text/event-stream"}
        req = httpclient.HTTPRequest(url=self.url,
                                        method='GET',
                                        headers=headers,
                                        request_timeout=0,
                                        streaming_callback=self._on_stream)

        self.client.fetch(req, self._on_request)
        self._io_loop.start(False)

    def subscribe(self, event, listener):
        self._emitter.subscribe(event, listener)

    def unsubscribe(self, event, listener):
        self._emitter.unsubscribe(event, listener)

    def subscribe_once(self, event, listener):
        self._emitter.subscribe_once(event, listener)

    def render(self, event, data):
        return data

    def stop(self):
        self.active = False
        #self._emitter.close()
        self.client.close()
        self._io_loop.stop()
        self._io_loop.close(True)

    def run(self):
        self.loop.run()

    def _on_request(self, response):
        self.stop()

    def _on_stream(self, message):
        if not message:
            return
        lines = [line for line in message.strip(b'\r\n').split(b"\r\n")]

        event = None
        data = []
        for line in lines:
            f, val = line.split(b":", 1)
            if f == b"event":
                event = val.strip()
            elif f == b"data":
                data.append(val.strip())
        if event is None:
            return

        event = event.decode('utf-8')
        data = self.render(event, b"\n".join(data).strip())
        self._emitter.publish(event, data)

class Watcher(EventsourceClient):
    """ simple EventsourceClient wrapper that decode the JSON to a
    python object """

    def render(self, event, data):
        return json.loads(data.decode('utf-8'))

class Server(object):
    """ Server, main object to connect to a gaffer node. Most of the
    calls are blocking. (but running in the loop) """

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

        print(url)
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
        """ get gaffer version """
        resp = self.request("get", "/")
        return self.json_body(resp)['version']

    def running(self):
        resp = self.request("get", "/pids")
        return self.json_body(resp)['pids']

    def ping(self):
        resp = self.request("get", "/ping")
        return resp.body == b'OK'

    def walk(self, callback):
        apps = self.all_apps()
        for appname in apps:
            templates = self.get_templates(appname)
            for template in templates:
                callback(self, template)

    def walk_templates(self, callback, appname=None):
        appname = appname or "system"
        templates = self.get_templates(appname)
        for name in templates:
            callback(self, self.get_template(name, appname))

    def walk_template(self, callback, name, appname=None):
        appname = appname or "system"
        template = self.get_template(name, appname)
        for pid in template.pids:
            callback(self, self.get_process(pid))

    def all_apps(self):
        """ get list of registered processes """
        resp = self.request("get", "/apps")
        obj = self.json_body(resp)
        return obj['apps']

    def get_templates(self, appname=None):
        appname = appname or "system"
        resp = self.request("get", "/apps/%s" % appname)
        obj = self.json_body(resp)
        return obj['templates']

    def get_template(self, name, appname=None):
        """ get a process by name or id.

        If id is given a Process instance is returned in other cases a
        Process instance is returned. """

        appname = appname or "system"
        resp = self.request("get", "/apps/%s/%s" % (appname, name))
        config = self.json_body(resp)['config']
        return Template(server=self, config=config)

    def get_process(self, pid):
        return Process(server=self, pid=pid)

    def is_template(self, name, appname=None):
        """ is the process exists ? """

        appname = appname or "system"
        resp = self.request("head", "/apps/%s/%s" % (appname, name))
        if resp.code == 200:
            return True
        return False

    def save_template(self, name, cmd, appname=None, **kwargs):
        """ save template.

        Args:

        - **name**: name of the process
        - **cmd**: program command, string)
        - **appname**: name of the application
        - **args**: the arguments for the command to run. Can be a list or
          a string. If **args** is  a string, it's splitted using
          :func:`shlex.split`. Defaults to None.
        - **env**: a mapping containing the environment variables the command
          will run with. Optional
        - **uid**: int or str, user id
        - **gid**: int or st, user group id,
        - **cwd**: working dir
        - **detach**: the process is launched but won't be monitored and
          won't exit when the manager is stopped.
        - **shell**: boolean, run the script in a shell. (UNIX
          only),
        - os_env: boolean, pass the os environment to the program
        - numprocesses: int the number of OS processes to launch for
          this description

        If `_force_update=True` is passed, the existing process template
        will be overwritten. """
        if "_force_update" in kwargs:
            force = kwargs.pop("_force_update")

        appname = appname or "system"

        config = { "name": name, "cmd": cmd, "appname": appname }
        config.update(kwargs)

        body = json.dumps(config)

        headers = {"Content-Type": "application/json" }

        if force:
            if self.is_template(name):
                self.request("put", "/apps/%s/%s" % (appname, name), body=body,
                        headers=headers)
            else:
                self.request("post", "/apps/%s" % appname, body=body,
                        headers=headers)
        else:
            self.request("post", "/apps/%s" % appname, body=body,
                        headers=headers)

        return Template(server=self, config=config)

    def add_template(self, name, cmd, appname=None, **kwargs):
        """ add a process. Use the same arguments as in save_process.

        If a process with the same name is already registred a
        `GafferConflict` exception is raised.
        """
        kwargs["_force_update"] = False
        return self.save_template(name, cmd, appname=None, **kwargs)

    def update_template(self, name, cmd, appname=None, **kwargs):
        """ update a process. """
        kwargs["_force_update"] = True
        return self.save_template(name, cmd, appname=appname, **kwargs)

    def remove_template(self, name, appname=None):
        """ Stop a process and remove it from the managed processes """

        appname = appname or "system"
        self.request("delete", "/apps/%s/%s" % (appname, name))
        return True

    def send_signal(self, name, signal, appname=None):
        """ Send a signal to the pid or the process name """
        appname = appname or "system"
        body = json.dumps({"signal": signal})
        headers = {"Content-Type": "application/json" }
        self.request('post', "/apps/%s/%s/signal" % (appname, name),
            body=body, headers=headers)
        return True

    def get_watcher(self, heartbeat="true"):
        """ return a watcher to listen on /watch """
        url =  make_uri(self.uri, '/watch', feed='eventsource',
                heartbeat=str(heartbeat))
        return Watcher(self.loop, url, **self.options)

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
        print(resp)
        obj = self.server.json_body(resp)
        return obj['stats']

    def stop(self):
        """ stop the process """
        self.server.request("delete", "/%s" % self.pid)
        return True

    def signal(self, sig):
        """ Send a signal to the pid """
        path = "/%s/signal" % (self.pid, sig)
        body = json.dumps({"signal", sig})
        headers = {"Content-Type": "application/json"}

        self.server.request("post", path, body=body, headers=headers)
        return True

class Template(object):
    """ Template object. Represent a remote template state"""

    def __init__(self, server, config):
        self.server = server
        self.config = config
        self.name = config['name']
        self.appname = config['appname']


    def __str__(self):
        return self.process.get('name')

    def __getattr__(self, key):
        if key in self.config:
            return self.config[key]

        try:
            return self.__dict__[key]
        except KeyError as e:
            raise AttributeError(str(e))

    @property
    def active(self):
        """ return True if the process is active """
        resp = self.server.request("get", "/apps/%s/%s/state" % (self.appname,
            self.name))
        if resp.body == b'1':
            return True
        return False

    @property
    def running(self):
        """ return the number of processes running for this template """
        info = self.info()
        return info['running']

    @property
    def numprocesses(self):
        """ return the maximum number of processes that can be launched
        for this template """
        info = self.info()
        return info['max_processes']

    @property
    def pids(self):
        """ return a list of running pids """
        resp = self.server.request("get", "/apps/%s/%s/pids" % (self.appname,
            self.name))
        result = self.server.json_body(resp)
        return result['pids']

    def info(self):
        """ return the process info dict """
        resp = self.server.request("get", "/apps/%s/%s" % (self.appname,
            self.name))
        return self.server.json_body(resp)

    def stats(self):
        """ Return the template stats
        """
        resp = self.server.request("get", "/apps/%s/%s" % (self.appname,
            self.name))
        return self.server.json_body(resp)


    def start(self):
        """ start the process if not started, spawn new processes """
        self.server.request("post", "/apps/%s/%s/state" % (self.appname,
            self.name), body="1")
        return True

    def stop(self):
        """ stop the process """
        self.server.request("post", "/apps/%s/%s/state" % (self.appname,
            self.name), body="0")
        return True

    def restart(self):
        """ restart the process """
        self.server.request("post", "/apps/%s/%s/state" % (self.appname,
            self.name), body="2")
        return True

    def scale(self, num=1):
        body = json.dumps({"scale": num})
        resp = self.server.request("post", "/apps/%s/%s/numprocesses" % (
            self.appname, self.name), body=body)
        result = self.server.json_body(resp)
        return result['numprocesses']

    def signal(self, num_or_str):
        """ send a signal to all processes of this template """
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

        body = json.dumps({"signal": signum})
        self.server.request("post", "/apps/%s/%s/signal" % (self.appname,
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
