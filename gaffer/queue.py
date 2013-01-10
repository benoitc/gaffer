# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import deque
import sys

import pyuv

class AsyncQueue(object):
    """ Asynchronous queue used to receive messages

    Like ``gaffer.events.EventEmitter`` but a lot simpler, AsyncQueue allows you
    to queue messages that will be handled later by the application::

        # callback for the queue
        def cb(msg, err):
            if err is None:
                # ... do something with the message
                print(msg)
            else:
                (exc_type, exc_value, exc_traceback) = err
                # ... do something with the error

        # define the queue
        q = AsyncQueue(loop, cb)

        # ... send a message
        q.send("some message")
    """

    def __init__(self, loop, callback):
        self.loop = loop
        self._queue = deque()
        self._dispatcher = pyuv.Prepare(self.loop)
        self._spinner = pyuv.Idle(self.loop)
        self._tick = pyuv.Async(loop, self._do_send)
        self._callback = callback

    def send(self, msg):
        """ add a message to the queue

        Send is the only threadsafe method of this queue. It means that any
        thread can send a message.

        """
        self._queue.append(msg)
        self._tick.send()

    def close(self):
        """ close the queue """
        self._queue.clear()
        self._dispatcher.close()
        self._spinner.close()
        self._tick.close()

    def _do_send(self, handle):
        if not self._dispatcher.active:
            self._dispatcher.start(self._send)
            self._spinner.start(lambda h: h.stop())

    def _send(self, handle):
        queue, self._queue = self._queue, deque()
        for msg in queue:
            try:
                self._callback(msg, None)
            except:
                self._callback(msg, sys.exc_info())

        self._dispatcher.stop()
