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
from functools import partial
import operator
from threading import RLock

import pyuv
import six

try:
    from collections import OrderedDict
except ImportError:
    from .datastructures import OrderedDict


from .loop import patch_loop, get_loop
from .events import EventEmitter
from .error import ProcessError
from .queue import AsyncQueue
from .process import Process
from .pubsub import Topic
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

        if loop is not None:
            self.loop = patch_loop(loop)
        else:
            self.loop = get_loop(True)

        # initialize the emitter
        self.events = EventEmitter(self.loop)

        # initialize the process tracker
        self._tracker = ProcessTracker(self.loop)

        # initialize some values
        self.mapps = []
        self.started = False
        self._stop_ev = None
        self.max_process_id = 0
        self.processes = OrderedDict()
        self.running = OrderedDict()
        self.apps = OrderedDict()
        self._topics = {}
        self._updates = deque()
        self._signals = []

        self.stopping= False
        self.stop_cb = None
        self.restart_cb = None
        self._lock = RLock()

    def start(self, apps=[]):
        """ start the manager. """
        self.mapps = apps

        self._mq = AsyncQueue(self.loop, self._handle_messages)

        # start the process tracker
        self._tracker.start()

        # manage processes
        self.events.subscribe('exit', self._on_exit)

        # start contollers
        for mapp in self.mapps:
            mapp.start(self.loop, self)

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
        self._mq.send(self._stop)

    def restart(self, callback=None):
        """ restart all processes in the manager. This function is
        threadsafe """
        self._mq.send(partial(self._restart, callback))

    def subscribe(self, topic):
        if topic not in self._topics:
            self._topics[topic] = Topic(topic, self)
            self._topics[topic].start()

        return self._topics[topic].subscribe()

    def unsubscribe(self, channel):
        if topic not in self._topics:
            return
        self._topics[topic].unsubscribe(channel)

    def all_apps(self):
        return list(self.apps)

    def walk(self, callback):
        with self._lock:
            for appname, templates in self.apps.items():
                for name in templates:
                    callback(self, templates[name])

    def walk_templates(self, callback, appname = None):
        appname = appname or "system"
        with self._lock:
            try:
                templates = self.apps[appname]
            except KeyError:
                raise ProcessError(404, "not_found")

            for name in templates:
                callback(self, templates[name])

    def walk_processes(self, callback, name, appname=None):
        appname = appname or "system"
        with self._lock:
            self._is_found(name, appname)
            state = self.apps[appname][name]
            for p in state.running:
                callback(self, p)


    # ------------- process functions

    def get_templates(self, appname=None):
        appname = appname or "system"
        with self._lock:
            try:
                return self.apps[appname]
            except KeyError:
                raise ProcessError(404, "not_found")

    def get_template(self, name, appname=None):
        appname = appname or "system"
        with self._lock:
            self._is_found(name, appname)
            return self.apps[appname][name]


    def add_template(self, name, cmd, **kwargs):
        """ add a process template to the manager. all templates should be
        added using this function

        - **name**: name of the process
        - **cmd**: program command, string)
        - **appname**: name of the application that own this template
        - **args**: the arguments for the command to run. Can be a list or
          a string. If **args** is  a string, it's splitted using
          :func:`shlex.split`. Defaults to None.
        - **env**: a mapping containing the environment variables the command
          will run with. Optional
        - **uid**: int or str, user id
        - **gid**: int or st, user group id,
        - **cwd**: working dir
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
          redirect stdout & stderr and stdout events will be labeled "a"
        - **redirect_input**: Boolean (False is the default). Set it if
          you want to be able to write to stdin.
        - **graceful_timeout**: graceful time before we send a  SIGKILL
          to the process (which definitely kill it). By default 30s.
          This is a time we let to a process to exit cleanly.
        """

        appname = kwargs.get('appname')
        if not appname:
            # if no appname is specified then the process is handled as a
            # system app.
            appname = kwargs['appname'] = "system"

        # remove the start options from the kwargs, it's only used to
        # start the process when creating it.
        if 'start' in kwargs:
            start = kwargs.pop('start')
        else:
            start = True

        with self._lock:
            if appname in self.apps:
                # check if a process with this name is already referenced for
                # this app. If yes, raises a conflict error
                if name in self.apps[appname]:
                    raise ProcessError(409, "process_conflict")
            else:
                # initialize the application
                self.apps[appname] = OrderedDict()

            # initialize the process
            state = ProcessState(name, cmd, **kwargs)
            self.apps[appname][name] = state

            self._publish("create", name=name, appname=appname)
            if start:
                self._publish("start", name=name, appname=appname)
                self._publish("proc.%s.%s.start" % (appname, name), name=name,
                        appname=appname)
                self._manage_processes(state)


    def update_template(self, name, cmd, **kwargs):
        """ update a process template.

        When a templates is updated, all current processes are stopped
        then the state is updated and new processes with new info are
        started """

        appname = kwargs.get('appname')
        if not appname:
            # if no appname is specified then the process is handled as a
            # system app.
            appname = kwargs['appname'] = "system"

        # stop all process for this template
        self.stop_process(name, appname=appname)

        # remove the start option if any
        if 'start' in kwargs:
            del kwargs['start']

        # do the update and restart the processes
        with self._lock:
            state = ProcessState(name, cmd, **kwargs)
            self.apps[appname][name] = state
            self._publish("update", appname=appname, name=name)
            self._manage_processes(state)

    def start_template(self, name, appname=None):
        appname = appname or "system"
        with self._lock:
            self._is_found(name, appname)
            state = self.apps[appname][name]
            self._publish("start", name=name, appname=appname)
            self._publish("proc.%s.%s.start" % (appname, name), name=name,
                    appname=appname)
            self._manage_processes(state)

    def stop_template(self, name, appname=None):
        """ stop a process by name or id

        If a name is given all processes associated to this name will be
        removed and the process is marked at stopped. If the internal
        process id is givien, only the process with this id will be
        stopped """

        appname = appname or "system"
        with self._lock:
            self._stop_template(name, appname)

    def restart_template(self, name, appname=None):
        """ restart a process """
        appname = appname or "system"

        with self._lock:
            self._is_found(name, appname)
            state = self.apps[appname][name]
            self._restart_processes(state)

    def remove_template(self, name, appname=None):
        """ remove the process and its config from the manager """

        appname = appname or "system"
        with self._lock:
            # stop all processes
            self._stop_template(name, appname)

            # remove this template from the application
            del self.apps[appname][name]

            # if the list of templates for this application is empty, delete
            # this application
            if len(self.apps[appname]) == 0 and appname != "system":
                del self.apps[appname]

            # notify other that this template has been deleted
            self._publish("delete", appname=appname, name=name)


    def scale(self, name, n, appname=None):
        """ Scale the number of processes in a template. By using this
        function you can increase, decrease or set the number of processes in
        a template. Change is handled once the event loop is idling


        n can be a positive or negative integer. It can also be a string
        containing the opetation to do. For example::

            m.scale("sometemplate", 1) # increase of 1
            m.scale("sometemplate", -1) # decrease of 1
            m.scale("sometemplate", "+1") # increase of 1
            m.scale("sometemplate", "-1") # decrease of 1
            m.scale("sometemplate", "=1") # set the number of processess to 1
        """
        appname = appname or "system"

        # find the operation to do
        if isinstance(n, int):
            if n > 0:
                op = "+"
            else:
                op = "-"
            n = abs(n)
        else:
            if n.isdigit():
                op = "+"
                n = int(n)
            else:
                op = n[0]
                if op not in ("=", "+", "-"):
                    raise ValueError("bad_operation")
                n = int(op[1:])

        with self._lock:
            self._is_found(name, appname)
            state = self.apps[appname][name]

            # scale
            if op == "=":
                curr = state.numproceses
                if curr > n:
                    ret = state.decr(curr - n)
                else:
                    ret = state.incr(n - curr)
            elif op == "+":
                ret = state.incr(n)
            else:
                ret = state.decr(n)

            self._publish("update", name=name)
            self._manage_processes(state)
            return ret

    def manage(self, name, appname=None):
        appname = appname or "system"
        with self._lock:
            self._is_found(name, appname)
            state = self.apps[appname][name]
            self._manage_processes(state)

    def get_process(self, pid):
        """ get a process by ID.

        return a ``gaffer.Process`` instance that you can use.
        """
        with self._lock:
            try:
                return self.running[pid]
            except KeyError:
                raise ProcessError(404, "not_found")

    def stop_process(self, pid):
        """ Stop a process by pid """

        with self._lock:
            if pid not in self.running:
                return

            # remove the process from the running processes
            p = self.running.pop(pid)
            try:
                state = self.apps[p.appname][p.name]
            except KeyError:
                return

            state.remove(p)

            # signal to the process to stop
            p.stop()

            # track this process to make sure it's killed after the
            # graceful time
            self._tracker.check(p, state.graceful_timeout)

            # notify  other that the process is beeing stopped
            self._publish("proc.%s.stop" % p.pid, name=p.name, pid=p.pid, os_pid=p.os_pid)
            self._publish("proc.%s.stop_pid" % p.name, name=p.name, pid=pid,
                    os_pid=p.os_pid)

    def get_template_info(self, name, appname=None):
        state = self.get_template(name, appname=appname)
        processes = list(state.running)

        info = {"active":  state.active,
                "running": len(state.running),
                "max_processes": state.numprocesses,
                "processes": [p.pid for p in processes]}

        # get config
        config = {"name": state.name,
                  "appname": state.appname,
                  "cmd": state.cmd}
        config.update(state.settings)
        # remove custom channels because they can't be serialized
        config.pop('custom_channels', None)

        # add config to the info
        info['config'] = config
        return info

    def get_template_stats(self, name, appname=None):
        """ return template stats

        """
        appname = appname or "system"

        with self._lock:
            self._is_found(name, appname)
            state = self.apps[appname][name]

            stats = []
            lmem = []
            lcpu = []
            for p in state.running:
                pstats = p.stats
                pstats['pid'] = p.pid
                pstats['os_pid'] = p.os_pid
                stats.append(pstats)
                lmem.append(pstats['mem'])
                lcpu.append(pstats['cpu'])

            if 'N/A' in lmem or not lmem:
                mem, max_mem, min_mem = "N/A"
            else:
                max_mem = max(lmem)
                min_mem = min(lmem)
                mem = sum(lmem)

            if 'N/A' in lcpu or not lcpu:
                cpu, max_cpu, min_cpu = "N/A"
            else:
                max_cpu = max(lcpu)
                min_cpu = min(lcpu)
                cpu = sum(lcpu)

            ret = dict(name=name, appname=appname, stats=stats, mem=mem,
                    max_mem=max_mem, min_mem=min_mem, cpu=cpu,
                    max_cpu=max_cpu, min_cpu=min_cpu)

            return ret

    def monitor(self, listener, name, appname=None):
        """ get stats changes on a process template or id
        """

        appname = appname or "system"
        with self._lock:
            self._is_found(name, appname)
            template = self.apps[appname][name]
            for p in template.running:
                p.monitor(listener)

    def unmonitor(self, listener, name, appname=None):
        """ get stats changes on a process template or id
        """
        appname = appname or "system"
        with self._lock:
            self._is_found(name, appname)
            template = self.apps[appname][name]
            for p in template.running:
                p.unmonitor(listener)


    def send_signal(self, name, signum, appname=None):
        """ send a signal to a process or all processes using the template"""

        appname = appname or "system"
        with self._lock:
            self._is_found(name, appname)
            state = self.apps[appname][name]
            for p in state.running:
                p.kill(signum)

    # ------------- general purpose utilities

    def wakeup(self):
        self._mq.send(None)

    def get_process_id(self):
        """ generate a process id """
        self.max_process_id = increment(self.max_process_id)
        return self.max_process_id


    # ------------- general private functions

    def _shutdown(self):
        with self._lock:
            self._mq.close()

            # stop the applications.
            for ctl in self.mapps:
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
            for appname, templates in self.apps.items():
                for name in templates:
                    self._stop_template(name, appname)

            self._tracker.on_done(self._shutdown)

    def _restart(self, callback):
        with self._lock:
            # on restart we first restart the applications
            for app in self.mapps:
                app.restart()

            # then we restart the temlates
            for appname, templates in self.apps.items():
                for name in templates:
                    self._restart_processes(templates[name])

            # if any callback has been set, run it
            if callback is not None:
                callback(self)


    # ------------- templates private functions

    def _is_found(self, name, appname):
        if appname not in self.apps:
            raise ProcessError(404, "not_found")

        if not name in self.apps[appname]:
            raise ProcessError(404, "not_found")

    def _stop_template(self, name, appname):
        """ stop all processes in a template """
        self._is_found(name, appname)

        # get the template
        state = self.apps[appname][name]

        # if all process have already been stopped then return
        if state.stopped:
            return

        # mark this template as stopped
        state.stopped = True

        # notify others that all processes of the templates are beeing
        # stopped.
        self._publish("stop", name=name, appname=appname)
        self._publish("proc.%s.%s.stop" % (appname, name), appname=appname,
                name=name)

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
            self._publish("proc.%s.stop" % p.pid, name=p.name,
                    appname=appname, pid=p.pid, os_pid=p.os_pid)
            self._publish("proc.%s.%s.stop_pid" % (p.appname, p.name),
                    name=p.name, pid=p.pid, os_pid=p.os_pid)

            # remove the pid from the running processes
            if p.pid in self.running:
                self.running.pop(p.pid)

            # stop the process
            p.stop()
            # track this process to make sure it's killed after the
            # graceful time
            self._tracker.check(p, state.graceful_timeout)


    # ------------- functions that manage the process

    def _spawn_process(self, state):
        """ spawn a new process and add it to the state """
        # get internal process id
        pid = self.get_process_id()

        # start process
        p = state.make_process(self.loop, pid, self._on_process_exit)
        p.spawn()

        # add the process to the running state
        state.queue(p)

        # we keep a list of all running process by id here
        self.running[pid] = p

        self._publish("spawn", appname=p.appname, name=p.name, pid=pid,
                detached=p.detach, os_pid=p.os_pid)
        self._publish("proc.%s.%s.spawn" % (p.appname, p.name), name=p.name,
                appname=p.appname, pid=pid, detached=p.detach,
                os_pid=p.os_pid)

        self._publish("proc.%s.spawn" % pid, name=p.name,
                appname=p.appname, pid=pid, detached=p.detach,
                os_pid=p.os_pid)

    def _spawn_processes(self, state):
        """ spawn all processes for a state """
        num_to_start = state.numprocesses - len(state.running)
        for i in range(num_to_start):
            self._spawn_process(state)

    def _reap_processes(self, state):
        if state.stopped:
            return

        diff = len(state.running) - state.numprocesses
        if diff > 0:
            for i in range(diff):
                # remove the process from the running processes
                try:
                    p = state.dequeue()
                except IndexError:
                    return

                # remove the pid from the running processes
                if p.pid in self.running:
                    self.running.pop(p.pid)

                # stop the process
                p.stop()

                # track this process to make sure it's killed after the
                # graceful time
                self._tracker.check(p, state.graceful_timeout)

                # notify others that the process is beeing reaped
                self._publish("reap", name=p.name, pid=p.pid, os_pid=p.os_pid)
                self._publish("proc.%s.%s.reap" % (p.appname, p.name),
                        name=p.name, appname=p.appname, pid=p.pid,
                        os_pid=p.os_pid)
                self._publish("proc.%s.reap" % p.pid,
                        name=p.name, appname=p.appname, pid=p.pid,
                        os_pid=p.os_pid)

    def _manage_processes(self, state):
        if state.stopped:
            return

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
            self._stop_template(state.name, state.appname)
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
        self.events.publish(evtype, event)


    # ------------- events handler

    def _handle_messages(self, msg, err):
        if not msg:
            return

        if msg == "STOP":
            self.stop()

        elif six.callable(msg):
            msg()

    def _on_exit(self, evtype, msg):
        appname = msg['appname']
        name = msg['name']

        with self._lock:
            try:
                state = self.apps[appname][name]
            except KeyError:
                return

            # eventually restart the process
            if not state.stopped:
                # manage the template, eventually restart a new one.

                if self._check_flapping(state):
                    self._manage_processes(state)

    def _on_process_exit(self, process, exit_status, term_signal):
        with self._lock:
            # maybe uncjeck this process from the tracker
            self._tracker.uncheck(process)

            # unexpected exit, remove the process from the list of
            # running processes.
            if process.pid in self.running:
                self.running.pop(process.pid)

            try:
                state = self.apps[process.appname][process.name]
                # remove the process from the state if needed
                state.remove(process)
            except KeyError:
                pass

            # notify other that the process exited
            ev_details = dict(name=process.name, appname=process.appname,
                    pid=process.pid, exit_status=exit_status,
                    term_signal=term_signal, os_pid=process.os_pid)

            self._publish("exit", **ev_details)
            self._publish("proc.%s.%s.exit" % (process.appname, process.name),
                **ev_details)
            self._publish("proc.%s.exit" % process.pid, **ev_details)
