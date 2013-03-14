# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

from .base import GafferNotFound

class Users(object):

    def __init__(self, server):
        self.server = server

    def all_users(self, include_user=False):
        path = "/users"
        if include_user:
            path += "?include_user=true"

        resp = self.server.request("get", path)
        return self.server.json_body(resp)["users"]

    def create_user(self, username, password, user_type=1, key=None,
            extra=None):

        extra = extra or {}

        # create json obj
        obj = extra.copy()
        obj.update(dict(username=username, password=password,
            user_type=user_type, key=key))

        # post the request
        headers = {"Content-Type": "application/json"}
        body = json.dumps(obj)
        self.server.request("post", "/users", headers=headers, body=body)

    def get_user(self, username):
        resp = self.server.request("get", "/users/%s" % username)
        return self.server.json_body(resp)

    def set_password(self, username, password):
        body = json.dumps({"password": password})
        self.server.request("put", "/users/%s/password" % username, body=body)

    def set_key(self, username, key):
        body = json.dumps({"key": key})
        self.server.request("put", "/users/%s/key" % username, body=body)

    def update_user(self, username, password, user_type=1, key=None,
            extra=None):
        extra = extra or {}
        # create json obj
        obj = extra.copy()
        obj.update(dict(password=password, user_type=user_type, key=key))

        # send the request
        body = json.dumps(obj)
        self.server.request("put", "/users/%s" % username, body=body)

    def delete_user(self, username):
        self.server.request("delete", "/users/%s" % username)

    def has_user(self, username):
        try:
            self.server.request("head", "/users/%s" % username)
        except GafferNotFound:
            return False

        return True
