# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import uuid

from tornado.web import HTTPError

from .util import CorsHandlerWithAuth
from ..keys import KeyConflict, KeyNotFound

class KeysHandler(CorsHandlerWithAuth):

    def get(self, *args):
        if not self.api_key.is_admin():
            raise HTTPError(403)

        if self.get_argument("include_keys", "false").lower() == "true":
            include_key = True
        else:
            include_key = False
        self.write({"keys": self.key_mgr.all_keys(include_key)})

    def post(self, *args):
        if not self.api_key.can_create_key():
            raise HTTPError(403)

        try:
            api_key, data, parent = self.fetch_key()
        except ValueError:
            raise HTTPError(400)

        permissions = data.get('permissions', {})
        if permissions.get('admin') == True and not self.api_key.is_admin():
            raise HTTPError(403)

        try:
            self.key_mgr.set_key(api_key, data, parent=parent)
        except KeyConflict:
            raise HTTPError(409)

        location = '%s://%s/keys/%s' % (self.request.protocol,
                self.request.host, api_key)

        self.set_header("Content-Type", "application/json")
        self.set_header("X-Api-Key", api_key)
        self.set_header("Location", location)
        self.write(json.dumps({"ok": True, "api_key": api_key}))

    def fetch_key(self):
        obj = json.loads(self.request.body.decode('utf-8'))
        key = uuid.uuid4().hex

        # if key id was passed in obj, remove it
        if "key" in obj:
            del obj['key']

        # parent key ?
        parent = None
        if "parent" in obj:
            parent = obj.pop('parent')

        return key, obj, parent


class KeyHandler(CorsHandlerWithAuth):

    def head(self, *args):
        if (not self.api_key.can_create_key() and
                self.api_key.api_key != args[0]):
            # only those who can create keys or the key owner can read the key
            # object
            raise HTTPError(403)

        try:
            key_obj = self.key_mgr.has_key(args[0])
        except KeyNotFound:
            raise HTTPError(404)

        self.set_status(200)

    def get(self, *args):
        if (not self.api_key.can_create_key() and
                self.api_key.api_key != args[0]):
            # only those who can create keys or the key owner can read the key
            # object
            raise HTTPError(403)

        try:
            key_obj = self.key_mgr.get_key(args[0])
        except KeyNotFound:
            raise HTTPError(404)

        if self.get_argument("include_keys", "false").lower() == "true":
            # include subkeys
            subkeys = self.key_mgr.all_subkeys(args[0])
            key_obj['keys'] = subkeys

        self.write(key_obj)

    def delete(self, *args):
        if (not self.api_key.can_create_key() and
                self.api_key.api_key != args[0]):
            # only those who can create keys or the key owner can read the key
            # object
            raise HTTPError(403)

        try:
            key_obj = self.key_mgr.delete_key(args[0])
        except KeyNotFound:
            raise HTTPError(404)

        self.write({"ok": True})
