# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import deque
import json
import os
import sqlite3

import pyuv

from ..loop import patch_loop
from .util import load_backend


class Auth(object):

    def __init__(self, loop, cfg):
        if not cfg.auth_backend:
            self._backend = SqliteAuthHandler(loop, cfg)
        else:
            self._backend = load_backend(backend)








class BaseAuthHandler(object):

    def __init__(self, loop, cfg, dbname=None):
        self.loop = patch_loop(loop)
        self.cfg = cfg
        self.dbname = dbname

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def set_user(self, username, password, user_type=0, extra=None):
        raise NotImplementedError

    def get_user(self, username):
        raise NotImplementedError

    def delete_user(self, username):
        raise NotImplementedError

    def get_password(self, username):
        raise NotImplementedError

    def has_user(self, username):
        raise NotImplementedError

    def users_bytype(self, username):
        raise NotImplementedError

    def has_usertype(self, user_type):
        raise NotImplementedError

    def user_keys(self, username):
        raise NotImplementedError

    def set_key(self, key, data):
        raise NotImplementedError

    def get_key(self, key):
        raise NotImplementedError

    def delete_key(self, key):
        raise NotImplementedError

    def has_key(self, key):
        raise NotImplementedError


class KeyNotFound(Exception):
    """ exception raised when the key isn't found """


class KeyConflict(Exception):
    """ exception when you try to create a key that already exists """


class UserNotFound(Exception):
    """ exception raised when a user doesn't exist"""

class UserConflict(Exception):
    """ exception raised when you try to create an already exisiting user """

class SqliteAuthHandler(BaseAuthHandler):

    def __init__(self, loop, cfg, dbname=None):
        # set dbname
        dbname = dbname or "auth.db"
        if dbname != ":memory:":
            dbname = os.path.join(cfg.config_dir, dbname)

        super(SqliteAuthHandler, self).__init__(loop, cfg, dbname)

        # intitialize conn
        self.conn = None

    def open(self):
        self.conn = sqlite3.connect(self.dbname)
        if self.dbname != ":memory:" and os.path.isfile(self.dbname):
            return

        with self.conn:
            sql = ["""CREATE TABLE auth (user text primary key, pwd text, type
            int, extra text)""",
            """CREATE TABLE keys (key text primary key, user text, data
            text)"""]

            for q in sql:
                self.conn.execute(q)

    def close(self):
        self.conn.commit()
        self.conn.close()

    def set_user(self, username, password, user_type=0, extra=None):
        assert self.conn is not None
        with self.conn:
            try:
                self.conn.execute("INSERT INTO auth VALUES(?, ?, ?, ?)",
                        [username, password, user_type, extra])
            except sqlite3.IntegrityError:
                raise UserConflict()

    def update_user(self, username, password, user_type=1, extra=None):
        assert self.conn is not None

        if not self.has_user(username):
            raise UserNotFound()

        with self.conn:
            self.conn.execute("REPLACE INTO auth VALUES(?, ?, ?, ?)",
                    [username, password, user_type, extra])

    def get_user(self, username):
        assert self.conn is not None
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM auth where user=?", [username])
            row = cur.fetchone()
            user = row[3] or {}
            user.update({"username": row[0], "password": row[1], "user_type":
                row[2]})
            return user

    def delete_user(self, username):
        assert self.conn is not None
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM auth WHERE user=?", [username])
            # don't forget to delete all keys for this user
            cur.execute("DELETE FROM keys WHERE user=?", [username])

    def get_password(self, username):
        assert self.conn is not None
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT pwd FROM auth where user=?", [username])
            return cur.fetchone()[0]

    def has_user(self, username):
        try:
            self.get_user(username)
        except UserNotFound:
            return False
        return True

    def user_keys(self, username):
        assert self.conn is not None
        with self.conn:
            cur = self.conn.cursor()
            rows = cur.execute("SELECT key, data from keys WHERE user=?",
                    [username])
            keys = []
            for row in rows:
                key = json.loads(row[1])
                key["key"] = row[0]
                keys.append(key)
            return keys

    def set_key(self, owner, key, data):
        assert self.conn is not None
        if isinstance(data, dict):
            data = json.dumps(data)

        with self.conn:
            cur = self.conn.cursor()
            try:
                res = cur.execute("INSERT INTO keys VALUES (?, ?, ?)", [key,
                    owner, data])
            except sqlite3.IntegrityError:
                raise UserConflict()

    def get_key(self, key):
        assert self.conn is not None
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM keys WHERE key=?", [key])
        row = cur.fetchone()
        if not row:
            raise KeyNotFound()

        kobj = json.loads(row[2])
        kobj.update({ "key": row[0], "owner": row[1] })
        return kobj

    def delete_key(self, key):
        assert self.conn is not None
        with self.conn:
            self.conn.execute("DELETE FROM keys WHERE key=?", [key])

    def has_key(self, key):
        try:
            self.get_key(key)
        except KeyNotFound:
            return False
        return True
