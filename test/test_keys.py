# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import pyuv
import pytest

from gaffer.gafferd.keys import (KeyNotFound, KeyConflict, InvalidKey,
        UnknownPermission, Key, DummyKey, KeyManager, SqliteKeyBackend)

from test_http import MockConfig

def test_config():
    return MockConfig(auth_dbname=":memory:", keys_dbname=":memory:")

def test_sqlite_backend():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with SqliteKeyBackend(loop, conf) as h:
        h.set_key("test", {"permission": {}})

        with pytest.raises(KeyConflict):
            h.set_key("test", {"permission": {}})

        assert h.has_key("test") == True

        key = h.get_key("test")
        assert key == {"key": "test", "permission": {}}

        key = h.delete_key("test")
        with pytest.raises(KeyNotFound):
            key = h.get_key("test")

        h.set_key("test", {"permission": {}})
        h.set_key("test1", {"permission": {}}, "test")

        assert h.has_key("test1") == True
        assert h.all_subkeys("test") == [{"key": "test1", "permission": {}}]
        assert len(h.all_keys()) == 2
        assert h.all_keys() == ["test", "test1"]
        assert h.all_keys(include_key=True) == [{"key": "test",
            "permission": {}}, {"key": "test1", "permission": {}}]

def test_key_manager():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.set_key("test", {"permission": {}})

        with pytest.raises(KeyConflict):
            h.set_key("test", {"permission": {}})

        assert h.has_key("test") == True

        key = h.get_key("test")
        assert key == {"key": "test", "permission": {}}
        assert len(h._cache) == 1
        assert "test" in h._cache
        assert len(h._entries) == 1
        assert list(h._entries) == ["test"]


        key = h.delete_key("test")
        with pytest.raises(KeyNotFound):
            key = h.get_key("test")

        h.set_key("test", {"permission": {}})
        h.set_key("test1", {"permission": {}}, "test")

        assert h.has_key("test1") == True
        assert h.all_subkeys("test") == [{"key": "test1", "permission": {}}]
        assert len(h.all_keys()) == 2
        assert h.all_keys() == ["test", "test1"]
        assert h.all_keys(include_key=True) == [{"key": "test",
            "permission": {}}, {"key": "test1", "permission": {}}]

        h.get_key("test")
        h.get_key("test1")
        assert len(h._cache) == 2
        assert "test" in h._cache
        assert "test1" in h._cache
        assert len(h._entries) == 2
        assert list(h._entries) == ["test", "test1"]

        # make sure keys are deleted from the cache
        h.delete_key("test")
        assert len(h._cache) == 0
        assert len(h._entries) == 0

        with pytest.raises(KeyNotFound):
            key = h.get_key("test")

        with pytest.raises(KeyNotFound):
            key = h.get_key("test1")


def test_create_key():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"admin": True}, label="some key", key="test")
        key = h.get_key("test")

        assert key == {"key": "test", "label": "some key",
                "permissions": {"admin": True}}


def test_admin_permissions():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"admin": True}, key="test", label="admin")
        key = Key.load(h.get_key("test"))
        assert key.api_key == "test"
        assert key.label == "admin"
        assert key.permissions == {"admin": True}
        assert key.is_admin() == True
        assert key.can_create_key() == True
        assert key.can_create_user() == True
        assert key.can_manage_all() == True
        assert key.can_read_all() == True
        assert key.can_write_all() == True
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == True
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == True
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == True
        assert key.can_manage("test.test") == True
        assert key.can_manage("test1") == True
        assert key.can_manage("test1.test") == True

def test_manage_all_permission():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"manage": ["*"]}, key="test")
        key = Key.load(h.get_key("test"))
        assert key.api_key == "test"
        assert key.permissions == {"manage": ["*"]}
        assert key.is_admin() == False
        assert key.can_create_key() == False
        assert key.can_create_user() == False
        assert key.can_manage_all() == True
        assert key.can_read_all() == True
        assert key.can_write_all() == True
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == True
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == True
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == True
        assert key.can_manage("test.test") == True
        assert key.can_manage("test1") == True
        assert key.can_manage("test1.test") == True

def test_read_all_permission():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"read": ["*"]}, key="test")
        key = Key.load(h.get_key("test"))
        assert key.api_key == "test"
        assert key.permissions == {"read": ["*"]}
        assert key.is_admin() == False
        assert key.can_create_key() == False
        assert key.can_create_user() == False
        assert key.can_manage_all() == False
        assert key.can_read_all() == True
        assert key.can_write_all() == False
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == False
        assert key.can_write("test.test") == False
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_write_all_permission():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"write": ["*"]}, key="test")
        key = Key.load(h.get_key("test"))
        assert key.api_key == "test"
        assert key.permissions == {"write": ["*"]}
        assert key.is_admin() == False
        assert key.can_create_key() == False
        assert key.can_create_user() == False
        assert key.can_manage_all() == False
        assert key.can_read_all() == True
        assert key.can_write_all() == True
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == True
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == True
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False


def test_manage_session():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"manage": ["test"]}, key="test")
        key = Key.load(h.get_key("test"))
        assert key.api_key == "test"
        assert key.is_admin() == False
        assert key.can_create_key() == False
        assert key.can_create_user() == False
        assert key.can_manage_all() == False
        assert key.can_read_all() == False
        assert key.can_write_all() == False
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == False
        assert key.can_write("test") == True
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == True
        assert key.can_manage("test.test") == True
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_manage_session2():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"manage": ["test", "test1"]}, key="test1")
        key = Key.load(h.get_key("test1"))

        assert key.can_manage_all() == False
        assert key.can_read_all() == False
        assert key.can_write_all() == False
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == True
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == True
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == True
        assert key.can_manage("test.test") == True
        assert key.can_manage("test1") == True
        assert key.can_manage("test1.test") == True


def test_manage_job():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"manage": ["test.test"]}, key="test1")
        key = Key.load(h.get_key("test1"))
        assert key.can_read("test") == False
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == False
        assert key.can_write("test") == False
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == True
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_manage_job2():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"manage": ["test.test", "test1"]}, key="test1")
        key = Key.load(h.get_key("test1"))
        assert key.can_read("test") == False
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == False
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == True
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == True
        assert key.can_manage("test1") == True
        assert key.can_manage("test1.test") == True

def test_manage_job3():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"manage": ["test.test", "test1.test"]}, key="test1")
        key = Key.load(h.get_key("test1"))
        assert key.can_read("test") == False
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == False
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == True
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == True



def test_read_session():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"read": ["test"]}, key="test")
        key = Key.load(h.get_key("test"))
        assert key.api_key == "test"
        assert key.is_admin() == False
        assert key.can_create_key() == False
        assert key.can_create_user() == False
        assert key.can_manage_all() == False
        assert key.can_read_all() == False
        assert key.can_write_all() == False
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == False
        assert key.can_write("test") == False
        assert key.can_write("test.test") == False
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_read_session1():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"read": ["test", "test1"]}, key="test")
        key = Key.load(h.get_key("test"))
        assert key.api_key == "test"
        assert key.is_admin() == False
        assert key.can_create_key() == False
        assert key.can_create_user() == False
        assert key.can_manage_all() == False
        assert key.can_read_all() == False
        assert key.can_write_all() == False
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == False
        assert key.can_write("test.test") == False
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_read_job():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"read": ["test.test"]}, key="test1")
        key = Key.load(h.get_key("test1"))
        assert key.can_read("test") == False
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == False
        assert key.can_write("test") == False
        assert key.can_write("test.test") == False
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_read_job2():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"read": ["test.test", "test1"]}, key="test1")
        key = Key.load(h.get_key("test1"))
        assert key.can_read("test") == False
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == False
        assert key.can_write("test.test") == False
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_read_job3():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"read": ["test.test", "test1.test"]}, key="test1")
        key = Key.load(h.get_key("test1"))
        assert key.can_read("test") == False
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == False
        assert key.can_write("test.test") == False
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_write_session():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"write": ["test"]}, key="test")
        key = Key.load(h.get_key("test"))
        assert key.api_key == "test"
        assert key.is_admin() == False
        assert key.can_create_key() == False
        assert key.can_create_user() == False
        assert key.can_manage_all() == False
        assert key.can_read_all() == False
        assert key.can_write_all() == False
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == False
        assert key.can_write("test") == True
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_write_session1():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"write": ["test", "test1"]}, key="test")
        key = Key.load(h.get_key("test"))
        assert key.api_key == "test"
        assert key.is_admin() == False
        assert key.can_create_key() == False
        assert key.can_create_user() == False
        assert key.can_manage_all() == False
        assert key.can_read_all() == False
        assert key.can_write_all() == False
        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == True
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == True
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False


def test_write_job():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"write": ["test.test"]}, key="test1")
        key = Key.load(h.get_key("test1"))
        assert key.can_read("test") == False
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == False
        assert key.can_write("test") == False
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == False
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_write_job2():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"write": ["test.test", "test1"]}, key="test1")
        key = Key.load(h.get_key("test1"))
        assert key.can_read("test") == False
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == True
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == False
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == True
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

def test_write_job3():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"write": ["test.test", "test1.test"]}, key="test1")
        key = Key.load(h.get_key("test1"))
        assert key.can_read("test") == False
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == False
        assert key.can_write("test.test") == True
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False


def test_mix():
    conf = test_config()
    loop = pyuv.Loop.default_loop()

    with KeyManager(loop, conf) as h:
        h.create_key({"read": ["test"], "write": ["test1.test"]}, key="test1")
        key = Key.load(h.get_key("test1"))

        assert key.can_read("test") == True
        assert key.can_read("test.test") == True
        assert key.can_read("test1") == False
        assert key.can_read("test1.test") == True
        assert key.can_write("test") == False
        assert key.can_write("test.test") == False
        assert key.can_write("test1") == False
        assert key.can_write("test1.test") == True
        assert key.can_manage("test") == False
        assert key.can_manage("test.test") == False
        assert key.can_manage("test1") == False
        assert key.can_manage("test1.test") == False

