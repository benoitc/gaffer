# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import uuid

from tornado.web import HTTPError

from .util import CorsHandlerWithAuth
from ..users import UserNotFound, UserConflict


class UsersHandler(CorsHandlerWithAuth):

    def get(self, *args):
        if not self.api_key.is_admin():
            raise HTTPError(403)

        if self.get_argument("include_user", "false").lower() == "true":
            include_user = True
        else:
            include_user = False
        self.write({"users":  self.auth_mgr.all_users(
            include_user=include_user)})


    def post(self, *args):
        if not self.api_key.can_create_user():
            raise HTTPError(403)

        try:
            username, password, user_type, key, extra = self.fetch_user()
        except ValueError:
            raise HTTPError(400)

        try:
            self.auth_mgr.create_user(username, password, user_type=user_type,
                    key=key, extra=extra)
        except UserConflict:
            raise HTTPError(409)

        self.write({"ok": True})

    def fetch_user(self, update=False):
        obj = json.loads(self.request.body.decode('utf-8'))

        if not update:
            try:
                username = obj.pop('username')
            except KeyError:
                raise ValueError()
        elif "username" in obj:
            del obj['username']

        try:
            password = obj.pop('password')
        except KeyError:
            raise ValueError()

        user_type = obj.pop('user_type', 1)
        if user_type == 0 and not self.api_key.is_admin():
            raise HTTPError(403)

        key = obj.pop('key', None)

        if not update:
            return username, password, user_type, key, obj
        return password, user_type, key, obj


class UserHandler(UsersHandler):

    def head(self, *args):
        # only the key with can_create_user or key associated to a username
        # can fetch the user details
        if not self.api_key.can_create_user() and self.key_username != args[0]:
            raise HTTPError(404)

        if not self.auth_mgr.has_user(args[0]):
            self.set_status(404)
        else:
            self.set_status(200)


    def get(self, *args):
        # only the key with can_create_user or key associated to a username
        # can fetch the user details
        if not self.api_key.can_create_user() and self.key_username != args[0]:
            raise HTTPError(403)

        try:
            self.write(self.auth_mgr.get_user(args[0]))
        except UserNotFound:
            raise HTTPError(404)

    def delete(self, *args):
        if not self.api_key.can_create_user() and self.key_username != args[0]:
            raise HTTPError(403)

        if not self.auth_mgr.has_user(args[0]):
            raise HTTPError(404)

        try:
            self.auth_mgr.delete_user(args[0])
        except UserNotFound:
            raise HTTPError(404)

        self.write({"ok": True})

    def put(self, *args):
        if not self.api_key.can_create_user() and self.key_username != args[0]:
            raise HTTPError(403)

        try:
            password, user_type, key, extra = self.fetch_user(update=True)
        except ValueError:
            raise HTTPError(400)

        try:
            self.auth_mgr.update_user(args[0], password, user_type=user_type,
                    key=key, extra=extra)
        except UserConflict:
            raise HTTPError(409)

        self.write({"ok": True})


class UserPasswordHandler(CorsHandlerWithAuth):

    def put(self, *args):
        if not self.api_key.can_create_user() and self.key_username != args[0]:
            raise HTTPError(403)

        obj = json.loads(self.request.body.decode('utf-8'))
        if obj.get("password", None) is None:
            raise HTTPError(400)

        try:
            self.auth_mgr.set_password(args[0], obj['password'])
        except UserNotFound:
            raise HTTPError(404)

        self.write({"ok": True})

class UserKeydHandler(CorsHandlerWithAuth):

    def put(self, *args):
        if not self.api_key.can_create_user() and self.key_username != args[0]:
            raise HTTPError(403)

        obj = json.loads(self.request.body.decode('utf-8'))
        if obj.get("key", None) is None:
            raise HTTPError(400)

        try:
            self.auth_mgr.set_key(args[0], obj['key'])
        except UserNotFound:
            raise HTTPError(404)

        self.write({"ok": True})
