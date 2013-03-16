# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import os
import sqlite3
import uuid

from ..util import bytestring, ord_
from .pbkdf2 import pbkdf2_hex
from .util import load_backend


class UserNotFound(Exception):
    """ exception raised when a user doesn't exist"""


class UserConflict(Exception):
    """ exception raised when you try to create an already exisiting user """

class User(object):
    """ instance representing an authenticated user """

    def __init__(self, username, password, user_type=0, key=None, extra=None):
        self.username = username
        self.password = password
        self.user_type = user_type
        self.key = key
        self.extra = extra or {}

    def __str__(self):
        return "USer: %s" % self.username

    def is_authenticated(self):
        return True

    def is_anonymous(self):
        return False

    def is_user(self):
        return self.user_type == 0

    def is_app(self):
        return self.user_type == 1

    @classmethod
    def load(cls, obj):
        return cls(obj['username'], obj['password'], obj.get('user_type', 0),
                obj.get("key"), obj.get('extra'))

    def dump(self):
        return {"username": self.username, "password": self.password,
                "user_type": self.user_type, "key": self.key,
                "extra": self.extra}


class DummyUser(User):

    def __init__(self, *args, **kwargs):
        self.username = "anonymous"
        self.password = None
        self.user_type = 0
        self.key = None
        self.extra = {}

    def is_authenticated(self):
        return False

    def is_anonymous(self):
        return True


class AuthManager(object):

    def __init__(self, loop, cfg):
        self.loop = loop
        self.cfg = cfg

        # initialize the db backend
        if not cfg.auth_backend or cfg.auth_backend == "default":
            self._backend = SqliteAuthHandler(loop, cfg)
        else:
            self._backend = load_backend(cfg.keys_backend)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.close()
        except:
            pass

    def open(self):
        self._backend.open()

    def close(self):
        self._backend.close()

    def all_users(self, include_user=False):
        return self._backend.all_users(include_user=include_user)

    def create_user(self, username, password, user_type=1, key=None,
            extra=None):

        password = self._hash_password(password)

        # store the user
        self._backend.create_user(username, password, user_type=user_type,
                key=key, extra=extra)

    def authenticate(self, username, password):

        try:
            user = self._backend.get_user(username)
        except UserNotFound:
            return DummyUser()

        _alg, infos, password_hash = user['password'].split("$", 3)
        salt, iterations = infos.split(":")

        password_hash1 =  bytestring(pbkdf2_hex(password.encode('utf-8'),
            salt.encode('utf-8'), iterations=int(iterations)).decode('utf-8'))

        if not self._check_password(password_hash, password_hash1):
            return DummyUser()

        return User.load(user)

    def get_user(self, username):
        return self._backend.get_user(username)

    def set_password(self, username, password):
        password = self._hash_password(password)
        self._backend.set_password(username, password)

    def set_key(self, username, key):
        self._backend.set_key(username, key)

    def update_user(self, username, password, user_type=1, key=None,
            extra=None):
        password = self._hash_password(password)
        self._backend.update_user(username, password, user_type=user_type,
                key=key, extra=extra)

    def delete_user(self, username):
        self._backend.delete_user(username)

    def user_by_key(self, key):
        return self._backend.get_bykey(key)

    def user_by_type(self, user_type):
        return self._backend.get_bytype(user_type)

    def has_user(self, username):
        return self._backend.has_user(username)

    def has_usertype(self, user_type):
        return self._backend.has_usertype(user_type)

    def _check_password(self, a, b):
        # compare password hashes lengths
        if len(a) != len(b):
            return False

        # do a binary comparaison of password hashes
        rv = 0
        for x, y in zip(a, b):
            rv |= ord(x) ^ ord(y)

        return rv == 0

    def _hash_password(self, password):
        # hash the password
        salt = uuid.uuid4().hex
        hashed_password =  bytestring(pbkdf2_hex(password.encode('utf-8'),
                salt.encode('utf-8')).decode('utf-8'))
        return "PBKDF2-256$%s:%s$%s" % (salt, 1000, hashed_password)


class BaseAuthHandler(object):

    def __init__(self, loop, cfg):
        self.loop = loop
        self.cfg = cfg

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def create_user(self, username, password, user_type=0, key=None,
            extra=None):
        raise NotImplementedError

    def get_user(self, username):
        raise NotImplementedError

    def update_user(self, username, password, user_type=0, key=None,
            extra=None):
        raise NotImplementedError

    def set_password(self, username, password):
        raise NotImplementedError

    def set_key(self, username, key):
        raise NotImplementedError

    def delete_user(self, username):
        raise NotImplementedError

    def user_bykey(self, key):
        raise NotImplementedError

    def users_bytype(self, username):
        raise NotImplementedError

    def has_usertype(self, user_type):
        raise NotImplementedError

    def has_user(self, usernamen ):
        raise NotImplementedError

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.close()
        except:
            pass


class SqliteAuthHandler(BaseAuthHandler):
    """ SQLITE AUTH BACKEND FOR THE AUTHENTICATION API in gaffer """

    def __init__(self, loop, cfg):
        super(SqliteAuthHandler, self).__init__(loop, cfg)

        # set dbname
        self.dbname = cfg.auth_dbname or "auth.db"
        if self.dbname != ":memory:":
            self.dbname = os.path.join(cfg.config_dir, self.dbname)

        # intitialize conn
        self.conn = None

    def open(self):
        self.conn = sqlite3.connect(self.dbname)
        with self.conn:
            sql = """CREATE TABLE if not exists auth (user text primary key,
            pwd text, user_type int, key text, extra text)"""
            self.conn.execute(sql)

    def close(self):
        self.conn.commit()
        self.conn.close()

    def all_users(self, include_user=False):
        with self.conn:
            cur = self.conn.cursor()
            if include_user:
                rows = cur.execute("SELECT * FROM auth")
                return [self._make_user(row, False) for row in rows]
            else:
                rows = cur.execute("SELECT user FROM auth")
                return [row[0] for row in rows]

    def create_user(self, username, password, user_type=0, key=None,
            extra=None):
        assert self.conn is not None
        with self.conn:
            try:
                self.conn.execute("INSERT INTO auth VALUES(?, ?, ?, ?, ?)",
                        [username, password, user_type, key,
                         json.dumps(extra or {})])
            except sqlite3.IntegrityError:
                raise UserConflict()

    def get_user(self, username):
        assert self.conn is not None
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM auth where user=?", [username])
            row = cur.fetchone()

        if not row:
            raise UserNotFound()

        return self._make_user(row)

    def set_password(self, username, password):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("UPDATE auth SET pwd=? WHERE user=?", [password,
                username])

    def set_key(self, username, key):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("UPDATE auth SET key=? WHERE user=?", [key,
                username])

    def update_user(self, username, password, user_type=0, key=None,
            extra=None):
        assert self.conn is not None

        if not self.has_user(username):
            raise UserNotFound()

        with self.conn:
            self.conn.execute("""UPDATE auth SET pwd=?, user_type=?,
            key=?, extra=? WHERE user=?""", [password, user_type, key,
                json.dumps(extra or {}), username])

    def delete_user(self, username):
        assert self.conn is not None
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM auth WHERE user=?", [username])

    def get_bytype(self, user_type):
        assert self.conn is not None
        with self.conn:
            cur = self.conn.cursor()
            rows = cur.execute("SELECT * from auth WHERE user_type=?",
                    [user_type])

            return [self._make_user(row, False) for row in rows]

    def get_bykey(self, key):
        assert self.conn is not None
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT * from auth WHERE key=?", [key])
            row = cur.fetchone()

            if not row:
                raise UserNotFound()

            return self._make_user(row)

    def has_user(self, username):
        try:
            self.get_user(username)
        except UserNotFound:
            return False
        return True

    def has_type(self, user_type):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT * from auth WHERE user_type=?", [user_type])

            if not cur.fetchone():
                return False
            return True

    def _make_user(self, row, include_password=True):
        user = json.loads(row[4]) or {}
        user.update({"username": row[0], "user_type": row[2], "key": row[3]})

        if include_password:
            user.update({"password": row[1]})
        return user
