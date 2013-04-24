# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
"""
The process module wrap a process and IO redirection

"""


from datetime import timedelta
from functools import partial
import os
import signal
import shlex

import pyuv
import psutil
from psutil.error import AccessDenied
import six

from .events import EventEmitter
from .util import (bytestring, getcwd, check_uid, check_gid,
        bytes2human, substitute_env, IS_WINDOWS)
from .sync import atomic_read, increment, decrement

pyuv.Process.disable_stdio_inheritance()

def get_process_stats(process=None, interval=0):

    """Return information about a process. (can be an pid or a Process object)

    If process is None, will return the information about the current process.
    """
    if process is None:
        process = psutil.Process(os.getpid())

    stats = {}
    try:
        mem_info = process.get_memory_info()
        stats['mem_info1'] = bytes2human(mem_info[0])
        stats['mem_info2'] = bytes2human(mem_info[1])
    except AccessDenied:
        stats['mem_info1'] = stats['mem_info2'] = "N/A"

    try:
        stats['cpu'] = process.get_cpu_percent(interval=interval)
    except AccessDenied:
        stats['cpu'] = "N/A"

    try:
        stats['mem'] = round(process.get_memory_percent(), 1)
    except AccessDenied:
        stats['mem'] = "N/A"

    try:
        cpu_times = process.get_cpu_times()
        ctime = timedelta(seconds=sum(cpu_times))
        ctime = "%s:%s.%s" % (ctime.seconds // 60 % 60,
                        str((ctime.seconds % 60)).zfill(2),
                        str(ctime.microseconds)[:2])
    except AccessDenied:
        ctime = "N/A"

    stats['ctime'] = ctime
    return stats


class RedirectIO(object):

    pipes_count = 2

    def __init__(self, loop, process, stdio=[]):
        self.loop = loop
        self.process = process
        self._emitter = EventEmitter(loop)

        self._stdio = []
        self._channels = []

        # create (channel, stdio) pairs
        for label in stdio[:self.pipes_count]:
            # io registered can any label, so it's easy to redirect
            # stderr to stdout, just use the same label.
            p = pyuv.Pipe(loop)
            io = pyuv.StdIO(stream=p, flags=pyuv.UV_CREATE_PIPE | \
                                            pyuv.UV_READABLE_PIPE | \
                                            pyuv.UV_WRITABLE_PIPE)
            setattr(p, 'label', label)
            self._channels.append(p)
            self._stdio.append(io)

        # create remaining pipes
        for _ in range(self.pipes_count - len(self._stdio)):
            self._stdio.append(pyuv.StdIO(flags=pyuv.UV_IGNORE))

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

    def stop(self, all_events=False):
        for p in self._channels:
            if not p.closed:
                p.close()

        if all_events:
            self._emitter.close()

    def _on_read(self, handle, data, error):
        if not data:
            return

        label = getattr(handle, 'label')
        msg = dict(event=label, name=self.process.name, pid=self.process.pid,
                data=data)
        self._emitter.publish(label, msg)


class RedirectStdin(object):
    """ redirect stdin allows multiple sender to write to same pipe """

    def __init__(self, loop, process):
        self.loop = loop
        self.process = process
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

    def stop(self, all_events=False):
        if not self.channel.closed:
            self.channel.close()

        if all_events:
            self._emitter.close()

    def _on_write(self, evtype, data):
        self.channel.write(data)

    def _on_writelines(self, evtype, data):
        self.channel.writelines(data)

    def _on_read(self, handle, data, error):
        if not data:
            return

        label = getattr(handle, 'label')
        msg = dict(event=label, name=self.process.name, pid=self.process.pid,
                data=data)
        self._emitter.publish(label, msg)


class Stream(RedirectStdin):
    """ create custom stdio """

    def __init__(self, loop, process, id):
        super(Stream, self).__init__(loop, process)
        self.id = id

    def start(self):
        super(Stream, self).start()
        self.channel.start_read(self._on_read)

    def subscribe(self, listener):
        self._emitter.subscribe('READ', listener)

    def unsubscribe(self, listener):
        self._emitter.unsubscribe('READ', listener)

    def _on_read(self, handle, data, error):
        if not data:
            return

        msg = dict(event='READ', name=self.process.name, pid=self.process.pid,
                data=data)
        self._emitter.publish('READ', msg)


class ProcessWatcher(object):
    """ object to retrieve process stats """

    def __init__(self, loop, process):
        self.loop = loop
        self.process = process
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
        try:
            self._last_info = self.refresh()
        except psutil.error.NoSuchProcess:
            self.stop()
            return

        # create the message
        msg = self._last_info.copy()
        msg.update({'pid': self.process.pid, 'os_pid': self.process.os_pid})

        # publish it
        self._emitter.publish("stat", msg)

    def refresh(self, interval=0):
        return get_process_stats(self.process._pprocess, interval=interval)

    def _start(self):
        if not self.active:
            self._timer = pyuv.Timer(self.loop)
            # start the timer to refresh the informations
            # 0.1 is the minimum interval to fetch cpu stats for this
            # process.
            self._timer.start(self._async_refresh, 0.1, 0.1)
            self._active = increment(self._active)


class ProcessConfig(object):
    """ object to maintain a process config """

    DEFAULT_PARAMS = {
            "args": [],
            "env": {},
            "uid": None,
            "gid": None,
            "cwd": None,
            "shell": False,
            "redirect_output": [],
            "redirect_input": False,
            "custom_streams": [],
            "custom_channels": []}

    def __init__(self, name, cmd, **settings):
        """
        Initialize the ProcessConfig object

        Args:

        - **name**: name of the process
        - **cmd**: program command, string)

        Settings:

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
        self.name = name
        self.cmd = cmd
        self.settings = settings

    def __str__(self):
        return "process: %s" % self.name

    def make_process(self, loop, pid, label, env=None, on_exit=None):
        """ create a Process object from the configuration

        Args:

        - **loop**: main pyuv loop instance that will maintain the process
        - **pid**: process id, generally given by the manager
        - **label**: the job label. Usually the process type.
          context. A context can be for example an application.
        - **on_exit**: callback called when the process exited.

        """

        params = {}
        for name, default in self.DEFAULT_PARAMS.items():
            params[name] = self.settings.get(name, default)

        os_env = self.settings.get('os_env', False)
        if os_env:
            env = params.get('env') or {}
            env.update(os.environ)
            params['env'] = env

        if env is not None:
            params['env'].update(env)

        params['on_exit_cb'] = on_exit
        return Process(loop, pid, label, self.cmd, **params)

    def __getitem__(self, key):
        if key == "name":
            return self.name

        if key == "cmd":
            return self.cmd

        return self.settings[key]

    def __setitem__(self, key, value):
        if key in ("name", "cmd"):
            setattr(self, key, value)
        else:
            self.settings[key] = value

    def __contains__(self, key):
        if key in ('name', 'cmd'):
            return True

        if key in self.settings:
            return True

        return False

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self):
        d = dict(name=self.name, cmd=self.cmd)
        d.update(self.settings)
        return d

    @classmethod
    def from_dict(cls, config):
        d = config.copy()
        try:
            name = d.pop('name')
            cmd = d.pop('cmd')
        except KeyError:
            raise ValueError("invalid config dict")

        return cls(name, cmd, **d)

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
    - **custom_streams**: list of additional streams that should be created
      and passed to process. This is a list of streams labels. They become
      available through :attr:`streams` attribute.
    - **custom_channels**: list of additional channels that should be passed to
      process.

    """


    def __init__(self, loop, pid, name, cmd, args=None, env=None, uid=None,
            gid=None, cwd=None, detach=False, shell=False,
            redirect_output=[], redirect_input=False, custom_streams=[],
            custom_channels=[], on_exit_cb=None):
        self.loop = loop
        self.pid = pid
        self.name = name
        self.cmd = cmd
        self.env = env or {}

        # set command
        self.cmd = bytestring(cmd)

        # remove args from the command
        args_ = shlex.split(self.cmd)
        if len(args_) == 1:
            self.args = []
        else:
            self.cmd = args_[0]
            self.args = args_[1:]

        # if args have been passed to the options then add them
        if args and args is not None:
            if isinstance(args, six.string_types):
                self.args.extend(shlex.split(bytestring(args)))
            else:
                self.args.extend([bytestring(arg) for arg in args])

        # replace envirnonnement variable in args
        # $PORT for example will become the given env variable.
        self.args = [substitute_env(arg, self.env) for arg in self.args]

        if shell:
            self.args = ['-c', self.cmd] + self.args
            self.cmd = "sh"

        self.uid = uid
        self.gid = gid
        if not IS_WINDOWS:
            if self.uid is not None:
                self.uid = check_uid(uid)

            if self.gid is not None:
                self.gid = check_gid(gid)

        self.cwd = cwd or getcwd()
        self.redirect_output = redirect_output
        self.redirect_input = redirect_input
        self.custom_streams = custom_streams
        self.custom_channels = custom_channels

        self._redirect_io = None
        self._redirect_in = None
        self.streams = {}
        self.detach = detach
        self.on_exit_cb = on_exit_cb
        self._process = None
        self._pprocess = None
        self._process_watcher = None
        self._os_pid = None
        self._info = None
        self.stopped = False
        self.graceful_time = 0
        self.graceful_timeout = None
        self.once = False

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
        # create custom streams,
        for label in self.custom_streams:
            stream = self.streams[label] = Stream(self.loop, self,
                len(self._stdio))
            self._stdio.append(stream.stdio)
        # create containers for custom channels.
        for channel in self.custom_channels:
            assert not channel.closed, \
                "Closed channel {0!r} can't be passed to process!" \
                    .format(channel)
            self._stdio.append(pyuv.StdIO(stream=channel,
                flags=pyuv.UV_INHERIT_STREAM))

    def spawn(self, once=False, graceful_timeout=None, env=None):
        """ spawn the process """

        self.once = once
        self.graceful_timeout = graceful_timeout

        if env is not None:
            self.env.update(env)

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
        self._os_pid = self._process.pid
        self._pprocess = psutil.Process(self._process.pid)

        # start to cycle the cpu stats so we can have an accurate number on
        # the first call of ``Process.stats``
        self.loop.queue_work(self._init_cpustats)


        # start redirecting IO
        self._redirect_io.start()

        if self._redirect_in is not None:
            self._redirect_in.start()

        for stream in self.streams.values():
            stream.start()


    @property
    def active(self):
        return self._process.active

    @property
    def closed(self):
        return self._process.closed

    @property
    def os_pid(self):
        """ return the process pid """
        if self._os_pid is None:
            self._os_pid = self._process.pid
        return self._os_pid

    @property
    def info(self):
        """ return the process info. If the process is monitored it
        return the last informations stored asynchronously by the watcher"""

        # info we have on this process
        if self._info is None:
            self._info = dict(pid=self.pid, name=self.name, cmd=self.cmd,
                    args=self.args, env=self.env, uid=self.uid, gid=self.gid,
                    os_pid=None, create_time=None, commited=self.once,
                    redirect_output=self.redirect_output,
                    redirect_input=self.redirect_input,
                    custom_streams=self.custom_streams)

        if (self._info.get('create_time') is None and
                self._pprocess is not None):

            self._info.update({'os_pid': self.os_pid,
                'create_time':self._pprocess.create_time})

        self._info['active'] = self._process.active
        return self._info

    @property
    def stats(self):
        if not self._pprocess:
            return

        return get_process_stats(self._pprocess, 0.0)

    @property
    def status(self):
        """ return the process status """
        if not self._pprocess:
            return
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
            self._process_watcher = ProcessWatcher(self.loop, self)

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

    def _init_cpustats(self):
        try:
            get_process_stats(self._pprocess, 0.1)
        except psutil.error.NoSuchProcess:
            # catch this error. It can can happen when the process is closing
            # very fast
            pass


    def _exit_cb(self, handle, exit_status, term_signal):
        if self._redirect_io is not None:
            self._redirect_io.stop(all_events=True)

        if self._redirect_in is not None:
            self._redirect_in.stop(all_events=True)

        for custom_io in self.streams.values():
            custom_io.stop(all_events=True)

        if self._process_watcher is not None:
            self._process_watcher.stop(all_events=True)

        self._running = False
        handle.close()

        # handle the exit callback
        if self.on_exit_cb is not None:
            self.on_exit_cb(self, exit_status, term_signal)
