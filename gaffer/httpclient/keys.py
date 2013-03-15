# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import uuid

from .base import GafferNotFound

class Keys(object):

    def __init__(self, server):
        self.server = server

    def all_keys(self, include_keys=False):
        path = "/keys"
        if include_keys:
            path += "?include_keys=true"

        resp = self.server.request("get", path)
        return self.server.json_body(resp)["keys"]

    def create_key(self, permissions, key=None, label="", parent=None):
        key = key or uuid.uuid4().hex
        data = {"permissions": permissions}
        if label and label is not None:
            data['label'] = label
        resp = self.set_key(key, data, parent=parent)
        return self.server.json_body(resp)['api_key']

    def set_key(self, key, data, parent=None):
        obj = data.copy()
        obj["key"] = key
        obj["parent"] = parent

        # post the request
        headers = {"Content-Type": "application/json"}
        body = json.dumps(obj)
        return self.server.request("post", "/keys", headers=headers, body=body)


    def get_key(self, key, include_keys=False):
        path = "/keys/%s" % key
        if include_keys:
            path += "?include_keys=true"

        resp = self.server.request("get", path)
        return self.server.json_body(resp)

    def delete_key(self, key):
        self.server.request("delete", "/keys/%s" % key)

    def has_key(self, key):
        try:
            self.server.request("head", "/keys/%s" % key)
        except GafferNotFound:
            return False
        return True
