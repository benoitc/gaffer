# -*- coding: utf-8 -
#
# this file is part of gaffer. see the notice for more information.

try:
    import httplib
except ImportError:
    import http.client as httplib
import json

import pyuv
from tornado.web import RequestHandler, asynchronous, HTTPError
from ..keys import DummyKey, Key, KeyNotFound
from ..users import UserNotFound

ACCESS_CONTROL_HEADERS = ['X-Requested-With',
            'X-HTTP-Method-Override', 'Content-Type', 'Accept',
            'Authorization']

CORS_HEADERS = {
    'Access-Control-Allow-Methods' : 'POST, GET, PUT, DELETE, OPTIONS',
    'Access-Control-Max-Age'       : '86400', # 24 hours
    'Access-Control-Allow-Headers' : ", ".join(ACCESS_CONTROL_HEADERS),
    'Access-Control-Allow-Credentials': 'true'
}


class CorsHandler(RequestHandler):

    @asynchronous
    def options(self, *args, **kwargs):
        self.preflight()
        self.set_status(204)
        self.finish()

    def preflight(self):
        origin = self.request.headers.get('Origin', '*')

        if origin == 'null':
            origin = '*'

        self.set_header('Access-Control-Allow-Origin', origin)
        for k, v in CORS_HEADERS.items():
            self.set_header(k, v)

    def get_error_html(self, status_code, **kwargs):
        self.set_header("Content-Type", "application/json")

        if status_code == 400:
            resp = {"error": 400, "reason": "bad_request"}
        elif status_code == 404:
            resp = {"error": 404, "reason": "not_found"}
        elif status_code == 409:
            resp = {"error": 409, "reason": "conflict"}
        elif status_code == 401:
            resp = {"error": 401, "reason": "unauthorized"}
        elif status_code == 403:
            resp = {"error": 403, "reason": "forbidden"}
        else:
            resp = {"error": status_code,
                    "reason": httplib.responses[status_code]}

        if self.settings.get("debug") and "exc_info" in kwargs:
            exc_info = traceback.format_exception(*kwargs["exc_info"])
            resp['exc_info'] = exc_info

        return json.dumps(resp)


class CorsHandlerWithAuth(CorsHandler):

    def prepare(self):
        api_key = self.request.headers.get('X-Api-Key', None)
        require_key = self.settings.get('require_key', False)
        self.auth_mgr = self.settings.get('auth_mgr')
        key_mgr = self.key_mgr = self.settings.get('key_mgr')
        self.api_key = DummyKey()
        self.key_username = None

        # if the key API is enable start to use it
        if require_key:
            if api_key is not None:
                try:
                    self.api_key = Key.load(key_mgr.get_key(api_key))
                except KeyNotFound:
                    raise HTTPError(403, "key %s doesn't exist",api_key)

                try:
                    user_obj = self.auth_mgr.user_by_key(api_key)
                    self.key_username = user_obj["username"]
                except UserNotFound:
                    pass
            else:
                raise HTTPError(401)
