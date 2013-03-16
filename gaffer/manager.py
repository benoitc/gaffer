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
from collections import deque, OrderedDict
from threading import RLock

import pyuv

from .events import EventEmitter
from .error import ProcessError, ProcessConflict, ProcessNotFound
from .pubsub import Topic
from .state import ProcessState, ProcessTracker
from .sync import increment
from .util import parse_signal_value


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
        self._sessions = OrderedDict()
        self._topics = {}
        self._updates = deque()
        self._signals = []

        self.status = -1
        self.stop_cb = None
        self.restart_cb = None
        self._lock = RLock()

    @property
    def active(self):
        return self.status == 0 and self.started

    def start(self, apps=[]):
        """ start the manager. """
        self.mapps = apps

        self._waker = pyuv.Async(self.loop, self._wakeup)

        # start the process tracker
        self._tracker.start()

        # manage processes
        self.events.subscribe('exit', self._on_exit)

        # start contollers
        for mapp in self.mapps:
            mapp.start(self.loop, self)

        self.started = True
        self.status = 0

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

        if not self.started:
            return

        if self.status == 1:
            # someone already requested to stop the manager
            return

        # set the callback
        self.stop_cb = callback

        # update the status to stop and wake up the loop
        self.status = 1
        self._waker.send()

    def restart(self, callback=None):
        """ restart all processes in the manager. This function is
        threadsafe """
        if self.status == 2:
            # a restart is already running
            return

        self.restart_cb = callback
        self.status = 2
        self._waker.send()

    def subscribe(self, topic):
        if topic not in self._topics:
            self._topics[topic] = Topic(topic, self)
            self._topics[topic].start()

        return self._topics[topic].subscribe()

    def unsubscribe(self, topic, channel):
        if topic not in self._topics:
            return
        self._topics[topic].unsubscribe(channel)

    @property
    def sessions(self):
        return list(self._sessions)

    def jobs(self, sessionid=None):
        if not sessionid:
            jobs = []
            for sessionid in self._sessions:
                session = self._sessions[sessionid]
                jobs.extend(["%s.%s" % (sessionid, name) for name in session])
            return jobs
        else:
            try:
                session = self._sessions[sessionid]
            except KeyError:
                raise ProcessNotFound()

            return ["%s.%s" % (sessionid, name) for name in session]


    def jobs_walk(self, callback, sessionid=None):
        with self._lock:
            if not sessionid:
                for sessionid in self._sessions:
                    for name in self._sessions[sessionid]:
                        callback(self, "%s.%s" % (sessionid, name))
            else:
                try:
                    session = self._sessions[sessionid]
                except KeyError:
                    raise ProcessNotFound()

                for name in session:
                    callback(self, "%s.%s" % (sessionid, name))

    # ------------- process functions

    def load(self, config, sessionid=None, env=None, start=True):
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
                self._sessions[sessionid] = OrderedDict()

            # create a new state for this config
            state = ProcessState(config, sessionid, env)
            self._sessions[sessionid][config.name] = state

            pname = "%s.%s" % (sessionid, config.name)
            self._publish("load", name=pname)

        if start:
            self.start_job(pname)

    def unload(self, name_or_process, sessionid=None):
        """ unload a process config. """

        sessionid = self._sessionid(sessionid)
        name = self._get_pname(name_or_process)

        pname = "%s.%s" % (sessionid, name)

        with self._lock:
            if sessionid not in self._sessions:
                raise ProcessNotFound()

            # get the state and remove it from the context
            session = self._sessions[sessionid]
            try:
                state = session.pop(name)
            except KeyError:
                raise ProcessNotFound()

            if not session:
                try:
                    del self._sessions[sessionid]
                except KeyError:
                    pass

            # notify that we unload the process
            self._publish("unload", name=pname)

            # notify that we are stoppping the process
            self._publish("stop", name=pname)
            self._publish("job.%s.stop" % pname, name=pname)

            # stop the process now.
            state.stopped = True
            self._stopall(state)

    def reload(self, name, sessionid=None):
        """ reload a process config. The number of processes is resetted to
        the one in settings and all current processes are killed """

        if not sessionid:
            if hasattr(name, "name"):
                sessionid = 'default'
                name = getattr(name, 'name')
            else:
                sessionid, name = self._parse_name(name)
        else:
            name = self._get_pname(name)

        with self._lock:
            # reset the number of processes
            state = self._get_state(sessionid, name)
            state.reset()

            # kill all the processes and let gaffer manage asynchronously the
            # reload
            self._stopall(state)

            # manage processes
            self._manage_processes(state)

    def update(self, config, sessionid=None, env=None, start=False):
        """ update a process config. All processes are killed """
        sessionid = self._sessionid(sessionid)

        with self._lock:
            state = self._get_state(sessionid, config.name)
            state.update(config, env=env)

            if start:
                # make sure we unstop the process
                state.stop = False

            # kill all the processes and let gaffer manage asynchronously the
            # reload. If the process is not stopped then it will start
            self._stopall(state)

    def get(self, name):
        """ get a job config """
        sessionid, name = self._parse_name(name)
        with self._lock:
            state = self._get_state(sessionid, name)
            return state.config


    def start_job(self, name):
        """ Start a job from which the config have been previously loaded """

        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)

        with self._lock:
            state = self._get_state(sessionid, name)

            # make sure we unstop the process
            state.stopped = False
            # reset the number of processes
            state.reset()

            # notify that we are starting the process
            self._publish("start", name=pname)
            self._publish("job.%s.start" % pname, name=pname)

            # manage processes
            self._manage_processes(state)

    def stop_job(self, name):
        """ stop a jon. All processes of this job are stopped and won't be
        restarted by the manager """

        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)

        with self._lock:
            state = self._get_state(sessionid, name)

            # put the number to 0
            state.numprocesses = 0
            # flag the state to stop
            state.stopped = True

            # notify that we are stoppping the process
            self._publish("stop", name=pname)
            self._publish("job.%s.stop" % pname, name=pname)

            self._stopall(state)

    def commit(self, name, graceful_timeout=0, env=None):
        """ Like ``scale(1) but the process won't be kept alived at the end.
        It is also not handled uring scaling or reaping. """

        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)

        with self._lock:
            state = self._get_state(sessionid, name)

            # commit the job and return the pid
            return self._commit_process(state,
                    graceful_timeout=graceful_timeout, env=env)

    def scale(self, name, n):
        """ Scale the number of processes in for a job. By using this
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
        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)

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
                n = int(n[1:])

        with self._lock:
            state = self._get_state(sessionid, name)

            # scale
            if op == "=":
                curr = state.numprocesses
                if curr > n:
                    ret = state.decr(curr - n)
                else:
                    ret = state.incr(n - curr)
            elif op == "+":
                ret = state.incr(n)
            else:
                ret = state.decr(n)
            self._publish("update", name=pname)
            self._manage_processes(state)
            return ret

    def info(self, name):
        """ get job' infos """
        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)

        with self._lock:
            state = self._get_state(sessionid, name)

        processes = list(state.running)
        processes.extend(list(state.running_out))

        info = {"name": pname,
                "active":  state.active,
                "running": len(processes),
                "running_out": len(state.running_out),
                "max_processes": state.numprocesses,
                "processes": [p.pid for p in processes]}

        # get config
        config = state.config.to_dict()

        # remove custom channels because they can't be serialized
        config.pop('custom_channels', None)

        # add config to the info
        info['config'] = config
        return info

    def stats(self, name):
        """ return job stats

        """
        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)


        with self._lock:
            state = self._get_state(sessionid, name)
            processes = list(state.running)
            processes.extend(list(state.running_out))

            stats = []
            lmem = []
            lcpu = []
            for p in processes:
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

            ret = dict(name=pname, stats=stats, mem=mem,
                    max_mem=max_mem, min_mem=min_mem, cpu=cpu,
                    max_cpu=max_cpu, min_cpu=min_cpu)

            return ret

    def get_process(self, pid):
        """ get an OS process by ID. A process is a ``gaffer.Process`` instance
        attached to a process state that you can use.
        """
        with self._lock:
            return self._get_pid(pid)

    def stop_process(self, pid):
        """ stop a process """
        with self._lock:
            # remove the job from the runnings jobs
            try:
                p = self.running.pop(pid)
            except KeyError:
                raise ProcessNotFound()

            # remove the process from the state
            sessionid, name = self._parse_name(p.name)
            state = self._get_state(sessionid, name)

            # if the process is marked once it means the job has been
            # committed and the process shouldn't be restarted
            if p.once:
                state.running_out.remove(p)
            else:
                state.remove(p)

            # notify we stop this pid
            self._publish("stop_process", pid=p.pid, name=p.name)

            # then stop the process
            p.stop()

            # track this process to make sure it's killed after the
            # graceful time
            graceful_timeout = p.graceful_timeout or state.graceful_timeout
            self._tracker.check(p, graceful_timeout)

    def stopall(self, name):
        """ stop all processes of a job. Processes are just exiting and will
        be restarted by the manager. """

        sessionid, name = self._parse_name(name)
        with self._lock:
            state = self._get_state(sessionid, name)
            # kill all the processes.
            self._stopall(state)


    def kill(self, pid, sig):
        """ send a signal to a process """
        signum = parse_signal_value(sig)
        with self._lock:
            p = self._get_pid(pid)

            # notify we stop this job
            self._publish("proc.%s.kill" % p.pid, pid=p.pid, name=p.name)

            # effectively send the signal
            p.kill(signum)

    def send(self, pid, lines, stream=None):
        """ send some data to the process """
        with self._lock:
            p = self._get_pid(pid)

            # find the stream we need to write to
            if not stream or stream == "stdin":
                target = p
            else:
                if stream in p.streams:
                    target = p.streams[stream]
                else:
                    raise ProcessError(404, "stream_not_found")

            # finally write to the stream
            if isinstance(lines, list):
                target.writelines(lines)
            else:
                target.write(lines)


    def killall(self, name, sig):
        """ send a signal to all processes of a job """
        signum = parse_signal_value(sig)
        sessionid, name = self._parse_name(name)
        pname = "%s.%s" % (sessionid, name)
        with self._lock:
            state = self._get_state(sessionid, name)
            self._publish("job.%s.kill" % pname, name=pname, signum=signum)

            processes = list(state.running)
            processes.extend(list(state.running_out))
            for p in processes:
                # notify we stop this job
                self._publish("proc.%s.kill" % p.pid, pid=p.pid, name=p.name)
                # effectively send the signal
                p.kill(signum)

            self._manage_processes(state)

    def walk(self, callback, name=None):
        with self._lock:
            if not name:
                processes = [p for pid, p in self.running.items()]
            else:
                sessionid, name = self._parse_name(name)
                state = self._get_state(sessionid, name)
                processes = state.running

            for p in processes:
                callback(self, p)

    def list(self, name=None):
        with self._lock:
            if not name:
                processes = [p for pid, p in self.running.items()]
            else:
                sessionid, name = self._parse_name(name)
                state = self._get_state(sessionid, name)
                processes = state.running
            return list(processes)

    def pids(self, name=None):
        return [p.pid for p in self.list(name=name)]

    def manage(self, name):
        sessionid, name = self._parse_name(name)
        with self._lock:
            state = self._get_state(sessionid, name)
            self._manage_processes(state)

    def monitor(self, listener, name):
        """ get stats changes on a process template or id
        """

        sessionid, name = self._parse_name(name)
        with self._lock:
            state = self._get_state(sessionid, name)
            for p in state.running:
                p.monitor(listener)

    def unmonitor(self, listener, name):
        """ get stats changes on a process template or id
        """
        sessionid, name = self._parse_name(name)
        with self._lock:
            state = self._get_state(sessionid, name)
            for p in state.running:
                p.unmonitor(listener)


    # ------------- general purpose utilities

    def wakeup(self):
        self._waker.send()

    def get_process_id(self):
        """ generate a process id """
        self.max_process_id = increment(self.max_process_id)
        return self.max_process_id

    def _get_locked_state(self, name):
        """ utility function to get a state from name generally used for debug
        """
        sessionid, name = self._parse_name(name)
        with self._lock:
            return self._get_state(sessionid, name)


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
        elif "/" in name:
            sessionid, name = name.split("/", 1)
        else:
            sessionid = "default"

        return sessionid, name

    def _get_state(self, sessionid, name):
        if sessionid not in self._sessions:
            raise ProcessNotFound()

        session = self._sessions[sessionid]
        if name not in session:
            raise ProcessNotFound()

        return session[name]

    def _get_pid(self, pid):
        try:
            return self.running[pid]
        except KeyError:
            raise ProcessNotFound()



    # ------------- general private functions

    def _shutdown(self):
        with self._lock:

            self._tracker.stop()

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
            for sid in self._sessions:
                for name, state in self._sessions[sid].items():
                    if not state.stopped:
                        state.stopped = True
                        self._stopall(state)

            self._tracker.on_done(self._shutdown)

    def _restart(self):
        with self._lock:
            # on restart we first restart the applications
            for app in self.mapps:
                app.restart()

            # then we restart the sessions
            for sid in self._sessions:
                session = self._sessions[sid]
                for name in session:
                    self._restart_processes(session[name])

            # if any callback has been set, run it
            if self.restart_cb is not None:
                self.restart_cb(self)
                self.restart_cb = None

            self.status = 0


    # ------------- process type private functions

    def _stop_group(self, state, group):
        while True:
            try:
                p = group.popleft()
            except IndexError:
                break

            if p.pid not in self.running:
                continue

            self.running.pop(p.pid)

            # notify we stop this pid
            self._publish("stop_process", pid=p.pid, name=p.name)

            # stop the process
            p.stop()

            # track this process to make sure it's killed after the
            # graceful time
            graceful_timeout = p.graceful_timeout or state.graceful_timeout
            self._tracker.check(p, graceful_timeout)

    def _stopall(self, state):
        """ stop all processes of a job """

        # stop the flapping detection before killing the process to prevent
        # any race condition
        if state.flapping_timer is not None:
            state.flapping_timer.stop()

        # kill all keepalived processes
        if state.running:
            self._stop_group(state, state.running)

        # kill all others processes (though who have been committed)
        if state.running_out:
            self._stop_group(state, state.running_out)

        # if the job isn't stopped, restart the flapping detection
        if not state.stopped and state.flapping_timer is not None:
            state.flapping_timer.start()

    # ------------- functions that manage the process

    def _commit_process(self, state, graceful_timeout=10.0, env=None):
        """ like spawn but doesn't keep the process associated to the state.
        It should die at the end """
        # get internal process id
        pid = self.get_process_id()

        # start process
        p = state.make_process(self.loop, pid, self._on_process_exit)
        p.spawn(once=True, graceful_timeout=graceful_timeout, env=env)

        # add the pid to external processes in the state
        state.running_out.append(p)

        # we keep a list of all running process by id here
        self.running[pid] = p

        # notify
        self._publish("spawn", name=p.name, pid=pid, os_pid=p.os_pid)

        # on commit we return the pid now, so someone will be able to use it.
        return pid


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

        self._publish("spawn", name=p.name, pid=pid, os_pid=p.os_pid)
        self._publish("job.%s.spawn" % p.name, name=p.name, pid=pid,
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
                self._publish("job.%s.reap" % p.name, name=p.name, pid=p.pid,
                        os_pid=p.os_pid)
                self._publish("proc.%s.reap" % p.pid,
                        name=p.name, pid=p.pid, os_pid=p.os_pid)

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
            if not state.stopped:
                state.stopped = True
                self._stopall(state)

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

    def _wakeup(self, handle):
        if self.status == 1:
            handle.close()
            self._stop()

        elif self.status == 2:
            self._restart()

    def _on_exit(self, evtype, msg):
        sessionid, name = self._parse_name(msg['name'])
        once = msg.get('once', False)

        with self._lock:
            try:
                state = self._get_state(sessionid, name)
            except ProcessNotFound:
                # race condition, we already removed this process
                return

            # eventually restart the process
            if not state.stopped and not once:
                # manage the template, eventually restart a new one.
                if self._check_flapping(state):
                    self._manage_processes(state)

    def _on_process_exit(self, process, exit_status, term_signal):
        with self._lock:
            # maybe uncheck this process from the tracker
            self._tracker.uncheck(process)

            # unexpected exit, remove the process from the list of
            # running processes.
            if process.pid in self.running:
                self.running.pop(process.pid)

            sessionid, name = self._parse_name(process.name)
            try:
                state = self._get_state(sessionid, name)
                # remove the process from the state if needed
                if process.once:
                    state.running_out.remove(process)
                else:
                    state.remove(process)
            except (ProcessNotFound, KeyError):
                pass

            # notify other that the process exited
            ev_details = dict(name=process.name, pid=process.pid,
                    exit_status=exit_status, term_signal=term_signal,
                    os_pid=process.os_pid, once=process.once)

            self._publish("exit", **ev_details)
            self._publish("job.%s.exit" % process.name, **ev_details)
