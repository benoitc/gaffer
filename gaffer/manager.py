# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import deque
from threading import RLock
try:
    from queue import Queue
except ImportError:
    from Queue import Queue

import pyuv
import six

from .process import Process
from .sync import increment, add, sub, atomic_read, compare_and_swap

class bomb(object):
    def __init__(self, exp_type=None, exp_value=None, exp_traceback=None):
        self.type = exp_type
        self.value = exp_value
        self.traceback = exp_traceback

    def raise_(self):
        six.reraise(self.type, self.value, self.traceback)


class ProcessState(object):
    """ object used by the manager to maintain the process state """

    DEFAULT_PARAMS = {
            "group": None,
            "args": None,
            "uid": None,
            "gid": None,
            "cwd": None,
            "detach": False,
            "shell": False}

    def __init__(self, name, cmd, **settings):
        self.running = deque()
        self.stopped = False
        self.setup(name, cmd, **settings)

    def setup(self, name, cmd, **settings):
        self.name = name
        self.cmd = cmd
        self.settings = settings
        self._numprocesses = self.settings.get('numprocesses', 1)
        self.stopped = False

    @property
    def active(self):
        return len(self.running) > 0

    def __str__(self):
        return "state: %s" % self.name

    def make_process(self, loop, id, on_exit):
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
    def hup(self):
        return self.settings.get('hup', False)

    def reset(self):
        self.numprocesses = self.settings.get('numprocesses', 1)

    def ttin(self, i=1):
        self._numprocesses = add(self._numprocesses, i)
        return self._numprocesses

    def ttou(self, i=1):
        self._numprocesses = sub(self._numprocesses, i)
        return self._numprocesses

    def queue(self, process):
        self.running.append(process)

    def dequeue(self):
        return self.running.popleft()

    def remove(self, process):
        try:
            self.running.remove(process)
        except ValueError:
            pass

    def list_processes(self):
        return list(self.running)

class Manager(object):

    def __init__(self, loop=None,):

        # by default we run on the default loop
        self.loop = loop or pyuv.Loop.default_loop()

        # setup wakeup event
        self._wakeup_ev = pyuv.Async(self.loop, self._on_wakeup)

        # initialize some values
        self.controllers = None
        self.started = False
        self._stop_ev = None
        self.max_process_id = 0
        self.processes = {}
        self.running = {}
        self.channel = deque()
        self._updates = deque()
        self._signals = deque()

        self.stop_cb = None
        self.restart_cb = None
        self._lock = RLock()

    def start(self, controllers=[]):
        """ start the manager. """
        self.controllers = controllers

        # start contollers
        for ctl in self.controllers:
            ctl.start(self.loop, self)

        self.started = True

    def run(self):
        """ Convenience function to use in place of `loop.run()'
        If the manager is not started it raises a `RuntimeError'.

        Note: if you want to use separately the default loop for this
        thread then just use the start function and run the loop somewhere
        else. """
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
        with self._lock:
            return self.running

    # ------------- process functions

    def add_process(self, name, cmd, **kwargs):
        """ add a process to the manager. all process should be added
        using this function """
        with self._lock:
            if name in self.processes:
                raise KeyError("a process named %r is already managed" % name)

            if 'start' in kwargs:
                start = kwargs.pop('start')
            else:
                start = True

            state = ProcessState(name, cmd, **kwargs)
            self.processes[name] = state
            if start:
                self._spawn_processes(state)

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

            self._spawn_processes(state)

    def stop_process(self, name_or_id):
        """ stop a process by name or id

        If a name is given all processes associated to this name will be
        removed and the process is marked at stopped. If the internal
        process id is givien, only the process with this id will be
        stopped """

        if isinstance(name_or_id, six.string_types):
            stop_func = self._stop_byname_unlocked
        else:
            stop_func = self._stop_byid_unlocked

        # really stop the process
        with self._lock:
            stop_func(name_or_id)

    def remove_process(self, name):
        """ remove the process and its config from the manager """

        with self._lock:
            if name not in self.processes:
                raise KeyError("%r not found" % name)

            self._stop_byname_unlocked(name)
            del self.processes[name]

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
        with self._lock:
            if name not in self.processes:
                raise KeyError("%r not found" % name)

            state = self.processes[name]
            status = { "active":  state.active,
                       "running": len(state.running),
                       "max_processes": state.numprocesses }
            return status


    def manage_process(self, name):
        with self._lock:
            state = self.get_process_state(name)
            state.stopped = False
            self._manage_processes(state)

    start_process = manage_process

    def reap_process(self, name):
        with self._lock:
            self._reap_processes(self.get_process_state(name))

    def restart_process(self, name):
        """ restart a process """
        with self._lock:
            state = self.get_process_state(name)
        self._restart_processes(state)

    def ttin(self, name, i=1):
        """ increase the number of system processes for a state. Change
        is handled once the event loop is idling """

        with self._lock:
            state = self.get_process_state(name)
            ret = state.ttin(i)
            self._manage_processes(state)
            return ret

    def ttou(self, name, i=1):
        """ decrease the number of system processes for a state. Change
        is handled once the event loop is idling """

        with self._lock:
            state = self.get_process_state(name)
            ret = state.ttou(i)
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

    def update_state(self, name):
        """ update the state. When the event loop is idle, the state is
        read and processes in the state managed """

        self._updates.append(name)
        self.wakeup()

    def get_process_state(self, name):
        if name not in self.processes:
            return
        return self.processes[name]

    def get_process_id(self):
        """ generate a process id """
        self.max_process_id = increment(self.max_process_id)
        return self.max_process_id


    # ------------- private functions

    def _stop(self):
        # stop all processes
        self.stop_processes()

        with self._lock:
            # stop controllers
            for ctl in self.controllers:
                ctl.stop()

            # we are now stopped
            self.started = False

            if self.stop_cb:
                self.stop_cb(self)
                self.stop_cb = None

    def _restart(self):
        with self._lock:
            to_restart = [state for name, state in self.processes.items()]

        for state in to_restart:
            if state is not None:
                self._restart_processes(state)

        with self._lock:
            for ctl in self.controllers:
                ctl.restart()

            if self.restart_cb:
                self.restart_cb(self)
                self.restart_cb = None

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

    def _stop_byname_unlocked(self, name):
        """ stop a process by name """
        if name not in self.processes:
            return

        state = self.processes[name]
        state.stopped = True

        while True:
            try:
                p = state.dequeue()
            except IndexError:
                break

            # race condition, we need to remove the process from the
            # running pid now.
            if p.id in self.running:
                self.running.pop(p.id)

            p.stop()

    def _stop_byid_unlocked(self, pid):
        """ stop a process bby id """
        if pid not in self.running:
            return

        p = self.running.drop(pid)

        # remove the process from the running processes
        state = self.processes[p.name]
        state.remove(p)

        # finally stop the process
        p.stop()

    def _spawn_processes(self, state):
        """ spawn all processes for a state """
        num_to_start = state.numprocesses - len(state.running)
        for i in range(num_to_start):
            self._spawn_process(state)

    def _reap_processes(self, state):
        diff = len(state.running) - state.numprocesses

        if diff > 0:
            for i in range(diff):
                p = state.dequeue()
                p.stop()

    def _manage_processes(self, state):
        if len(state.running) < state.numprocesses:
            self._spawn_processes(state)
        self._reap_processes(state)


    def _restart_processes(self, state):
        # disable automatic process management while we are stopping
        # the processes
        state.numprocesses = 0

        # stop the processes, we need to lock here
        with self._lock:
            while True:
                try:
                    p = state.dequeue()
                except IndexError:
                    break

                # race condition, we need to remove the process from the
                # running pid now.
                if p.id in self.running:
                    self.running.pop(p.id)

                p.stop()

        # reset the number of processes
        state.reset()

        # start the processes the next time
        self.manage_process(state.name)


    # ------------- events handler

    def _on_wakeup(self, handle):
        sig = None
        try:
            sig = self._signals.popleft()
        except IndexError:
            pass
        if sig is not None:
            sig = sig.upper()
            if sig == "STOP":
                handle.close()
                return self._stop()
            elif sig == "RESTART":
                return self._restart()

        if not len(self._updates):
            pass

        to_update = self._updates.popleft()
        self.manage_process(to_update)

    def _on_exit(self, process, exit_status, term_signal):
        """ exit callback returned when a process exit """
        with self._lock:
            # remove the process from the running processes
            if process.id in self.running:
                self.running.pop(process.id)

            # remove the running process from the process state
            state = self.get_process_state(process.name)
            if not state:
                return
            state.remove(process)

            # if not stopped we may need to restart a new process
            if not state.stopped:
                self._manage_processes(state)
