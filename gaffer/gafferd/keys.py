# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import deque
import os
import json
import sqlite3
import uuid

from ..events import EventEmitter
from .util import load_backend


class KeyNotFound(Exception):
    """ exception raised when the key isn't found """


class KeyConflict(Exception):
    """ exception when you try to create a key that already exists """


class InvalidKey(Exception):
    """ exception raised when the key is invalid """


class UnknownPermission(Exception):
    """ raised when the permission is not found """


class Key(object):
    """ instance representing a key """

    def __init__(self, api_key, label="", permissions={}):
        self.api_key = api_key
        self.label = label
        self.permissions = permissions

        # parse permissions
        self.manage = permissions.get('manage', None) or {}
        self.write = permissions.get('write', None) or {}
        self.read = permissions.get('read', None) or {}

    def __str__(self):
        return "Key: %s" % self.api_key

    @classmethod
    def load(cls, obj):
        if not "key" in obj:
            raise InvalidKey()

        key = obj['key']
        label = obj.get('label', "")
        permissions = obj.get("permissions", {})
        return cls(key, label, permissions)

    def dump(self):
        return {"key": self.api_key, "label": self.label, "permissions":
                self.permissions}

    def is_admin(self):
        """ does this key has all rights? """
        return self.permissions.get("admin", False)

    def can_create_key(self):
        """ can we create new keys with this key?

        Note only a user key can create keys able to create other keys. Sub
        keys can't create keys.
        """
        if self.is_admin():
            return True

        return self.permissions.get("create_key", False)

    def can_create_user(self):
        """ can we create users with this key ? """
        if self.is_admin():
            return True

        return self.permissions.get("create_user", False)

    def can_manage_all(self):
        return '*' in self.manage or self.is_admin()

    def can_write_all(self):
        return '*' in self.write or self.can_manage_all()

    def can_read_all(self):
        return '*' in self.read or self.can_write_all()

    def can_manage(self, job_or_session):
        """ test if a user can manage a job or a session

        managing a session means:
        - load/unload/update job in this session
        - start/stop processes and jobs in a session
        - list
        """

        return self.can('manage', job_or_session)

    def can_write(self, job_or_session):
        """ test if a user can write to a process for this job or all the jobs
        of the session """
        if self.can_manage(job_or_session):
            return True

        return self.can('write', job_or_session)

    def can_read(self, job_or_session):
        """ test if a user can read from a process for this job or all the jobs
        of the session """

        if self.can_write(job_or_session):
            return True

        return self.can('read', job_or_session)

    def can(self, permission, what):
        """ test the permission for a job or a session """
        if not hasattr(self, permission):
            raise UnknownPermission("%r does not exist")

        # get all permissions
        permissions = getattr(self, permission, {})

        # check if we we have the permission on all resources
        if '*' in permissions or self.is_admin():
            return True

        if "." in what:
            # we are testing job possibilities. The try first to know if we
            # have the permissions on the session
            session = what.split(".")[0]
            if session in permissions:
                return True

        # test the job permission
        if what in getattr(self, permission, {}):
            return True

        return False


class DummyKey(Key):

    def __init__(self):
        super(DummyKey, self).__init__("dummy")

    def can_create_key(self):
        return False

    def can_create_user(self):
        return False

    def is_admin(self):
        return True

    def can_manage_all(self):
        return True

    def can_write_all(self):
        return True

    def can_read_all(self):
        return True

    def can(self, permissions, what):
        return True


class KeyManager(object):

    def __init__(self, loop, cfg):
        self.loop = loop
        self.cfg = cfg
        self._cache = {}
        self._entries = deque()

        # initialize the db backend
        if not cfg.keys_backend or cfg.keys_backend == "default":
            self._backend = SqliteKeyBackend(loop, cfg)
        else:
            self._backend = load_backend(cfg.keys_backend)

        # initialize the events listenr
        self._emitter = EventEmitter(loop)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.close()
        except:
            pass

    def subscribe(self, event, listener):
        self._emitter.subscribe(event, listener)

    def unsubscribe(self, event, listener):
        self._emitter.unsubscribe(event, listener)

    def open(self):
        self._backend.open()
        self._emitter.publish("open", self)

    def close(self):
        self._emitter.publish("close", self)
        self._backend.close()
        self._emitter.close()

        # empty the cache
        self._entries.clear()
        self._cache = {}

    def all_keys(self, include_key=False):
        return self._backend.all_keys(include_key=include_key)

    def create_key(self, permissions, key=None, label="", parent=None):
        key = key or uuid.uuid4().hex
        data = {"permissions": permissions}
        if label and label is not None:
            data['label'] = label

        self.set_key(key, data, parent=parent)
        return key


    def set_key(self, key, data, parent=None):
        self._backend.set_key(key, data, parent=parent)
        self._emitter.publish("set", self, key)

    def get_key(self, key):
        if key in self._cache:
            return self._cache[key]

        okey = self._backend.get_key(key)

        # do we need to clean the cache?
        # we only keep last 1000 acceded keys in RAM
        if len(self._cache) >= 1000:
            to_remove = self._entries.popleft()
            self._cache.pop(to_remove)

        # enter last entry in the cache
        self._cache[key] = okey
        self._entries.append(key)
        return okey

    def delete_key(self, key):
        # remove the key and all sub keys from the cache if needed
        self._delete_entry(key)

        for subkey in self.all_subkeys(key):
            self._delete_entry(subkey["key"])

        # then delete the
        self._backend.delete_key(key)
        self._emitter.publish("delete", self, key)

    def has_key(self, key):
        return self._backend.has_key(key)

    def all_subkeys(self, key):
        return self._backend.all_subkeys(key)

    def _delete_entry(self, key):
        if key in self._cache:
            self._entries.remove(key)
            self._cache.pop(key)


class KeyBackend(object):

    def __init__(self, loop, cfg):
        self.loop = loop
        self.cfg = cfg

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.close()
        except:
            pass

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def all_keys(self):
        raise NotImplementedError

    def set_key(self, key, data):
        raise NotImplementedError

    def get_key(self, key):
        raise NotImplementedError

    def delete_key(self, key):
        raise NotImplementedError

    def has_key(self, key):
        raise NotImplementedError

    def all_subkeys(self, key):
        raise NotImplementedError


class SqliteKeyBackend(KeyBackend):
    """ sqlite backend to store API keys in gaffer """


    def __init__(self, loop, cfg):
        super(SqliteKeyBackend, self).__init__(loop, cfg)

        # set dbname
        self.dbname = cfg.keys_dbname or "keys.db"
        if self.dbname != ":memory:":
            self.dbname = os.path.join(cfg.config_dir, self.dbname)

        # intitialize conn
        self.conn = None

    def open(self):
        self.conn = sqlite3.connect(self.dbname)
        with self.conn:
            sql = """CREATE TABLE if not exists keys (key text primary key,
            data text, parent text)"""
            self.conn.execute(sql)

    def close(self):
        self.conn.commit()
        self.conn.close()

    def all_keys(self, include_key=False):
        with self.conn:
            cur = self.conn.cursor()
            rows = cur.execute("SELECT * FROM keys", [])
            if include_key:
                return [self._make_key(row) for row in rows]
            else:
                return [row[0] for row in rows]

    def set_key(self, key, data, parent=None):
        assert self.conn is not None
        if isinstance(data, dict):
            data = json.dumps(data)

        with self.conn:
            cur = self.conn.cursor()
            try:
                cur.execute("INSERT INTO keys VALUES (?, ?, ?)", [key,
                    data, parent])
            except sqlite3.IntegrityError:
                raise KeyConflict()

    def get_key(self, key, subkeys=True):
        assert self.conn is not None

        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM keys WHERE key=?", [key])
            row = cur.fetchone()

        if not row:
            raise KeyNotFound()
        return self._make_key(row)

    def delete_key(self, key):
        assert self.conn is not None
        with self.conn:
            self.conn.execute("DELETE FROM keys WHERE key=? OR parent=?",
                    [key, key])

    def has_key(self, key):
        try:
            self.get_key(key)
        except KeyNotFound:
            return False
        return True

    def all_subkeys(self, key):
        with self.conn:
            cur = self.conn.cursor()
            rows = cur.execute("SELECT * FROM keys WHERE parent=?", [key])
            return [self._make_key(row) for row in rows]

    def _make_key(self, row):
        obj = json.loads(row[1])
        obj.update({ "key": row[0] })
        return obj
