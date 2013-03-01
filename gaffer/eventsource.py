# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

from tornado.httpclient import HTTPRequest, AsyncHTTPClient

from .events import EventEmitter
from .loop import patch_loop
from .tornado_pyuv import IOLoop

class EventsourceClient(object):
    """ simple client to fetch Gaffer streams using the eventsource
    stream.

    Example of usage::

        loop = pyuv.Loop.default_loop()

        def cb(event, data):
            print(data)

        # create a client
        url = http://localhost:5000/streams/1/stderr?feed=continuous'
        client = EventSourceClient(loop, url)

        # subscribe to the stderr event
        client.subscribe("stderr", cb)

        # start the client
        client.start()

    """

    def __init__(self, loop, url, **kwargs):
        self.loop = patch_loop(loop)
        self._io_loop = IOLoop(_loop=loop)
        self.url = url
        self._emitter = EventEmitter(self.loop)
        self.client = AsyncHTTPClient(self._io_loop, **kwargs)
        self.active = False
        self.stopped = False

    def start(self):
        self.active = True
        headers = {"Content-Type": "text/event-stream"}
        req = HTTPRequest(url=self.url,
                                        method='GET',
                                        headers=headers,
                                        request_timeout=0,
                                        streaming_callback=self._on_stream)

        self.client.fetch(req, self._on_request)
        self._io_loop.start(False)

    def subscribe(self, event, listener):
        self._emitter.subscribe(event, listener)

    def unsubscribe(self, event, listener):
        self._emitter.unsubscribe(event, listener)

    def subscribe_once(self, event, listener):
        self._emitter.subscribe_once(event, listener)

    def render(self, event, data):
        return data

    def stop(self):
        self.active = False
        #self._emitter.close()
        self.client.close()
        self._io_loop.stop()
        self._io_loop.close(True)

    def run(self):
        self.loop.run()

    def _on_request(self, response):
        self.stop()

    def _on_stream(self, message):
        if not message:
            return
        lines = [line for line in message.strip(b'\r\n').split(b"\r\n")]

        event = None
        data = []
        for line in lines:
            f, val = line.split(b":", 1)
            if f == b"event":
                event = val.strip()
            elif f == b"data":
                data.append(val.strip())
        if event is None:
            return

        event = event.decode('utf-8')
        data = self.render(event, b"\n".join(data).strip())
        self._emitter.publish(event, data)

class Watcher(EventsourceClient):
    """ simple EventsourceClient wrapper that decode the JSON to a
    python object """

    def render(self, event, data):
        return json.loads(data.decode('utf-8'))
