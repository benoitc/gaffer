# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from functools import partial
import json

from .sockjs import SockJSConnection
from ..sync import increment, decrement
from ..error import ProcessError


class MessageError(Exception):
    """ raised on message error """

class SubscriptionError(Exception):
    """ raised on subscriptionError """

COMMANDS_TABLE= {
        "load": "add_template",
        "unload": "remove_template",
        "reload": "restart_template",
        "update": "update_template",
        "remove": "remove_template",
        "list": "list",
        "start": "start_template",
        "stop": "stop_template",
        "scale": "scale",
        "kill": "kill",
        "killall": "killall"}

class Subscription(object):

    def __init__(self, topic):
        self.topic = topic
        self.nb = 0
        self.callback = None

        parts = self.topic.split(":", 1)
        self.pid = None
        if len(parts) == 1:
            self.source = parts[0].upper()
            self.target = "."
        else:
            self.source, self.target = parts[0].upper(), parts[1].lower()
            if self.target.isdigit():
                self.pid = int(self.target)

    def __str__(self):
        return "subscription: %s" % self.topic


class Message(object):

    def __init__(self, msg):
        if not isinstance(msg, dict):
            try:
                msg = json.loads(msg)
            except ValueError:
                raise MessageError("invalid_json")

        self.msg = msg
        try:
            self.event = msg['event']
        except KeyError:
            raise MessageError("event_missing")

        if self.event == "NOP":
            self.nop = True
        else:
            self.nop = False
            self.parse_message(msg)

    def parse_message(self, msg):
        try:
            self.data = msg['data']
        except KeyError:
            raise MessageError("data_missing")

        if self.event in ("SUB", "UNSUB"):
            if "topic" not in self.data:
                raise MessageError("topic_missing")

            self.topic = self.data['topic']

        elif self.event == "CMD":
            if "name" not in self.data:
                raise MessageError("cmd_name_mssing")

            self.name = self.data['name']
            if self.name not in self.COMMANDS_TABLE:
                raise MessageError("cmd_notfound")

            self.args = self.data.get('args', ())
            self.kwargs = self.data.get('kwargs', {})
        else:
            raise MessageError("unknown_cmd")

    def __str__(self):
        if self.event in ("SUB", "UNSUB"):
            return "%s: %s" % (self.event, self.data['event'])
        elif self.event == "CMD":
            return "%s: %s" % (self.event, self.data['cmd'])

        return self.event


class ChannelConnection(SockJSConnection):

    def on_open(self, info):
        self.manager = self.session.server.settings.get('manager')
        self._subscriptions = {}

    def on_message(self, raw):
        print(raw)
        try:
            msg = Message(raw)
        except MessageError as e:
            return self.write_message(_error_msg(error="invalid_msg",
                reason=str(e)))

        if msg.nop:
            return

        try:
            if msg.event == "SUB":
                self.add_subscription(msg.topic)
            elif msg.event == "UNSUB":
                self.del_subscription(msg.topic)
            elif msg == "CMD":
                ret = self.process_command(msg)
        except ProcessError as e:
            return self.write_message(_error_msg(event="command_error",
                reason=e.reason, errno=e.errno))
        except SubscriptionError as e:
            return self.write_message(_error_msg(event="subscription_error",
                reason=str(e)))

        if msg.event == "SUB":
            self.write_message({"event": "gaffer:subscription_success"})
        elif msg.event == "UNSUB":
            self.write_message({"event": "gaffer:subscription_success"})
        elif msg.event == "CMD":
            self.write_message({"event": "gaffer:command_success",
                "result": ret})

    def process_command(self, msg):
        meth = getattr(self.manager, msg.name)
        return meth(*msg.args, **msg.kwargs)

    def add_subscription(self, topic):
        print("add subscription")
        if topic in self._subscriptions:
            sub = self._subscriptions[topic]
        else:
            sub = self._subscriptions[topic] = Subscription(topic)

        if not sub.nb:
            self.start_subscription(sub)

        sub.nb = increment(sub.nb)

    def del_subscription(self, topic):
        if topic not in self._subscriptions:
            return

        sub = self._subscriptions[topic]
        sub.nb = decrement(sub.nb)

        if not sub.nb:
            self.stop_subcription(sub)
            del self._subscriptions[sub]

    def start_subscription(self, sub):
        if sub.source == "EVENTS":
            sub.callback = partial(self._dispatch_event, sub.topic)
            # subscribe to all manager events
            self.manager.events.subscribe(sub.target, sub.callback)
        elif sub.source == "JOB":
            sub.callback = partial(self._dispatch_process_event, sub.topic)
            self.manager.events.subscribe("job.%s" % sub.target, sub.callback)
        elif sub.source == "PROCESS":
            sub.callback = partial(self._dispatch_process_event, sub.topic)
            self.manager.events.subscribe("proc.%s" % sub.target, sub.callback)
        elif sub.source == "STATS":
            if sub.pid is not None:
                sub.callback = partial(self._dispatch_event, sub.topic)
                # subscribe to the pid stats
                proc = self.manager.get_process(sub.pid)
                proc.monitor(sub.callback)
            else:
                sub.callback = partial(self._dispatch_event, sub.topic)
                # subscribe to the group stats
                aname, tname = sub.target.split(".")
                t = self.manager.get_template(tname, aname)
                for proc in t.running:
                    proc.monitor(sub.callback)
        elif sub.source == "STREAM":
            if not sub.pid:
                raise SubscriptionError("invalid_topic")

            sub.callback = partial(self._dispatch_event, sub.topic)

            proc = self.manager.get_process(sub.pid)
            proc.monitor_io(sub.target, sub.callback)
        else:
            raise SubscriptionError("invalid_topic")

    def stop_subscription(self, sub):
        if sub.source == "EVENTS":
            self.manager.events.unsubscribe(sub.target, sub.callback)
        elif sub.source == "JOB":
            self.manager.events.unsubscribe("job.%s" % sub.target,
                    sub.callback)
        elif sub.source == "PROCESS":
            self.manager.events.unsubscribe("proc.%s" % sub.target,
                    sub.callback)
        elif sub.source == "STATS":
            if sub.pid is not None:
                proc = self.manager.get_process(sub.pid)
                proc.unmonitor(sub.callback)
            else:
                aname, tname = sub.target.split(".")
                t = self.manager.get_template(tname, aname)
                for proc in t.running:
                    proc.unmonitor(sub.callback)
        elif sub.source == "STREAM":
            if sub.pid:
                proc = self.manager.get_process(sub.pid)
                proc.unmonitor_io(".", sub.callback)

    def _dispatch_event(self, topic, evtype, ev):
        data = { "event": evtype, "topic": topic}
        data.update(ev)
        msg = { "event": "gaffer:event", "data": data}
        self.write_message(msg)

    def _dispatch_process_events(self, topic, evtype, ev):

        try:
            sub = self._subscriptions[topic]
        except KeyError:
            return

        evtype = evtype.split("proc.%s." % sub.target, 1)[1]
        self._dispatch_event(topic, evtype, ev)

    def write_message(self, msg):
        if isinstance(msg, dict):
            self.send(json.dumps(msg))
        else:
            self.send(msg)

def _error_msg(event="gaffer:error", **data):
    msg =  { "event": event, "data": data }
    return json.dumps(msg)
