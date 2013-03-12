# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import pyuv
import pytest

from gaffer.gafferd.users import (AuthManager, User, DummyUser,
        SqliteAuthHandler, UserConflict, UserNotFound)

from test_http import MockConfig

def test_config():
    return MockConfig(auth_dbname=":memory:", keys_dbname=":memory:")

def test_sqlite_backend():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with SqliteAuthHandler(loop, conf) as h:
        h.create_user("test", "test")

        with pytest.raises(UserConflict):
            h.create_user("test", "test")

        assert h.has_user("test") == True
        assert h.has_user("test1") == False

        h.create_user("test1", "test")
        assert h.has_user("test1") == True

        user = h.get_user("test")
        assert user == {"username": "test", "password": "test", "user_type": 0,
                "key": None}

        h.set_password("test", "test1")
        user = h.get_user("test")
        assert user['password'] == "test1"

        h.set_key("test", "test_key")
        user = h.get_user("test")
        assert user['key'] == "test_key"

        h.update_user("test", "test")
        user = h.get_user("test")
        assert user == {"username": "test", "password": "test", "user_type": 0,
                "key": None}

        h.delete_user("test")
        with pytest.raises(UserNotFound):
            h.get_user("test")

def test_auth_backend():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with AuthManager(loop, conf) as auth:
        auth.create_user("test", "test")

        with pytest.raises(UserConflict):
            auth.create_user("test", "test")

        assert auth.has_user("test") == True
        assert auth.has_user("test1") == False

        auth.create_user("test1", "test")
        assert auth.has_user("test1") == True

        user = auth.get_user("test")
        assert user["password"] != "test"

        auth.set_password("test", "test1")
        user1 = auth.get_user("test")
        assert user1['password'] != user["password"]

        auth.set_key("test", "test_key")
        user = auth.get_user("test")
        assert user['key'] == "test_key"

        auth.update_user("test", "test")
        user3 = auth.get_user("test")
        assert user3 != user

        auth.delete_user("test")
        with pytest.raises(UserNotFound):
            auth.get_user("test")

def test_authenticate():

    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with AuthManager(loop, conf) as auth:
        auth.create_user("test", "test")
        user = auth.authenticate("test", "test")
        assert isinstance(user, User)
        assert user.is_authenticated() == True
        assert user.is_anonymous() == False
        user1 = auth.authenticate("test", "test1")
        assert isinstance(user1, DummyUser)
        assert user1.is_authenticated() == False
        assert user1.is_anonymous() == True
