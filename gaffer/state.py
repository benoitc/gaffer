# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import deque
import heapq
import operator
import os
import signal
from threading import RLock
import time

import pyuv

from .process import Process
from .sync import add, sub, increment, atomic_read, compare_and_swap
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

    def close(self):
        self.processes = []
        self._done_cb = None
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
    """ object used by the manager to maintain the process state """

    DEFAULT_PARAMS = {
            "group": None,
            "args": None,
            "uid": None,
            "gid": None,
            "cwd": None,
            "detach": False,
            "shell": False,
            "redirect_output": [],
            "redirect_input": False}

    def __init__(self, name, cmd, **settings):
        self.running = deque()
        self.stopped = False
        self.setup(name, cmd, **settings)

    def setup(self, name, cmd, **settings):
        self.name = name
        self.cmd = cmd
        self.settings = settings
        self._numprocesses = self.settings.get('numprocesses', 1)

        # set flapping
        self.flapping = self.settings.get('flapping')
        if isinstance(self.flapping, dict):
            try:
                self.flapping = FlappingInfo(**self.flapping)
            except TypeError: # unknown value
                self.flapping = None

        self.flapping_timer = None

        self.stopped = False

    @property
    def active(self):
        return len(self.running) > 0

    @property
    def graceful_timeout(self):
        return nanotime(self.settings.get('graceful_timeout', 10.0))

    @property
    def group(self):
        return self.settings.get('group')

    def __str__(self):
        return "state: %s" % self.name

    def make_process(self, loop, id, on_exit):
        """ create an OS process using this template """
        params = {}
        for name, default in self.DEFAULT_PARAMS.items():
            params[name] = self.settings.get(name, default)

        os_env = self.settings.get('os_env', False)
        if os_env:
            env = params.get('env', {})
            env.update(os.environ())
            params['env'] = env

        params['on_exit_cb'] = on_exit

        return Process(loop, id, self.name, self.cmd, **params)

    @property
    def group(self):
        return self.settings.get('group')

    def __get_numprocesses(self):
        return atomic_read(self._numprocesses)
    def __set_numprocesses(self, n):
        self._numprocesses = compare_and_swap(self._numprocesses, n)
    numprocesses = property(__get_numprocesses, __set_numprocesses,
            doc="""return the max numbers of processes that we keep
            alive for this command""")

    @property
    def pids(self):
        return [p.id for p in self.running]

    def reset(self):
        """ reset this template to default values """
        self.numprocesses = self.settings.get('numprocesses', 1)
        # reset flapping
        if self.flapping and self.flapping is not None:
            self.flapping.reset()

    def ttin(self, i=1):
        """ increase the maximum number of running processes """

        self._numprocesses = add(self._numprocesses, i)
        return self._numprocesses

    def ttou(self, i=1):
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

    def stats(self):
        """ return stats from alll running process using this template
        """
        infos = []
        lmem = []
        lcpu = []
        for p in self.running:
            info = p.info
            info['id'] = p.id
            infos.append(info)
            lmem.append(info['mem'])
            lcpu.append(info['cpu'])

        if 'N/A' in lmem:
            mem, max_mem, min_mem = "N/A"
        else:
            max_mem = max(lmem)
            min_mem = min(lmem)
            mem = sum(lmem)

        if 'N/A' in lcpu:
            cpu, max_cpu, min_cpu = "N/A"
        else:
            max_cpu = max(lcpu)
            min_cpu = min(lcpu)
            cpu = sum(lcpu)

        ret = dict(name=self.name, stats=infos, mem=mem, max_mem=max_mem,
                min_mem=min_mem, cpu=cpu, max_cpu=max_cpu,
                min_cpu=min_cpu)
        return ret

    def monitor(self, listener):
        """ start monitoring in all processes of the process template """
        for p in self.running:
            p.monitor(listener)

    def unmonitor(self, listener):
        """ unmonitor all processes maintained by this process template
        """
        for p in self.running:
            p.unmonitor(listener)

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
