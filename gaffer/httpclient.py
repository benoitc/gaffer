# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
Gaffer provides you a simple Client to control a gaffer node via HTTP.

Example of usage::

    import pyuv

    from gaffer.httpclient import Server

    # initialize a loop
    loop = pyuv.Loop.defaul_loop()

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

import pyuv
import six
from tornado import httpclient

from .events import EventEmitter
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
            response = http_client.fetch("http://www.friendpaste.com/")
            print response.body
        except httpclient.HTTPError as e:
            print("Error: %s" % e)
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
        self.loop = loop
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
        """ get gaffer version """
        resp = self.request("get", "/")
        return self.json_body(resp)['version']

    def processes(self):
        """ get list of registered processes """
        resp = self.request("get", "/processes")
        return self.json_body(resp)

    def running(self):
        """ get list of running processes by pid """
        resp = self.request("get", "/processes", running="true")
        return self.json_body(resp)

    def get_process(self, name_or_id):
        """ get a process by name or id.

        If id is given a ProcessId instance is returned in other cases a
        Process instance is returned. """
        resp = self.request("get", "/processes/%s" % name_or_id)
        process = self.json_body(resp)

        if isinstance(name_or_id, int):
            return ProcessId(server=self, pid=name_or_id, process=process)

        return Process(server=self, process=process)

    def is_process(self, name):
        """ is the process exists ? """
        resp = self.request("head", "/processes/%s" % name)
        if resp.code == 200:
            return True
        return False

    def save_process(self, name, cmd, **kwargs):
        """ save a process.

        Args:

        - **name**: name of the process
        - **cmd**: program command, string)
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
        """ add a process. Use the same arguments as in save_process.

        If a process with the same name is already registred a
        `GafferConflict` exception is raised.
        """
        kwargs["_force_update"] = False
        return self.save_process(name, cmd, **kwargs)

    def update_process(self, name, cmd, **kwargs):
        """ update a process. """
        kwargs["_force_update"] = True
        return self.save_process(name, cmd, **kwargs)

    def remove_process(self, name):
        """ Stop a process and remove it from the managed processes """

        self.request("delete", "/processes/%s" % name)
        return True

    def send_signal(self, name_or_id, num_or_str):
        """ Send a signal to the pid or the process name """
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

    def groups(self):
        """ return the list of all groups """
        resp = self.request("get", "/groups")
        return self.json_body(resp)

    def get_group(self, name):
        """ return the list of all process templates of this group """
        resp = self.request("get", "/groups/%s" % name)
        return self.json_body(resp)

    def start_group(self, name):
        """ start all process templates of the group """
        self.request("post", "/groups/%s/_start" % name)
        return True

    def stop_group(self, name):
        """ stop all process templates of the group """
        self.request("post", "/groups/%s/_stop" % name)
        return True


    def restart_group(self, name):
        """ restart all process templates of the group """
        self.request("post", "/groups/%s/_restart" % name)
        return True

    def remove_group(self, name):
        """ remove the group and all process templates of the group """
        self.request("delete", "/groups/%s" % name)
        return True

    def get_watcher(self, heartbeat="true"):
        """ return a watcher to listen on /watch """
        url =  make_uri(self.uri, '/watch', feed='eventsource',
                heartbeat=str(heartbeat))
        return Watcher(self.loop, url, **self.options)

class ProcessId(object):
    """ Process Id object. It represent a pid """

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
        """ return True if the process is active """
        resp = self.server.head("get", "/processes/%s" % self.pid)
        if resp.code == 200:
            return True
        return False

    def stop(self):
        """ stop the process """
        self.server.request("post", "/processes/%s/_stop" % self.pid)
        return True

    def signal(self, num_or_str):
        """ Send a signal to the pid """
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
    """ Process object. Represent a remote process state"""

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
        """ return True if the process is active """
        status = self.status()
        return status['active']

    @property
    def running(self):
        """ return the number of processes running for this template """
        status = self.status()
        return status['running']

    @property
    def numprocesses(self):
        """ return the maximum number of processes that can be launched
        for this template """
        status = self.status()
        return status['max_processes']

    @property
    def pids(self):
        """ return a list of running pids """
        resp = self.server.request("get", "/processes/%s/_pids" %
                self.process['name'])

        result = self.server.json_body(resp)
        return result['pids']

    def info(self):
        """ return the process info dict """
        return self.process

    def status(self):
        """ Return the status

        ::

            {
                "active": true,
                "running": 1,
                "numprocesses": 1
            }

        """
        resp = self.server.request("get", "/status/%s" % self.process['name'])
        return self.server.json_body(resp)


    def start(self):
        """ start the process if not started, spawn new processes """
        self.server.request("post", "/processes/%s/_start" %
                self.process['name'])
        return True

    def stop(self):
        """ stop the process """
        self.server.request("post", "/processes/%s/_stop" %
                self.process['name'])
        return True

    def restart(self):
        """ restart the process """
        self.server.request("post", "/processes/%s/_restart" %
                self.process['name'])
        return True

    def add(self, num=1):
        """ increase the number of processes for this template """
        resp = self.server.request("post", "/processes/%s/_add/%s" %
                (self.process['name'], num))

        obj = self.server.json_body(resp)
        return obj['numprocesses']

    def sub(self, num=1):
        """ decrease the number of processes for this template """

        resp = self.server.request("post", "/processes/%s/_sub/%s" %
                (self.process['name'], num))

        obj = self.server.json_body(resp)
        return obj['numprocesses']

    def stats(self):
        resp = self.server.request("get", "/stats/%s" % self.process['name'])
        return self.server.json_body(resp)



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
