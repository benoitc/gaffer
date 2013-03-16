# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
Webhooks allow to register an url to a specific event (or alls) and the
event will be posted on this URL. Each events can triger a post on a
given url.

for example to listen all create events on http://echohttp.com/echo you
can add this line in the webhooks sections of the gaffer setting file::

    [webhooks]
    create = http://echohttp.com/echo you

Or programatically::

    from gaffer.manager import Manager
    from gaffer.webhooks import WebHooks
    hooks = [("create", "http://echohttp.com/echo you ")
    webhooks = WebHooks(hooks=hooks)

    manager = Manager()
    manager.start(apps=[webhooks])


This gaffer application is started like other applications in the
manager. All :doc:`events` are supported.


The :mod:`webhooks` Module
--------------------------

"""
from functools import partial
import json

from tornado.httpclient import HTTPError

from .httpclient import HTTPClient
from .sync import atomic_read, increment, decrement

class WebHooks(object):
    """ webhook app """

    def __init__(self, hooks=[]):
        self.events = {}
        self._refcount = 0
        self.active = False

        # initialize hooks
        for event, url in hooks:
            if not event in self.events:
                self.events[event] = set()
            self.events[event].add(url)
            self.incref()

    def start(self, loop, manager):
        """ start the webhook app """
        self.loop = loop
        self.manager = manager
        self.maybe_start_monitor()

    def stop(self):
        """ stop the webhook app, stop monitoring to events """
        if self.active:
            self._stop_monitor()

    def restart(self):
        self._stop_monitor()
        self._start_monitor()

    def close(self):
        self.stop()
        self.events = []
        self._refcount = 0

    @property
    def refcount(self):
        return atomic_read(self._refcount)

    def register_hook(self, event, url):
        """  associate an url to an event """
        if event not in self.events:
            self.events[event] = set()

        self.events[event].add(url)

        self.incref()
        self.maybe_start_monitor()

    def unregister_hook(self, event, url):
        """ unregister an url for this event """
        if event not in self.events:
            return

        # remove an url from registered hooks
        urls = self.events[event]
        urls.remove(url)
        self.events[event] = urls

        self.decref()
        self.maybe_stop_monitor()

    def maybe_start_monitor(self):
        if self.refcount and not self.active:
            self._start_monitor()

    def maybe_stop_monitor(self):
        if self.refcount > 0 or not self.active:
            return

        self._stop_monitor()

    def incref(self):
        self._refcount = increment(self._refcount)

    def decref(self):
        self._refcount = decrement(self._refcount)

    def _on_event(self, event, msg):
        if not self.active:
            return

        urls = set()
        if event in self.events:
            urls = self.events[event]

        if "." in self.events:
            urls = urls.union(self.events['.'])

        if not urls:
            return

        # queue the hook, it will be executed in a thread asap
        callback = partial(self._post_hook, msg, urls)
        self.loop.queue_work(callback)

    def _post_hook(self, msg, urls):
        body = json.dumps(msg)
        headers = { "Content-Length": str(len(body)),
                    "Content-Type": "application/json" }

        client = HTTPClient()
        for url in urls:
            try:
                client.fetch(url, method="POST", headers=headers,
                        body=body)
            except HTTPError:
                # for now we ignore all http errors.
                pass

    def _start_monitor(self):
        self.manager.events.subscribe(".", self._on_event)
        self.active = True

    def _stop_monitor(self):
        self.manager.events.unsubscribe(".", self._on_event)
        self.active = False
