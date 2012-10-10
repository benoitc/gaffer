# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import time


import pyuv

from gaffer.events import EventEmitter


def test_basic():
    emitted = []
    loop = pyuv.Loop.default_loop()

    def cb():
        emitted.append(True)

    emitter = EventEmitter(loop)
    emitter.subscribe("test", cb)

    assert "test" in emitter._events
    assert emitter._events["test"] == set([(False, cb)])

    emitter.publish("test")
    loop.run()

    assert emitted == [True]
    assert "test" in emitter._events
    assert emitter._events["test"] == set([(False, cb)])
    assert emitter._triggered == []


def test_publish_value():
    emitted = []
    loop = pyuv.Loop.default_loop()
    def cb(val):
        emitted.append(val)

    emitter = EventEmitter(loop)
    emitter.subscribe("test", cb)
    emitter.publish("test", 1)
    emitter.publish("test", 2)
    loop.run()

    assert emitted == [1, 2]

def test_publish_once():
    emitted = []
    loop = pyuv.Loop.default_loop()
    def cb(val):
        emitted.append(val)

    emitter = EventEmitter(loop)
    emitter.subscribe_once("test", cb)
    emitter.publish("test", 1)
    loop.run()

    assert emitted == [1]
    assert emitter._events["test"] == set()


def test_multiple_listener():
    emitted = []

    loop = pyuv.Loop.default_loop()
    def cb1(val):
        emitted.append((1, val))

    def cb2(val):
        emitted.append((2, val))

    emitter = EventEmitter(loop)
    emitter.subscribe("test", cb1)
    emitter.subscribe("test", cb2)
    emitter.publish("test", 1)
    loop.run()

    assert (1, 1) in emitted
    assert (2, 1) in emitted


def test_multipart():
    emitted = []
    emitted2 = []
    loop = pyuv.Loop.default_loop()

    def cb1(val):
        emitted.append(val)

    def cb2(val):
        emitted2.append(val)

    emitter = EventEmitter(loop)
    emitter.subscribe("a.b", cb1)
    emitter.subscribe("a", cb2)
    emitter.publish("a.b", 1)
    emitter.publish("a", 2)
    loop.run()

    assert emitted == [1]
    assert 1 in emitted2
    assert 2 in emitted2
