# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import deque
import json
import os
import signal
import shlex

import pyuv
import psutil
import six

from .util import bytestring, getcwd, check_uid, check_gid, bytes2human
from .sync import atomic_read, increment, decrement

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
        info['children'].append(get_info(psutil.Process(child),
            interval=interval))

    return info


class RedirectIO(object):

    def __init__(self, loop, label, stream, process):
        self.loop = loop
        self.label = label

        if stream is None:
            self._stdio = pyuv.StdIO(flags=pyuv.UV_IGNORE)
        else:
            self.channel = pyuv.Pipe(loop, True)
            self._stdio = pyuv.StdIO(stream=self.channel,
                                    flags=pyuv.UV_CREATE_PIPE | \
                                            pyuv.UV_READABLE_PIPE | \
                                            pyuv.UV_WRITABLE_PIPE)
        self.stream = stream

    @property
    def stdio(self):
        return self._stdio

    def start(self):
        self.channel.start_read(self._on_read)

    def _on_read(self, handle, data, error):
        # redirect the message to the main pipe
        if data:
            msg = { "name": self.process.name,
                    "pid": self.process_type,
                    "label": self.label,
                    "data": data,
                    "msg_type": "redirect"}
            handle.write2(json.dumps(msg), self.stream)


class ProcessWatcher(object):
    """ object to retrieve process stats """

    def __init__(self, loop, pid, on_refresh_cb=None):
        self.loop = loop
        self.pid = pid
        self.on_refresh_cb = on_refresh_cb
        self._process = psutil.Process(pid)
        self._last_info = None
        self.active = True
        self._timer = pyuv.Timer(loop)
        self._timer.start(self._async_refresh, 0.1, 0.1)

    def _async_refresh(self, handle):
        self._last_info = refresh()
        if self.on_refresh_cb is not None:
            self.on_refresh_cb(self, self._last_info)

    def get_infos(self):
        if not self._last_info:
            self._last_info = refresh(0.1)
        return self._last_info

    def refresh(self, interval=0):
        return get_process_info(self._process, interval=interval)

    def stop(self):
        self.active = decrement(self.active)
        self._timer.stop()

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

    """


    def __init__(self, loop, id, name, cmd, group=None, args=None, env=None,
            uid=None, gid=None, cwd=None, detach=False, redirect_stream=[],
            monitor=False, monitor_cb=None, on_exit_cb=None):
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

        self.uid = uid
        if self.uid is not None:
            self.uid = check_uid(uid)

        self.gid = gid
        if self.gid is not None:
            self.gid = check_gid(gid)

        self.cwd = cwd or getcwd()
        self.env = env or {}
        self.redirect_stream = redirect_stream
        self.stdio = self._setup_stdio()
        self.detach = detach
        self.monitor = monitor
        self.monitor_cb = monitor_cb
        self.on_exit_cb = on_exit_cb
        self._process = None
        self._pprocess = None
        self._process_watcher = None
        self.stopped = False

    def _setup_stdio(self):
        stdio = []

        if not self.redirect_stream:
            # no redirect streams, ignore all
            for i in range(3):
                stdio.append(pyuv.StdIO(flags=pyuv.UV_IGNORE))
        else:
            # for now we ignore all stdin
            stdio.append(pyuv.StdIO(flags=pyuv.UV_IGNORE))

            # setup redirections
            for stream in redirect_stream:
                stdio.append(RedirectIO(self.loop, "stdout", stream))
                stdio.append(RedirectIO(self.loop, "stderr", stream))

        return stdio

    def spawn(self):
        """ spawn the process """
        kwargs = dict(
                file = self.cmd,
                exit_callback = self._exit_cb,
                args = self.args,
                env = self.env,
                cwd = self.cwd,
                stdio = self.stdio)

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
        self._process.disable_stdio_inheritance()

        # spawn the process
        self._process.spawn(**kwargs)
        self._running = True

        # start redirection
        for stream in self.redirect_stream:
            stream.start()

        if self.monitor:
            self.start_monitor()

    @property
    def active(self):
        return self._running

    @property
    def pid(self):
        """ return the process pid """
        return self._process.pid

    @property
    def info(self):
        """ return the process info. If the process is monitored it
        return the last informations stored asynchronously by the watcher"""

        if not self._process_watcher:
            if not self._pprocess:
                self._pprocess = psutil.Process(self.pid)
            return get_process_info(self._pprocess, 0.1)
        else:
            return self._process_watcher.get_info()

    @property
    def monitored(self):
        """ return True if the process is monitored """
        return self._process_watcher is not None

    def start_monitor(self, monitor_cb=None):
        """ start to monitor the process """
        on_refresh_cb = monitor_cb or self.monitor_cb
        self._process_watcher = ProcessWatcher(self.loop, self.pid,
                on_refresh_cb=monitor_cb)

    def stop_monitor(self):
        """ stop to moonitor the process """
        if atomic_read(self.monitored):
            self._process_watcher.stop()
            self._process_watcher = None

    def stop(self):
        """ stop the process """
        self.kill(signal.SIGTERM)

    def kill(self, signum):
        """ send a signal to the process """
        self._process.kill(signum)

    def _exit_cb(self, handle, exit_status, term_signal):

        # stop monitoring
        self.stop_monitor()
        self._process.close()
        self._running = False

        if not self.on_exit_cb:
            return

        self.on_exit_cb(self, exit_status, term_signal)
