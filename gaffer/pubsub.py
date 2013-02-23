# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from functools import partial

from .error import TopicError
from .events import EventEmitter

class EventChannel(object):
    """ An event channel.

    This channel is used to collect global or process events """

    def __init__(self, topic):
        self.topic = topic
        self._emitter = EventEmitter(topic.manager.loop)

    def bind(self, event, callback):
        self._emitter.subscribe(event, callback)

    def unbind(self, event, callback):
        self._emitter.unsubscribe(event, callback)

    def bind_all(self, callback):
        self._emitter.subscribe(".", callback)

    def unbind_all(self, callback):
        self._emitter.unsubscribe(".", callback)

    def close(self):
        self._emitter.close()
        self.topic.unsubscribe(self)

    def dispatch_event(self, evtype, event):
        self._emitter.publish(evtype, event)


class StatChannel(object):
    """ a channel to collect stats.

    This channel is used to collect stats or stream data. """

    def __init__(self, topic):
        self.topic = topic
        self._emitter = EventEmitter(topic.manager.loop)

    def bind(self, callback):
        self._emitter.subscribe("DATA", partial(self._on_message, callback))

    def unbind(self, callback):
        self._emitter.unsubscribe("DATA", partial(self._on_message, callback))

    def close(self):
        self._emitter.close()
        self.topic.unsubscribe(self)

    def dispatch_message(self, message):
        self._emitter.publish("DATA", message)

    def _on_message(self, callback, evtype, msg):
        callback(msg)


class Topic(object):
    """ A subscribed topic.

    A topic receive events and dispatch to all subscribed channels

    Available topics:

    - ``EVENTS``: all the manager events.
    - ``PROCESS:<PID>``: manager events for a pid
    - ``PROCESS:<APPNAME>.<PROCESSNAME>`` manager events for all pids
      associated to ``<APPNAME>.<PROCESSNAME>``
    - ``STATS:<PID>``: collect stats for this pid
    - ``STATS:<APPNAME>.<PROCNAME>``: collect stats for all pids associated to
      ``<APPNAME>.<PROCESSNAME>``
    - ``STREAM:<PID>`` -> get streams for this pid

    ``<PID>``: process ID
    ``<APPNAME>``: name of the app
    ``<PROCNAME>``: template name
    """

    def __init__(self, name, manager):
        self.name = name
        self.manager = manager

        parts = self.name.split(":", 1)
        self.pid = None
        if len(parts) == 1:
            self.source = parts[0].upper()
            self.target = "."
        else:
            self.source, self.target = parts[0].upper(), parts[1].lower()
            if self.target.isdigit():
                self.pid = int(self.target)

        self.channels = set()
        self.active = False

    def start(self):
        if self.active:
            return

        if self.source == "EVENTS":
            self.manager.events.subscribe(self.target, self._dispatch_events)
        elif self.source == "PROCESS":
            self.manager.events.subscribe("proc.%s" % self.target,
                    self._dispatch_process_events)
        elif self.source == "JOB":
            self.manager.events.subscribe("job.%s" % self.target,
                    self._dispatch_job_events)
        elif self.source == "STATS":
            if self.pid is not None:
                proc = self.manager.get_process(self.pid)
                proc.monitor(self._dispatch_data)
            else:
                state = self.manager._get_locked_state(self.target)
                for proc in state.running:
                    proc.monitor(self._dispatch_data)
        elif self.source == "STREAM":
            if not self.pid:
                raise TopicError(400, "invalid topic")

            proc = self.manager.get_process(self.pid)
            proc.monitor_io(self.target, self._dispatch_data)
        else:
            raise TopicError(400, "invalid topic")

        self.active = True

    def stop(self):
        if not self.active:
            return

        if self.source == "EVENTS":
            self.manager.events.unsubscribe(self.target,
                    self._dispatch_events)
        elif self.source == "PROCESS":
            self.manager.events.unsubscribe("proc.%s" % self.target,
                    self._dispatch_process_events)
        elif self.source == "JOB":
            self.manager.events.unsubscribe("job.%s" % self.target,
                    self._dispatch_process_events)
        elif self.source == "STATS":
            if self.pid is not None:
                proc = self.manager.get_process(self.pid)
                proc.unmonitor(self._dispatch_data)
            else:
                state = self.manager._get_locked_state(self.target)
                for proc in state.running:
                    proc.unmonitor(self._dispatch_data)
        elif self.source == "STREAM":
            if self.pid:
                proc = self.manager.get_process(self.pid)
                proc.unmonitor_io(".", self._dispatch_events)

        self.active = False

    def close(self):
        if not self.active:
            return

        self.stop()

        for chan in self.channels:
            try:
                chan.close()
            except:
                pass

    def subscribe(self):
        if not self.active:
            self.start()

        if self.source in ("EVENTS", "PROCESS", "JOB", "STREAM"):
            chan = EventChannel(self)
        else:
            chan = StatChannel(self)

        self.channels.add(chan)
        return chan

    def unsubscribe(self, chan):
        self.channels.remove(chan)
        if not self.channels:
            self.stop()

    def _dispatch_events(self, evtype, event):
        for c in self.channels:
            c.dispatch_event(evtype, event)

    def _dispatch_process_events(self, evtype, event):
        evtype = evtype.split("proc.%s." % self.target, 1)[1]
        self._dispatch_events(evtype, event)

    def _dispatch_job_events(self, evtype, event):

        evtype = evtype.split("job.%s." % self.target, 1)[1]
        self._dispatch_events(evtype, event)

    def _dispatch_data(self, evtype, data):
        for c in self.channels:
            c.dispatch_message(data)
