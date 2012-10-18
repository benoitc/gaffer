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
import copy
import operator
from threading import RLock

import pyuv
import six

try:
    from collections import OrderedDict
except ImportError:
    from .datastructures import OrderedDict

from .events import EventEmitter
from .process import Process
from .state import ProcessState, ProcessTracker
from .sync import increment

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

        # initialize the process tracker
        self._tracker = ProcessTracker(self.loop)

        # initialize some values
        self.apps = None
        self.started = False
        self._stop_ev = None
        self.max_process_id = 0
        self.processes = OrderedDict()
        self.running = OrderedDict()
        self.groups = {}
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

        # start the process tracker
        self._tracker.start()

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

    def start_processes(self):
        """ start all processes """
        self._lock.acquire()
        for name in self.processes:
            self._lock.release()
            self.start_process(name)
            self._lock.acquire()
        self._lock.release()

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

    def get_groups(self):
        """ return the groups list """
        with self._lock:
            return list(self.groups)

    def get_group(self, groupname):
        """ return list of named process of this group """
        with self._lock:
            if groupname not in self.groups:
                raise KeyError('%r not found')
            return copy.copy(self.groups[groupname])

    def remove_group(self, groupname):
        """ remove a group and all its processes. All processes are
        stopped """
        self._apply_group_func(groupname, self.remove_process)

        # finally remove the group
        with self._lock:
            del self.groups[groupname]

    def start_group(self, groupname):
        """ start all process templates of the group """
        self._apply_group_func(groupname, self.start_process)

    def stop_group(self, groupname):
        """ stop all processes templates of the group """
        self._apply_group_func(groupname, self.stop_process)

    def restart_group(self, groupname):
        """ restart all processes in a group  """
        self._apply_group_func(groupname, self.restart_process)




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

            # Grouped process are prefixed by the name of the group
            # <grouname>:<name>
            if ":" in name:
                group = name.split(":", 1)[0]
                kwargs['group'] = group
            else:
                group = None

            state = ProcessState(name, cmd, **kwargs)
            self.processes[name] = state

            # register this name to the group
            if group is not None:
                try:
                    self.groups[group].append(name)
                except KeyError:
                    self.groups[group] = [name]

            self._publish("create", name=name)
            if start:
                self._publish("start", name=name)
                self._publish("proc.%s.start" % name, name=name)
                self._manage_processes(state)


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

            # remove it the from the list
            state = self.processes.pop(name)
            # also remove it from the group if any.
            if state.group is not None:
                if state.group in self.groups:
                    g = self.groups[state.group]
                    del g[operator.indexOf(g, name)]
                    self.groups[state.group] = g

            # notify other that this template has been deleted
            self._publish("delete", name=name)

    def manage_process(self, name):
        with self._lock:
            if name not in self.processes:
                raise KeyError("%r not found" % name)
            state = self.processes[name]
            self._manage_processes(state)


    def get_process(self, name_or_pid):
        with self._lock:
            if isinstance(name_or_pid, int):
                return self.running[name_or_pid]
            else:
                return self.processes[name_or_pid]


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

    def _shutdown(self):
        with self._lock:
            # stop the applications.
            for ctl in self.apps:
                ctl.stop()

            # we are now stopped
            self.started = False

            # close all handles
            #def walk_cb(h):
            #    if h.active:
            #        h.close()
            #self.loop.walk(walk_cb)

            # if there any stop callback, excute it
            if self.stop_cb is not None:
                self.stop_cb(self)
                self.stop_cb = None

    def _stop(self):
        # stop should be synchronous. We need to first stop the
        # processes and let the applications know about it. It is
        # actually done by setting on startup a timer waiting that all
        # processes have stopped to run. Then applications are stopped.

        self.stopping = True

        # stop all processes
        with self._lock:
            for name in self.processes:
                self._stop_processes(name)

            self._tracker.on_done(self._shutdown)

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

    def _stop_processes(self, name):
        """ stop all processes in a template """
        if name not in self.processes:
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
            self._publish("stop_pid", name=p.name, pid=p.id, os_pid=p.pid)
            self._publish("proc.%s.stop_pid" % p.name, name=p.name,
                    pid=p.id, os_pid=p.pid)

            # remove the pid from the running processes
            if p.id in self.running:
                self.running.pop(p.id)

            # stop the process
            p.stop()

            # track this process to make sure it's killed after the
            # graceful time
            self._tracker.check(p, state.graceful_timeout)

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

        # track this process to make sure it's killed after the
        # graceful time
        self._tracker.check(p, state.graceful_timeout)

        # notify  other that the process is beeing stopped
        self._publish("stop_pid", name=p.name, pid=pid, os_pid=p.pid)
        self._publish("proc.%s.stop_pid" % p.name, name=p.name, pid=pid,
                os_pid=p.pid)

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

        self._publish("spawn", name=p.name, pid=pid,
                detached=p.detach, os_pid=p.pid)
        self._publish("proc.%s.spawn" % p.name, name=p.name, pid=pid,
                detached=p.detach, os_pid=p.pid)

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
                try:
                    p = state.dequeue()
                except IndexError:
                    return

                # remove the pid from the running processes
                if p.id in self.running:
                    self.running.pop(p.id)

                # stop the process
                p.stop()

                # track this process to make sure it's killed after the
                # graceful time
                self._tracker.check(p, state.graceful_timeout)

                # notify others that the process is beeing reaped
                self._publish("reap", name=p.name, pid=p.id, os_pid=p.pid)
                self._publish("proc.%s.reap" % p.name, name=p.name,
                    pid=p.id, os_pid=p.pid)

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
            self._stop_processes(state.name)
            if can_retry:
                # if we can retry later then set a callback
                def flapping_cb(handle):
                    # allows respawning
                    state.stopped = False
                    state._flapping_timer = None

                    # restart processes
                    self._restart_processes(state)
                # set a callback
                t = pyuv.Timer(self.loop)
                t.start(flapping_cb, state.flapping.retry_in, 0.0)
                state._flapping_timer = t
            return False
        return True

    def _publish(self, evtype, **ev):
        event = {"event": evtype }
        event.update(ev)
        self._emitter.publish(evtype, event)


    def _apply_group_func(self, groupname, func):
        self._lock.acquire()
        if groupname not in self.groups:
            raise KeyError('%r not found')

        for name in self.groups[groupname]:
            if name in self.processes:
                self._lock.release()
                func(name)
                self._lock.acquire()

        self._lock.release()


    # ------------- events handler

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
        # notify other that the process exited
        ev_details = dict(name=process.name, pid=process.id,
                exit_status=exit_status, term_signal=term_signal,
                os_pid=process.pid)

        self._publish("exit", **ev_details)
        self._publish("proc.%s.exit" % process.name, **ev_details)

        with self._lock:
            # maybe uncjeck this process from the tracker
            self._tracker.uncheck(process)

            state = self.get_process_state(process.name)

            # unexpected exit, remove the process from the list of
            # running processes.

            if process.id in self.running:
                self.running.pop(process.id)

            # this template has been removed, return
            if not state:
                return

            state.remove(process)

            # eventually restart the process
            if not state.stopped:
                # manage the template, eventually restart a new one.
                if self._check_flapping(state):
                    self._manage_processes(state)
