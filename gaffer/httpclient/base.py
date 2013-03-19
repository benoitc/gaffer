# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

import pyuv
from tornado import httpclient

from ..tornado_pyuv import IOLoop
from .util import make_uri

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
        self.loop = loop
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
            self._io_loop.close()
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
        self.loop = loop or pyuv.Loop.default_loop()
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
