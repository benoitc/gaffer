# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

"""
Many events happend in gaffer.


Manager events
--------------

Manager events have the following format::

    {
      "event": "<nameofevent">>,
      "name": "<templatename>"
    }

- **create**: a process template is created
- **start**: a process template start to launch OS processes
- **stop**: all OS processes of a process template are stopped
- **restart**: all processes of a process template are restarted
- **update**: a process template is updated
- **delete**: a process template is deleted

Processes events
----------------

All processes' events are prefixed by ``proc.<name>`` to make the pattern
matching easier, where ``<name>`` is the name of the process template

Events are:

- **proc.<name>.start** : the template <name> start to spawn processes
- **proc.<name>.spawn** : one OS process using the process <name>
  template is spawned. Message is::

    {
      "event": "proc.<name>.spawn">>,
      "name": "<name>",
      "detach": false,
      "pid": int
    }


  .. note::

    pid is the internal pid
- **proc.<name>.exit**: one OS process of the <name> template has
  exited. Message is::

    {
      "event": "proc.<name>.exit">>,
      "name": "<name>",
      "pid": int,
      "exit_code": int,
      "term_signal": int
    }

- **proc.<name>.stop**: all OS processes in the template <name> are
  stopped.
- **proc.<name>.stop_pid**: One OS process of the template <name> is
  stopped. Message is::

    {
      "event": "proc.<name>.stop_pid">>,
      "name": "<name>",
      "pid": int
    }

- **proc.<name>.stop_pid**: One OS process of the template <name> is
  reapped. Message is::

    {
      "event": "proc.<name>.reap">>,
      "name": "<name>",
      "pid": int
    }


The :mod:`events` Module
------------------------


This module offeres a common way to susbscribe and emit events. All
events in gaffer are using.

Example of usage
++++++++++++++++

::

        event = EventEmitter()

        # subscribe to all events with the pattern a.*
        event.subscribe("a", subscriber)

        # subscribe to all events "a.b"
        event.subscribe("a.b", subscriber2)

        # subscribe to all events (wildcard)
        event.subscribe(".", subscriber3)

        # publish an event
        event.publish("a.b", arg, namedarg=val)

In this example all subscribers will be notified of the event. A
subscriber is just a callable *(event, *args, **kwargs)*

Classes
-------

"""

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
            self._publish(parts[0], evtype, *args, **kwargs)
            key = []
            for part in parts:
                key.append(part)
                self._publish(".".join(key), evtype, *args, **kwargs)
        else:
            self._publish(evtype, evtype, *args, **kwargs)

        # emit the event for wildcards events
        self._publish_wildcards(evtype, *args, **kwargs)

    def _publish(self, pattern, evtype, *args, **kwargs):
        if pattern in self._events:
            self._queue.append((pattern, evtype, args, kwargs))

            idle = pyuv.Idle(self.loop)
            idle.start(self._send)
            self._triggered.append(idle)

    def _publish_wildcards(self, evtype, *args, **kwargs):
        if self._wildcards:
            self._wqueue.append((evtype, args, kwargs))

            idle = pyuv.Idle(self.loop)
            idle.start(self._send_wildcards)
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
            pattern, evtype, args, kwargs = self._queue.popleft()
        except IndexError:
            return

        # emit the event to all listeners
        if pattern in self._events:
            self._events[pattern] = self._send_listeners(evtype,
                self._events[pattern].copy(), *args, **kwargs)

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

        if evtype.endswith("."):
            evtype = evtype[:-1]

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
