# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
The manager module is a core component of gaffer. A Manager is
responsible of maintaining processes and allows you to interract with
them.

Classes
=======

"""
from collections import deque
import heapq
from threading import RLock
import operator
import os
import signal
import time

import psutil
import pyuv
import six

from .events import EventEmitter
from .process import Process
from .sync import increment, add, sub, atomic_read, compare_and_swap
from .util import nanotime

class Manager(object):
    """ Manager - maintain process alive

    A manager is responsible of maintaining process alive and manage
    actions on them:

    - increase/decrease the number of processes / process template
    - start/stop processes
    - add/remove process templates to manage

    The design is pretty simple. The manager is running on the default
    event loop and listening on events. Events are sent when a process
    exit or from any method call. The control of a manager can be
    extended by adding apps on startup. For example gaffer
    provides an application allowing you to control processes via HTTP.

    Running an application is done like this::

        # initialize the application with the default loop
        loop = pyuv.Loop.default_loop()
        m = Manager(loop=loop)

        # start the application
        m.start(apps=[HttpHandler])

        .... # do smth

        m.stop() # stop the controlller
        m.run() # run the event loop

    .. note::

        The loop can be omitted if the first thing you do is
        launching a manager. The run function is here for convenience. You
        can of course just run `loop.run()` instead

    .. warning::

        The manager should be stopped the last one to prevent any lock
        in your application.


    """

    def __init__(self, loop=None):

        # by default we run on the default loop
        self.loop = loop or pyuv.Loop.default_loop()

        # wakeup ev for internal signaling
        self._wakeup_ev = pyuv.Async(self.loop, self._on_wakeup)

        # initialize the emitter
        self._emitter = EventEmitter(self.loop)

        # initialize the process garbage collector
        self._stopped = []
        self._gc_collector = pyuv.Timer(self.loop)

        # initialize some values
        self.apps = None
        self.started = False
        self._stop_ev = None
        self.max_process_id = 0
        self.processes = {}
        self.running = {}
        self.channel = deque()
        self._updates = deque()
        self._signals = []

        self.stopping= False
        self.stop_cb = None
        self.restart_cb = None
        self._lock = RLock()

    def start(self, apps=[]):
        """ start the manager. """
        self.apps = apps

        # start the garbage collector
        self._gc_collector.start(self._gc_handler, 1.0, 1.0)
        self._gc_collector.unref()

        # start contollers
        for ctl in self.apps:
            ctl.start(self.loop, self)

        self.started = True

    def run(self):
        """ Convenience function to use in place of `loop.run()`
        If the manager is not started it raises a `RuntimeError`.

        Note: if you want to use separately the default loop for this
        thread then just use the start function and run the loop somewhere
        else.
        """
        if not self.started:
            raise RuntimeError("manager hasn't been started")
        self.loop.run()

    def stop(self, callback=None):
        """ stop the manager. This function is threadsafe """
        self.stop_cb = callback
        self._signals.append("STOP")
        self.wakeup()


    def restart(self, callback=None):
        """ restart all processes in the manager. This function is
        threadsafe """
        self.restart_cb = callback
        self._signals.append("RESTART")
        self.wakeup()

    def stop_processes(self):
        """ stop all processes in the manager """
        with self._lock:
            for name in self.processes:
                self._stop_byname_unlocked(name)

    def running_processes(self):
        """ return running processes """
        with self._lock:
            return self.running

    def processes_stats(self):
        """ iterator returning all processes stats """
        with self._lock:
            for name in self.processes:
                yield self.get_process_stats(name)

    def subscribe(self, evtype, listener):
        """ subscribe to the manager event *eventype*

        'on' is an alias to this function
        """
        self._emitter.subscribe(evtype, listener)
    on = subscribe

    def subscribe_once(self, evtype, listener):
        """ subscribe once to the manager event *eventype*

        'once' is an alias to this function
        """
        self._emitter.subscribe_once(evtype, listener)
    once = subscribe


    def unsubscribe(self, evtype, listener):
        """ unsubscribe from the event *eventype* """
        self._emitter.unsubscribe(evtype, listener)

    # ------------- process functions

    def add_process(self, name, cmd, **kwargs):
        """ add a process to the manager. all process should be added
        using this function

        - **name**: name of the process
        - **cmd**: program command, string)
        - **args**: the arguments for the command to run. Can be a list or
          a string. If **args** is  a string, it's splitted using
          :func:`shlex.split`. Defaults to None.
        - **env**: a mapping containing the environment variables the command
          will run with. Optional
        - **uid**: int or str, user id
        - **gid**: int or st, user group id,
        - **cwd**: working dir
        - **detach**: the process is launched but won't be monitored and
          won't exit when the manager is stopped.
        - **shell**: boolean, run the script in a shell. (UNIX
          only),
        - **os_env**: boolean, pass the os environment to the program
        - **numprocesses**: int the number of OS processes to launch for
          this description
        - **flapping**: a FlappingInfo instance or, if flapping detection
          should be used. flapping parameters are:

          - **attempts**: maximum number of attempts before we stop the
            process and set it to retry later
          - **window**: period in which we are testing the number of
            retry
          - **retry_in**: seconds, the time after we restart the process
            and try to spawn them
          - **max_retry**: maximum number of retry before we give up
            and stop the process.
        - **redirect_output**: list of io to redict (max 2) this is a list of custom
          labels to use for the redirection. Ex: ["a", "b"] will
          redirect stdoutt & stderr and stdout events will be labeled "a"
        - **redirect_input**: Boolean (False is the default). Set it if
          you want to be able to write to stdin.
        - **graceful_timeout**: graceful time before we send a  SIGKILL
          to the process (which definitely kill it). By default 30s.
          This is a time we let to a process to exit cleanly.
        """

        with self._lock:
            if name in self.processes:
                raise KeyError("a process named %r is already managed" % name)

            if 'start' in kwargs:
                start = kwargs.pop('start')
            else:
                start = True

            state = ProcessState(name, cmd, **kwargs)
            self.processes[name] = state

            self._publish("create", name=name)
            if start:
                self.start_process(name)

    def update_process(self, name, cmd, **kwargs):
        """ update a process information.

        When a process is updated, all current processes are stopped
        then the state is updated and new processes with new info are
        started """
        with self._lock:
            if name not in KeyError:
                raise KeyError("%r not found" % name)

            self._stop_byname_unlocked(name)
            state = ProcessState(name, cmd, **kwargs)
            state.setup(name, cmd, **kwargs)

            if 'start' in kwargs:
                del kwargs['start']

            self._publish("update", name=name)
            self._manage_processes(state)


    def start_process(self, name):
        with self._lock:
            if name in self.processes:
                state = self.processes[name]
                self._publish("start", name=name)
                self._publish("proc.%s.start" % name, name=name)
                self._manage_processes(state)
            else:
                raise KeyError("%s not found")

    def stop_process(self, name_or_id):
        """ stop a process by name or id

        If a name is given all processes associated to this name will be
        removed and the process is marked at stopped. If the internal
        process id is givien, only the process with this id will be
        stopped """

        with self._lock:
            # stop all processes of the template name
            if isinstance(name_or_id, six.string_types):
                print("here")
                self._stop_processes(name_or_id)
            else:
                # stop a process by its internal pid
                self._stop_process(name_or_id)


    def restart_process(self, name):
        """ restart a process """
        with self._lock:
            if name not in self.processes:
                raise KeyError("%r not found" % name)

            state = self.get_process_state(name)
            self._restart_processes(state)

    def remove_process(self, name):
        """ remove the process and its config from the manager """

        with self._lock:
            if name not in self.processes:
                raise KeyError("%r not found" % name)

            # stop all processes
            self._stop_processes(name)
            # remove it the list
            del self.processes[name]
            # notify other that this template has been deleted
            self._publish("delete", name=name)

    def manage_process(self, name):
        with self._lock:
            if name not in self.processes:
                raise KeyError("%r not found" % name)
            state = self.processes[name]
            self._manage_processes(state)


    def get_process_info(self, name):
        """ get process info """
        with self._lock:
            if name not in self.processes:
                raise KeyError("%r not found" % name)

            state = self.processes[name]
            info = {"name": state.name, "cmd": state.cmd}
            info.update(state.settings)
            return info

    def get_process_status(self, name):
        """ return the process status::

            {
              "active":  str,
              "running": int,
              "max_processes": int
            }

        - **active** can be *active* or *stopped*
        - **running**: the number of actually running OS processes using
          this template.
        - **max_processes**: The maximum number of processes that should
          run. It is is normally the same than the **runnin** value.

        """
        with self._lock:
            if name not in self.processes:
                raise KeyError("%r not found" % name)

            state = self.processes[name]
            status = { "active":  state.active,
                       "running": len(state.running),
                       "max_processes": state.numprocesses }
            return status

    def get_process_stats(self, name_or_id):
        """ return process stats for a process template or a process id
        """
        with self._lock:
            if isinstance(name_or_id, int):
                try:
                    return self.running[name_or_id].info
                except KeyError:
                    raise KeyError("%s not found" % name_or_id)
            else:
                if name_or_id not in self.processes:
                    raise KeyError("%r not found" % name_or_id)

                state = self.processes[name_or_id]
                return state.stats()

    def monitor(self, name_or_id, listener):
        """ get stats changes on a process template or id
        """
        with self._lock:
            try:
                if isinstance(name_or_id, int):
                    return self.running[name_or_id].monitor(listener)
                else:
                    state = self.processes[name_or_id]
                    return state.monitor(listener)
            except KeyError:
                raise KeyError("%s not found" % name_or_id)

    def unmonitor(self, name_or_id, listener):
        """ get stats changes on a process template or id
        """
        with self._lock:
            try:
                if isinstance(name_or_id, int):
                    return self.running[name_or_id].unmonitor(listener)
                else:
                    state = self.get_process_state(name_or_id)
                    return state.unmonitor(listener)
            except KeyError:
                raise KeyError("%s not found" % name_or_id)

    def ttin(self, name, i=1):
        """ increase the number of system processes for a state. Change
        is handled once the event loop is idling """

        with self._lock:
            state = self.get_process_state(name)
            ret = state.ttin(i)
            self._publish("update", name=name)
            self._manage_processes(state)
            return ret

    def ttou(self, name, i=1):
        """ decrease the number of system processes for a state. Change
        is handled once the event loop is idling """

        with self._lock:
            state = self.get_process_state(name)
            ret = state.ttou(i)
            self._publish("update", name=name)
            self._manage_processes(state)
            return ret

    def send_signal(self, name_or_id, signum):
        """ send a signal to a process or all processes contained in a
        state """
        with self._lock:
            try:
                if isinstance(name_or_id, int):
                    p = self.running[name_or_id]
                    p.kill(signum)
                else:
                    state = self.processes[name_or_id]
                    for p in state.running:
                        p.kill(signum)

            except KeyError:
                pass

    # ------------- general purpose utilities

    def wakeup(self):
        self._wakeup_ev.send()

    def get_process_state(self, name):
        if name not in self.processes:
            return
        return self.processes[name]

    def get_process_id(self):
        """ generate a process id """
        self.max_process_id = increment(self.max_process_id)
        return self.max_process_id


    # ------------- private functions

    def _maybe_shutdown(self, handle):
        with self._lock:
            # still running processes, return.
            if self._stopped or self.running:
                return

            # we can finally shutdown, stop the timer
            handle.close()

            # then stop the applications.
            for ctl in self.apps:
                ctl.stop()

            # we are now stopped
            self.started = False
            # if there any stop callback, excute it
            if self.stop_cb is not None:
                self.stop_cb(self)
                self.stop_cb = None

        # close all handles
        def walk_cb(h):
            if h.active:
                h.close()
        self.loop.walk(walk_cb)


    def _stop(self):
        # stop should be synchronous. We need to first stop the
        # processes and let the applications know about it. It is
        # actually done by setting on startup a timer waiting that all
        # processes have stopped to run. Then applications are stopped.

        self.stopping = True

        # start the waiting timer
        self._shutdown_t = pyuv.Timer(self.loop)
        self._shutdown_t.start(self._maybe_shutdown, 0.1, 0.1)

        # stop all processes
        with self._lock:
            for name in self.processes:
                self._stop_processes(name)


    def _restart(self):
        with self._lock:
            # on restart we first restart the applications
            for app in self.apps:
                app.restart()

            # then we restart the processes
            for name, state in self.processes.items():
                self._restart_processes(state)

            # if any callback has been set, run it
            if self.restart_cb is not None:
                self.restart_cb(self)
                self.restart_cb = None

    def _collect_for_gc(self, state, p):
        p.graceful_time = state.graceful_timeout + nanotime()
        heapq.heappush(self._stopped, p)

    def _stop_processes(self, name):
        """ stop all processes in a template """
        if name not in self.processes:
            print("return")
            return


        # get the template
        state = self.processes[name]
        if state.stopped:
            return
        state.stopped = True

        # notify others that all processes of the templates are beeing
        # stopped.
        self._publish("stop", name=name)
        self._publish("proc.%s.stop" % name, name=name)

        # stop the flapping detection.
        if state.flapping_timer is not None:
            state.flapping_timer.stop()

        # iterrate over queued processes.
        while True:
            try:
                p = state.dequeue()
            except IndexError:
                break

            # notify  other that the process is beeing stopped
            self._publish("proc.%s.stop_pid" % p.name, name=p.name,
                    pid=p.id)

            # remove the pid from the running processes
            if p.id in self.running:
                self.running.pop(p.id)

            # stop the process
            p.stop()
            # collect it for the garbage collection. We make sure a worker
            # is killed after a gracefull tome
            self._collect_for_gc(state, p)

    def _stop_process(self, pid):
        """ stop a process bby id """

        if pid not in self.running:
            return

        # remove the process from the running processes
        p = self.running.pop(pid)
        state = self.processes[p.name]
        state.remove(p)

        # stop the process
        p.stop()
        # collect it for the garbage collection. We make sure a worker
        # is killed after a gracefull tome
        self._collect_for_gc(state, p)

        # notify  other that the process is beeing stopped
        self._publish("proc.%s.stop_pid" % p.name, name=p.name, pid=pid)

    def _spawn_process(self, state):
        """ spawn a new process and add it to the state """
        # get internal process id
        pid = self.get_process_id()

        # start process
        p = state.make_process(self.loop, pid, self._on_exit)
        p.spawn()

        # add the process to the running state
        state.queue(p)

        # we keep a list of all running process by id here
        self.running[pid] = p

        self._publish("proc.%s.spawn" % p.name, name=p.name, pid=pid,
                detached=p.detach)

    def _spawn_processes(self, state):
        """ spawn all processes for a state """
        num_to_start = state.numprocesses - len(state.running)
        for i in range(num_to_start):
            self._spawn_process(state)

    def _reap_processes(self, state):
        diff = len(state.running) - state.numprocesses
        if diff > 0:
            for i in range(diff):
                # remove the process from the running processes
                p = state.dequeue()
                if p.id in self.running:
                    self.running.pop(p.id)

                # stop the process
                p.stop()

                # notify others that the process is beeing reaped
                self._publish("proc.%s.reap" % p.name, name=p.name,
                    pid=p.id)

    def _manage_processes(self, state):
        if len(state.running) < state.numprocesses:
            self._spawn_processes(state)
        self._reap_processes(state)

    def _restart_processes(self, state):
        # first launch new processes
        for i in range(state.numprocesses):
            self._spawn_process(state)

        # then reap useless one.
        self._manage_processes(state)

    def _check_flapping(self, state):
        if not state.flapping:
            return True

        check_flapping, can_retry = state.check_flapping()
        if not check_flapping:
            self._publish("flap", name=state.name)
            # stop the processes
            self._stop_byname_unlocked(state.name)
            if can_retry:
                # if we can retry later then set a callback
                def flapping_cb(handle):
                    handle.stop()

                    # allows respawning
                    state.stopped = False
                    state._flapping_timer = None

                    # restart processes
                    self._restart_processes(state)

                # set a callback
                t = pyuv.Timer(self.loop)
                t.start(flapping_cb, state.flapping.retry_in,
                        state.flapping.retry_in)
                state._flapping_timer = t
            return False
        return True

    def _publish(self, evtype, **ev):
        event = {"event": evtype }
        event.update(ev)
        self._emitter.publish(evtype, event)


    # ------------- events handler

    def _gc_handler(self, handle):
        # this function check if a process that need to be stopped after
        # a given graceful time is still in the stopped process. If yes
        # the process is killed. It let the possibility to let the time
        # to some worker to quit.
        #
        # The garbage collector run eveyry 0.1s .
        with self._lock:
            while True:
                if not len(self._stopped):
                    # nothing in the queue, quit
                    break

                # check the diff between the time it is now and the
                # graceful time set when the worker was stopped
                p = heapq.heappop(self._stopped)
                now = nanotime()
                delta = p.graceful_time - now

                if delta > 0:
                    # we have anything to do, put the process back in
                    # the heap and return
                    heapq.heappush(self._stopped, p)
                    break
                else:
                    # a process need to be kill. Send a SIGKILL signal
                    try:
                        p.kill(signal.SIGKILL)
                    except:
                        pass
                    # and close it. (maybe we should just close it)
                    p.close()

    def _on_wakeup(self, handle):
        sig = self._signals.pop(0) if len(self._signals) else None
        if not sig:
            return

        if sig == "STOP":
            handle.close()
            self._stop()
        elif sig == "RESTART":
            self._restart()

    def _on_exit(self, process, exit_status, term_signal):
        # exit callback called when a process exit

        # notify other that the process exited
        self._publish("proc.%s.exit" % process.name, name=process.name,
                pid=process.id, exit_status=exit_status,
                term_signal=term_signal)

        with self._lock:
            state = self.get_process_state(process.name)

            if process in self._stopped:
                # this exit was expected. remove it from the garbage
                # collection.
                del self._stopped[operator.indexOf(self._stopped,
                    process)]
            else:
                # unexpected exit, remove the process from the list of
                # running processes.

                if process.id in self.running:
                    self.running.pop(process.id)

                if state is not None:
                    state.remove(process)

            # this remplate has been removed
            if not state:
                return

            if not state.stopped:
                # manage the template, eventually restart a new one.
                if self._check_flapping(state):
                    self._manage_processes(state)

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
        if len(f.history) < f.attempts:
            f.history.append(time.time())
        else:
            diff = f.history[-1] - f.history[0]
            if diff > f.window:
                f.reset()
                f.history.append(time.time())
            elif f.retries < f.max_retry:
                increment(f.retries)
                return False, True
            else:
                f.reset()
                return False, False
        return True, None
