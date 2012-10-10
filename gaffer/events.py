# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import deque
from threading import RLock

import pyuv

class EventEmitter(object):
    """ Many events happend in gaffer. For example a process will emist
    the events "start", "stop", "exit".

    This object offer a common interface to all events emitters """

    def __init__(self, loop, max_size=200):
        self.loop = loop
        self._events = {}
        self._wildcards = set()
        self._lock = RLock()

        self._triggered = []
        self._queue = deque(maxlen=max_size)
        self._wqueue = deque(maxlen=max_size)

    def close(self):
        """ close the event

        This function clear the list of listeners and stop all idle
        callback """
        with self._lock:
            self._wqueue.clear()
            self._queue.clear()
            self._events = {}
            self._wildcards = set()

            # it will be garbage collected later
            self._triggered = []

    def publish(self, evtype, *args, **kwargs):
        """ emit an event **evtype**

        The event will be emitted asynchronously so we don't block here
        """
        if "." in evtype:
            parts = evtype.split(".")
            self._publish(parts[0], *args, **kwargs)
            key = []
            for part in parts:
                key.append(part)
                self._publish(".".join(key), *args, **kwargs)
        else:
            self._publish(evtype, *args, **kwargs)

        # emit the event for wildcards events
        self._publish_wildcards(evtype, *args, **kwargs)

    def _publish(self, evtype, *args, **kwargs):
        if evtype in self._events:
            self._queue.append((evtype, args, kwargs))

            idle = pyuv.Idle(self.loop)
            idle.start(self._send)
            idle.unref()
            self._triggered.append(idle)

    def _publish_wildcards(self, evtype, *args, **kwargs):
        if self._wildcards:
            self._wqueue.append((evtype, args, kwargs))

            idle = pyuv.Idle(self.loop)
            idle.start(self._send_wildcards)
            idle.unref()
            self._triggered.append(idle)

    def _send_wildcards(self, handle):
        # find an event to send
        try:
            evtype, args, kwargs = self._wqueue.popleft()
        except IndexError:
            return

        if self._wildcards:
            self._wildcards = self._send_listeners(evtype,
                    self._wildcards.copy(), *args, **kwargs)

        # close the handle and removed it from the list of triggered
        self._triggered.remove(handle)
        handle.close()


    def _send(self, handle):
        # find an event to send
        try:
            evtype, args, kwargs = self._queue.popleft()
        except IndexError:
            return

        # emit the event to all listeners
        if evtype in self._events:
            self._events[evtype] = self._send_listeners(evtype,
                self._events[evtype].copy(), *args, **kwargs)

        # close the handle and removed it from the list of triggered
        self._triggered.remove(handle)
        handle.close()

    def _send_listeners(self, evtype, listeners, *args, **kwargs):
        to_remove = []
        for once, listener in listeners:
            try:
                listener(evtype, *args, **kwargs)
            except Exception as e: # we ignore all exception
                to_remove.append(listener)

            if once:
                # once event
                to_remove.append(listener)

        if to_remove:
            for listener in to_remove:
                try:
                    listeners.remove((True, listener))
                except KeyError:
                    pass
        return listeners


    def subscribe(self, evtype, listener, once=False):
        """ subcribe to an event """

        if evtype == ".": # wildcard
            self._wildcards.add((once, listener))
            return

        if evtype not in self._events:
            self._events[evtype] = set()

        self._events[evtype].add((once, listener))

    def subscribe_once(self, evtype, listener):
        """ subscribe to event once.
        Once the evennt is triggered we remove ourself from the list of
        listenerrs """

        self.subscribe(evtype, listener, True)

    def unsubscribe(self, evtype, listener):
        """ unsubscribe from an event"""
        if evtype not in self._events:
            return

        with self._lock:
            try:
                self._events[evtype].remove(listener)
            except KeyError:
                pass

    def unsubscribe_all(self, events=[]):
        """ unsubscribe all listeners from a list of events """
        for evtype in events:
            if evtype == ".":
                self._wildcards = set()
            else:
                self._events[evtype] = set()
