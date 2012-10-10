# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import pyuv

from gaffer.events import EventEmitter


def test_basic():
    emitted = []
    loop = pyuv.Loop.default_loop()

    def cb(ev):
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
    def cb(ev, val):
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
    def cb(ev, val):
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
    def cb1(ev, val):
        emitted.append((1, val))

    def cb2(ev, val):
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

    def cb1(ev, val):
        emitted.append(val)

    def cb2(ev, val):
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


def test_multipart2():
    emitted = []
    loop = pyuv.Loop.default_loop()

    def cb(ev, val):
        emitted.append(ev)

    emitter = EventEmitter(loop)
    emitter.subscribe("a.b", cb)
    emitter.publish("a.b.c", 2)
    loop.run()

    assert emitted == ['a.b.c']

def test_wildcard():
    loop = pyuv.Loop.default_loop()
    emitted = []
    emitted2 = []
    emitted3 = []

    def cb(ev, val):
        emitted.append(val)

    def cb2(ev, val):
        emitted2.append(val)

    def cb3(ev, val):
        emitted3.append(val)


    emitter = EventEmitter(loop)
    emitter.subscribe(".", cb)
    emitter.subscribe("a.b", cb2)
    emitter.subscribe("a.b.", cb3)

    assert emitter._wildcards == set([(False, cb)])

    emitter.publish("a.b", 1)
    loop.run()

    assert emitted == [1]
    assert emitted2 == [1]
    assert emitted3 == [1]
