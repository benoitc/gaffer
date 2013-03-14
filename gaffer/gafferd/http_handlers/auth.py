# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import base64
import json

from tornado.web import HTTPError

from .util import CorsHandler

class AuthHandler(CorsHandler):

    def prepare(self):
        require_key = self.settings.get('require_key', False)
        auth_mgr = self.settings.get("auth_mgr")

        if not require_key:
            raise HTTPError(404)

        # get auth header
        auth_hdr = self.request.headers.get('Authorization', "").encode('utf-8')
        if not auth_hdr or not auth_hdr.startswith(b'Basic '):
            raise HTTPError(401)

        # decode the auth header
        auth_decoded = base64.decodestring(auth_hdr[6:])
        username, password = auth_decoded.split(b':', 2)

        # authenticate the user
        self.user = auth_mgr.authenticate(username.decode('utf-8'),
                password.decode('utf-8'))

        if not self.user.is_authenticated():
            raise HTTPError(401)

        self.set_header("Content-Type", "application/json")
        self.set_header("X-Api-Key", self.user.key or "")

    def head(self):
        self.set_status(200)

    def get(self, *args):
        self.write({"api_key": self.user.key})
