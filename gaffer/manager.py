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
from .error import ProcessError, ProcessConflict, ProcessError
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


    def load(self, config, sessionid=None, env=None, start=False):
        """  load a process config object.

        Args:

        - **config**: a ``process.ProcessConfig`` instance
        - **sessionid**: Some processes only make sense in certain contexts.
          this flag instructs gaffer to maintain this process in the sessionid
          context. A context can be for example an application. If no session
          is specified the config will be attached to the ``default`` session.

        - **env**: dict, None by default, if specified the config env variable will
          be updated with the env values.
        """

        sessionid = self._sessionid(sessionid)

        with self._lock:
            if sessionid in self._sessions:
                # if the process already exists in this context raises a
                # conflict.
                if config.name in self._sessions[sessionid]:
                    raise ProcessConflict()
            else:
                # initialize this session
                self._sessions[sessionid] = OrderedDict()

            state = ProcessState(config, sessionid, env)
            pname = "%s.%s" % (sessionid, config.name)
            self._publish("create", name=pname)

        if start:
            self.start(pname)

    def unload(self, name_or_process, sessionid=None):
        """ unload a process config. """

        sessionid = self._sessionid(sessionid)
        name = self._get_pname(name_or_process)
        with self._lock:
            if sessionid not in self._sessions:
                raise ProcessNotfound()

            # get the state and remove it from the context
            session = self._sessions[sessionid]
            try:
                state = session.pop(pname)
            except KeyError:
                raise ProcessNotFound()

            # stop the process now.
            self._stop_process(state)

    def reload(self, name_or_process, sessionid=None):
        """ reload a process config. The number of processes is resetted to
        the one in settings and all current processes are killed """

        sessionid = self._sessionid(sessionid)
        name = self._get_pname(name_or_process)

        with self._lock:
            # reset the number of processes
            state = _get_state(self._sessionid, name)
            state.reset()

        # kill all the processes and let gaffer manage asynchronously the
        # reload
        self.killall("%s.%s" % (sessionid, name))


    def update(self, config, sessionid=None, env=None, start=False):
        """ update a process config. All processes are killed """
        sessionid = self._sessionid(sessionid)

        with self._lock:
            state = _get_state(sessionid, config.name)
            state.update(config, env=env)

            if start:
                # make sure we unstop the process
                state.stop = False

        # kill all the processes and let gaffer manage asynchronously the
        # reload. If the process is not stopped then it will start
        self.killall("%s.%s" % (sessionid, name))


    def start_process(self, name):
        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)

        with self._lock:
            state = _get_state(sessionid, name)

            # make sure we unstop the process
            state.stop = False

            # notify that we are starting the process
            self._publish("start", name=pname)
            self._publish("proc.%s.start" % pname, name=pname)

            # manage processes
            self._manage_processes(state)

    def stop_process(self, name):
        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)


        with self._lock:
            state = _get_state(sessionid, name)
            # flag the state to stop
            state.stop = True
            # reset the number of processes
            state.reset()

            # notify that we are stoppping the process
            self._publish("stop", name=pname)
            self._publish("proc.%s.stop" % pname, name=pname)


        # kill all the processes. Since the state has been marked to stop then
        # they won't be restarted.
        self.stopall("%s.%s" % (sessionid, name))



    def get_job(self, pid):
        """ get a job by ID. A job is a ``gaffer.Process`` instance attached
        to a process state that you can use.
        """
        with self._lock:
            try:
                return self.running[pid]
            except KeyError:
                raise ProcessNotFound()

    def stop_job(self, pid):
        with self._lock:

            # remove the job from the runnings jobs
            try:
                p = self.running.pop(pid)
            except KeyError:
                raise ProcessNotFound()

            # remove the process from the state
            sessionid, name = self._parse_name(name)
            state = self._get_state(sessionid, name)
            state.remove(p)

            # notify we stop this job
            self._publish("job.%s.stop" % p.pid, pid=p.pid, name=p.name)

            # then stop the job
            p.stop()

    def stopall(self, name):
        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)

        with self._lock:
            state = _get_state(sessionid, name)
            self._publish("proc.%s.kill" % pname, name=pname, signum=signum)


    def kill(self, pid, signum):
        with self._lock:
            try:
                p = self.running[pid]
            except KeyError:
                raise ProcessNotFound()

            # notify we stop this job
            self._publish("job.%s.kill" % p.pid, pid=p.pid, name=p.name)

            # effectively send the signal
            p.kill(signum)



    def killall(self, name, signum):
        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)
        with self._lock:
            state = _get_state(sessionid, name)
            self._publish("proc.%s.kill" % pname, name=pname, signum=signum)
            for p in state.running:

                # notify we stop this job
                self._publish("job.%s.kill" % p.pid, pid=p.pid, name=p.name)

                # effectively send the signal
                p.kill(signum)






    def _sessionid(self, session=None):
        if not session:
            return "default"
        return session

    def _get_pname(self, name_or_process):
        if hasattr(name_or_process, "name"):
            return name_or_process.name
        else:
            return name_or_process


    def _parse_name(self, name):
        if "." in name:
            sessionid, name = name.split(".", 1)

        else:
            sessionid = "default"

        return sessionid, name

    def _get_state(self, sessionid, name):
        if sessionid not in self._sessions:
            raise ProcessNotfound()

        session = self._sessions[sessionid]
        if name not in session:
            raise ProcessNotfound()

        return session[name]







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


    def _stopall(self, state):

        if state.flapping_timer is not None:
            state.flapping_timer.stop()

        while True:
            try:
                p = state.dequeue()
            except IndexError:
                break

            if p.pid in self.running:
                # there is no reason to not have the pid there but make sure
                # it won't be the case
                del self.running[p.pid]

            p.stop()

        if not state.stopped:
            state.flapping_timer.start()

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
