# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
The process module wrap a process and IO redirection

"""


from datetime import timedelta
import os
import signal
import shlex

import pyuv
import psutil
from psutil.error import AccessDenied, NoSuchProcess
import six

from .events import EventEmitter
from .util import (bytestring, getcwd, check_uid, check_gid,
        bytes2human)
from .sync import atomic_read, increment, decrement

pyuv.Process.disable_stdio_inheritance()

def get_process_info(process=None, interval=0):

    """Return information about a process. (can be an pid or a Process object)

    If process is None, will return the information about the current process.
    """
    if process is None:
        process = psutil.Process(os.getpid())
    info = {}
    try:
        mem_info = process.get_memory_info()
        info['mem_info1'] = bytes2human(mem_info[0])
        info['mem_info2'] = bytes2human(mem_info[1])
    except AccessDenied:
        info['mem_info1'] = info['mem_info2'] = "N/A"

    try:
        info['cpu'] = process.get_cpu_percent(interval=interval)
    except AccessDenied:
        info['cpu'] = "N/A"

    try:
        info['mem'] = round(process.get_memory_percent(), 1)
    except AccessDenied:
        info['mem'] = "N/A"

    try:
        cpu_times = process.get_cpu_times()
        ctime = timedelta(seconds=sum(cpu_times))
        ctime = "%s:%s.%s" % (ctime.seconds // 60 % 60,
                        str((ctime.seconds % 60)).zfill(2),
                        str(ctime.microseconds)[:2])
    except AccessDenied:
        ctime = "N/A"

    info['ctime'] = ctime

    try:
        info['pid'] = process.pid
    except AccessDenied:
        info['pid'] = 'N/A'

    try:
        info['username'] = process.username
    except AccessDenied:
        info['username'] = 'N/A'

    try:
        info['nice'] = process.nice
    except AccessDenied:
        info['nice'] = 'N/A'
    except NoSuchProcess:
        info['nice'] = 'Zombie'

    try:
        cmdline = os.path.basename(shlex.split(process.cmdline[0])[0])
    except (AccessDenied, IndexError):
        cmdline = "N/A"

    info['cmdline'] = cmdline

    info['children'] = []
    for child in process.get_children():
        info['children'].append(get_process_info(psutil.Process(child),
            interval=interval))

    return info

class RedirectIO(object):

    def __init__(self, loop, process, stdio=[]):
        self.loop = loop
        self.process = process
        self._emitter = EventEmitter(loop)

        self._stdio = []
        self._channels = []

        if not stdio:
            self._stdio = [pyuv.StdIO(flags=pyuv.UV_IGNORE),
                    pyuv.StdIO(flags=pyuv.UV_IGNORE)]

        else:
            # create (channel, stdio) pairs
            for label in stdio[:2]:
                # io registered can any label, so it's easy to redirect
                # stderr to stdout, just use the same label.
                p = pyuv.Pipe(loop)
                io = pyuv.StdIO(stream=p, flags=pyuv.UV_CREATE_PIPE | \
                                                pyuv.UV_READABLE_PIPE | \
                                                pyuv.UV_WRITABLE_PIPE)
                setattr(p, 'label', label)
                self._channels.append(p)
                self._stdio.append(io)

    def start(self):
        # start reading
        for p in self._channels:
            p.start_read(self._on_read)

    @property
    def stdio(self):
        return self._stdio

    def subscribe(self, label, listener):
        self._emitter.subscribe(label, listener)

    def unsubscribe(self, label, listener):
        self._emitter.unsubscribe(label, listener)

    def stop(self):
        for p in self._channels:
            if p.active:
                p.close()

    def _on_read(self, handle, data, error):
        if not data:
            return

        label = getattr(handle, 'label')
        msg = dict(event=label, name=self.process.name,
                pid=self.process.id, data=data)
        self._emitter.publish(label, msg)


class RedirectStdin(object):
    """ redirect stdin allows multiple sender to write to same pipe """

    def __init__(self, loop, process):
        self.loop = loop
        self.process = process,
        self.channel = pyuv.Pipe(loop)
        self.stdio = pyuv.StdIO(stream=self.channel,
                flags=pyuv.UV_CREATE_PIPE | \
                        pyuv.UV_READABLE_PIPE | \
                        pyuv.UV_WRITABLE_PIPE )
        self._emitter = EventEmitter(loop)

    def start(self):
        self._emitter.subscribe("WRITE", self._on_write)
        self._emitter.subscribe("WRITELINES", self._on_writelines)

    def write(self, data):
        self._emitter.publish("WRITE", data)

    def writelines(self, data):
        self._emitter.publish("WRITELINES", data)

    def stop(self):
        if self.channel.active:
            self.channel.close()

    def _on_write(self, evtype, data):
        self.channel.write(data)

    def _on_writelines(self, evtype, data):
        self.channel.writelines(data)


class ProcessWatcher(object):
    """ object to retrieve process stats """

    def __init__(self, loop, pid):
        self.loop = loop
        self.pid = pid
        self._process = psutil.Process(pid)

        self._last_info = None
        self.on_refresh_cb = None
        self._active = 0
        self._refcount = 0
        self._emitter = EventEmitter(loop)


    @property
    def active(self):
        return atomic_read(self._active) > 0

    def subscribe(self, listener):
        self._refcount = increment(self._refcount)
        self._emitter.subscribe("stat", listener)
        self._start()

    def subscribe_once(self, listener):
        self._emitter.subscribe_once("stat", listener)

    def unsubscribe(self, listener):
        self._emitter.unsubscribe(".", listener)
        self._refcount = decrement(self._refcount)
        if not atomic_read(self._refcount):
            self.stop()

    def stop(self, all_events=False):
        if self.active:
            self._active = decrement(self._active)
            self._timer.stop()

        if all_events:
            self._emitter.close()

    def _async_refresh(self, handle):
        self._last_info = self.refresh()
        self._emitter.publish("stat", self._last_info)

    def refresh(self, interval=0):
        return get_process_info(self._process, interval=interval)

    def _start(self):
        if not self.active:
            self._timer = pyuv.Timer(self.loop)
            # start the timer to refresh the informations
            # 0.1 is the minimum interval to fetch cpu stats for this
            # process.
            self._timer.start(self._async_refresh, 0.1, 0.1)
            self._active = increment(self._active)

class Process(object):
    """ class wrapping a process

    Args:

    - **loop**: main application loop (a pyuv Loop instance)
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
      only)
    - **redirect_output**: list of io to redict (max 2) this is a list of custom
      labels to use for the redirection. Ex: ["a", "b"] will
      redirect stdoutt & stderr and stdout events will be labeled "a"
    - **redirect_input**: Boolean (False is the default). Set it if
      you want to be able to write to stdin.

    """


    def __init__(self, loop, id, name, cmd, group=None, args=None, env=None,
            uid=None, gid=None, cwd=None, detach=False, shell=False,
            redirect_output=[], redirect_input=False, on_exit_cb=None):
        self.loop = loop
        self.id = id
        self.name = name
        self.group = group
        self.cmd = cmd

        # set command
        self.cmd = bytestring(cmd)
        if args is not None:
            if isinstance(args, six.string_types):
                self.args = shlex.split(bytestring(args))
            else:
                self.args = [bytestring(arg) for arg in args]

        else:
            args_ = shlex.split(self.cmd)
            if len(args_) == 1:
                self.args = []
            else:
                self.cmd = args_[0]
                self.args = args_[1:]

        if shell:
            self.args = ['-c', cmd] + args
            self.cmd = "sh"

        self.uid = uid
        if self.uid is not None:
            self.uid = check_uid(uid)

        self.gid = gid
        if self.gid is not None:
            self.gid = check_gid(gid)

        self.cwd = cwd or getcwd()
        self.env = env or {}
        self.redirect_output = redirect_output
        self.redirect_input = redirect_input


        self._redirect_io = None
        self._redirect_in = None
        self.detach = detach
        self.on_exit_cb = on_exit_cb
        self._process = None
        self._pprocess = None
        self._process_watcher = None
        self._cached_pid = None
        self.stopped = False
        self.graceful_time = 0

        self._setup_stdio()


    def _setup_stdio(self):
        # for now we ignore all stdin
        if not self.redirect_input:
            self._stdio = [pyuv.StdIO(flags=pyuv.UV_IGNORE)]
        else:
            self._redirect_in = RedirectStdin(self.loop, self)
            self._stdio = [self._redirect_in.stdio]
        self._redirect_io = RedirectIO(self.loop, self,
                self.redirect_output)
        self._stdio.extend(self._redirect_io.stdio)

    def spawn(self):
        """ spawn the process """
        kwargs = dict(
                file = self.cmd,
                exit_callback = self._exit_cb,
                args = self.args,
                env = self.env,
                cwd = self.cwd,
                stdio = self._stdio)

        flags = 0
        if self.uid is not None:
            kwargs['uid'] = self.uid
            flags = pyuv.UV_PROCESS_SETUID

        if self.gid is not None:
            kwargs['gid'] = self.gid
            flags = flags | pyuv.UV_PROCESS_SETGID

        if self.detach:
            flags = flags | pyuv.UV_PROCESS_DETACHED

        self.running = True
        self._process = pyuv.Process(self.loop)

        # spawn the process
        self._process.spawn(**kwargs)
        self._running = True
        self._cached_pid = self._process.pid

        # start redirecting IO
        self._redirect_io.start()

        if self._redirect_in is not None:
            self._redirect_in.start()

    @property
    def active(self):
        return self._process.active

    @property
    def closed(self):
        return self._process.closed

    @property
    def pid(self):
        """ return the process pid """
        if self._cached_pid is None:
            self._cached_pid = self._process.pid
        return self._cached_pid

    @property
    def info(self):
        """ return the process info. If the process is monitored it
        return the last informations stored asynchronously by the watcher"""

        if not self._pprocess:
            self._pprocess = psutil.Process(self.pid)
        return get_process_info(self._pprocess, 0.1)

    @property
    def status(self):
        """ return the process status """
        if not self._pprocess:
            self._pprocess = psutil.Process(self.pid)
        return self._pprocess.status


    def __lt__(self, other):
        return (self.pid != other.pid and
                self.graceful_time < other.graceful_time)

    __cmp__ = __lt__

    def monitor(self, listener=None):
        """ start to monitor the process

        Listener can be any callable and receive *("stat", process_info)*
        """

        if not self._process_watcher:
            self._process_watcher = ProcessWatcher(self.loop, self.pid)

        self._process_watcher.subscribe(listener)

    def unmonitor(self, listener):
        """ stop monitoring this process.

        listener is the callback passed to the monitor function
        previously.
        """
        if not self._process_watcher:
            return

        self._process_watcher.unsubscribe(listener)

    def monitor_io(self, io_label, listener):
        """ subscribe to registered IO events """
        if not self._redirect_io:
            raise IOError("%s not redirected" % self.name)
        self._redirect_io.subscribe(io_label, listener)

    def unmonitor_io(self, io_label, listener):
        """ unsubscribe to the IO event """
        if not self._redirect_io:
            return
        self._redirect_io.unsubscribe(io_label, listener)

    def write(self, data):
        """ send data to the process via stdin"""
        if not self._redirect_in:
            raise IOError("stdin not redirected")
        self._redirect_in.write(data)

    def writelines(self, data):
        """ send data to the process via stdin"""

        if not self._redirect_in:
            raise IOError("stdin not redirected")
        self._redirect_in.writelines(data)

    def stop(self):
        """ stop the process """
        self.kill(signal.SIGTERM)

    def kill(self, signum):
        """ send a signal to the process """
        if not self.active:
            return

        self._process.kill(signum)

    def close(self):
        self._process.close()

    def _exit_cb(self, handle, exit_status, term_signal):
        if self._redirect_io is not None:
            self._redirect_io.stop()

        if self._redirect_in is not None:
            self._redirect_in.stop()

        self._running = False
        handle.close()

        # handle the exit callback
        if self.on_exit_cb is not None:
            self.on_exit_cb(self, exit_status, term_signal)
