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
from collections import deque
import json
from threading import RLock
import time

import pyuv

from tornado.httpclient import HTTPError

from .httpclient import HTTPClient
from .sync import atomic_read, increment, decrement

class WebHooks(object):
    """ webhook app """

    def __init__(self, hooks=[]):
        self.events = {}
        self._refcount = 0
        self._active = 0
        self._jobcount = 0
        self._queue = deque()
        self._lock = RLock()

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
        self._pool = pyuv.ThreadPool(self.loop)
        self.maybe_start_monitor()

    def stop(self):
        """ stop the webhook app, stop monitoring to events """
        self._stop_monitor()
        self._queue.clear()
        if self.jobcount > 0:
            while self.jobcount > 0:
                time.sleep(0.01)

    def restart(self):
        self._stop_monitor()
        self._start_monitor()

    def close(self):
        self.stop()
        with self._lock:
            self.events = []
            self._refcount = 0
            self._queue.clear()

    @property
    def active(self):
        return atomic_read(self._active) > 0

    @property
    def refcount(self):
        return atomic_read(self._refcount)

    @property
    def jobcount(self):
        return atomic_read(self._jobcount)

    def register_hook(self, event, url):
        """  associate an url to an event """
        with self._lock:
            if event not in self.events:
                self.events[event] = set()
            self.events[event].add(url)

        self.incref()
        self.maybe_start_monitor()

    def unregister_hook(self, event, url):
        """ unregister an url for this event """
        with self._lock:
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

        with self._lock:
            self._jobcount = increment(self._jobcount)
            self._queue.append((msg, urls))
            self._pool.queue_work(self._send, self._sent)

    def _sent(self, res, exc):
        self._jobcount = decrement(self._jobcount)

    def _send(self):
        try:
            msg, urls = self._queue.popleft()
        except IndexError:
            return


        body = json.dumps(msg)
        headers = { "Content-Length": str(len(body)),
                    "Content-Type": "application/json" }

        client = HTTPClient()
        for url in urls:
            try:
                client.fetch(url, method="POST", headers=headers,
                        body=body)
            except HTTPError as e:
                # for now we ignore all http errors.
                pass

    def _start_monitor(self):
        with self._lock:
            self.manager.subscribe(".", self._on_event)
            self._active = increment(self._active)

    def _stop_monitor(self):
        with self._lock:
            self.manager.unsubscribe(".", self._on_event)
        self._active = decrement(self._active)
