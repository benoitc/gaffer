# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import deque
import heapq
import operator
import signal
from threading import RLock
import time

import pyuv

from .sync import add, sub, increment, atomic_read
from .util import nanotime

class ProcessTracker(object):

    def __init__(self, loop):
        self.processes = []
        self._done_cb = None
        self._check_timer = pyuv.Timer(loop)
        self._lock = RLock()

    def start(self, interval=0.1):
        self._check_timer.start(self._on_check, interval, interval)
        self._check_timer.unref()

    def on_done(self, callback):
        self._done_cb = callback

    def stop(self):
        self._check_timer.stop()
        self.processes = []

    def close(self):
        self.processes = []
        self._done_cb = None
        if not self._check_timer.closed:
            self._check_timer.close()

    def check(self, process, graceful_timeout=10000000000):
        process.graceful_time = graceful_timeout + nanotime()
        heapq.heappush(self.processes, process)

    def uncheck(self, process):
        if process in self.processes:
            del self.processes[operator.indexOf(self.processes, process)]

    def _on_check(self, handle):
        # this function check if a process that need to be stopped after
        # a given graceful time is still in the stopped process. If yes
        # the process is killed. It let the possibility to let the time
        # to some worker to quit.
        #
        # The garbage collector run eveyry 0.1s .
        with self._lock:
            while True:
                if not len(self.processes):
                    # done callback has been set, run it
                    if self._done_cb is not None:
                        self._done_cb()
                        self._donc_cb = None

                    # nothing in the queue, quit
                    break

                # check the diff between the time it is now and the
                # graceful time set when the worker was stopped
                p = heapq.heappop(self.processes)
                now = nanotime()
                delta = p.graceful_time - now
                if delta > 0:
                    # we have anything to do, put the process back in
                    # the heap and return
                    if p.active:
                        heapq.heappush(self.processes, p)
                    break
                else:
                    # a process need to be kill. Send a SIGKILL signal
                    try:
                        p.kill(signal.SIGKILL)
                    except:
                        pass

                    # and close it. (maybe we should just close it)
                    p.close()


class FlappingInfo(object):
    """ object to keep flapping infos """

    def __init__(self, attempts=2, window=1., retry_in=7., max_retry=5):
        self.attempts = attempts
        self.window = window
        self.retry_in = retry_in
        self.max_retry = max_retry

        # exit history
        self.history = deque(maxlen = max_retry)
        self.retries = 0

    def reset(self):
        self.history.clear()
        self.retries = 0

class ProcessState(object):
    """ object used by the manager to maintain the process state for a
    session. """


    def __init__(self, config, sessionid, env=None):
        self.config = config
        self.sessionid = sessionid
        self.env = env

        self.running = deque()
        self.running_out = deque()
        self.stopped = False
        self.setup()

    def setup(self):
        self.name = "%s.%s" % (self.sessionid, self.config.name)
        self.cmd = self.config.cmd
        self._numprocesses = self.config.get('numprocesses', 1)

        # set flapping
        self.flapping = self.config.get('flapping')
        if isinstance(self.flapping, dict):
            try:
                self.flapping = FlappingInfo(**self.flapping)
            except TypeError: # unknown value
                self.flapping = None

        self.flapping_timer = None
        self.stopped = False

    @property
    def active(self):
        return (len(self.running) + len(self.running_out)) > 0

    @property
    def graceful_timeout(self):
        return nanotime(self.config.get('graceful_timeout', 10.0))

    def __str__(self):
        return "state: %s" % self.name

    def make_process(self, loop, id, on_exit):
        """ create an OS process using this template """
        return self.config.make_process(loop, id, self.name, env=self.env,
                on_exit=on_exit)

    def __get_numprocesses(self):
        return atomic_read(self._numprocesses)
    def __set_numprocesses(self, n):
        self._numprocesses = n
    numprocesses = property(__get_numprocesses, __set_numprocesses,
            doc="""return the max numbers of processes that we keep
            alive for this command""")

    @property
    def pids(self):
        pids = [p.pid for p in self.running]
        pids.extend([p.pid for p in self.running_out])
        return pids

    def reset(self):
        """ reset this template to default values """
        self.numprocesses = self.config.get('numprocesses', 1)
        # reset flapping
        if self.flapping and self.flapping is not None:
            self.flapping.reset()

    def update(self, config, env=None):
        """ update a state """
        self.config = config
        self.env = env

        # update the number of preocesses
        self.numprocesses = max(self.config.get('numprocesses', 1),
                self.numprocesses)

    def incr(self, i=1):
        """ increase the maximum number of running processes """

        self._numprocesses = add(self._numprocesses, i)
        return self._numprocesses

    def decr(self, i=1):
        """ decrease the maximum number of running processes """
        self._numprocesses = sub(self._numprocesses, i)
        return self._numprocesses

    def queue(self, process):
        """ put one OS process in the running queue """
        self.running.append(process)

    def dequeue(self):
        """ retrieved one OS process from the queue (FIFO) """
        return self.running.popleft()

    def remove(self, process):
        """ remove an OS process from the running processes """
        try:
            self.running.remove(process)
        except ValueError:
            pass

    def list_processes(self):
        return list(self.running)

    def check_flapping(self):
        """ main function used to check the flapping """
        f = self.flapping

        f.history.append(time.time())
        if len(f.history) >= f.attempts:
            diff = f.history[-1] - f.history[0]
            if diff > f.window:
                f.reset()
                self.flapping = f
            elif f.retries < f.max_retry:
                f.retries = increment(f.retries)
                self.flapping = f
                return False, True
            else:
                f.reset()
                self.flapping = f
                return False, False
        self.flapping = f
        return True, None
