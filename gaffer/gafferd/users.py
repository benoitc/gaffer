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


class UserNotFound(Exception):
    """ exception raised when a user doesn't exist"""


class UserConflict(Exception):
    """ exception raised when you try to create an already exisiting user """


class AuthManager(object):

    def __init__(self, loop, cfg, key_mgr=None):
        self.loop = patch_loop(loop)
        self.cfg = cfg
        self.key_mgr = key_mgr

        # initialize the db backend
        if not cfg.keys_backend or cfg.keys_backend == "default":
            self._backend = SqliteAuthHandler(loop, cfg)
        else:
            self._backend = load_backend(cfg.keys_backend)

        # initialize the events listenr
        self._emitter = EventEmitter(loop)

    def create_user(self, username, password, user_type=0, key=None,
            extra=None):
        self._backend.creatre_user(username, password, user_type=user_type,
                key=key, extra=extra)

    def update_user(self, username, password, user_type=0, key=None,
            extra=None):

class BaseAuthHandler(object):

    def __init__(self, loop, cfg, dbname=None):
        self.loop = patch_loop(loop)
        self.cfg = cfg
        self.dbname = dbname

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def create_user(self, username, password, user_type=0, extra=None):
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


    def user_bykey(self, key):
        raise NotImplementedError

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
            sql = """CREATE TABLE auth (user text primary key, pwd text, type
            int, key text, extra text)"""
            self.conn.execute(sql)

    def close(self):
        self.conn.commit()
        self.conn.close()

    def create_user(self, username, password, user_type=0, extra=None):
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
