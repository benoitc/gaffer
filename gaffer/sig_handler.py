# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import signal

import pyuv

if pyuv.__version__.startswith("0.8"):
    class Signal(object):

        def __init__(self, loop):
            self.loop = loop
            self._signal_uv = pyuv.Signal(loop)

        def start(self, cb, signum):
            self._signal_uv.start()
            signal.signal(signum, cb)

        def stop(self):
            self._signal_uv.stop()
else:
    Signal = pyuv.Signal


class SigHandler(object):
    """ A simple controller to handle signals """

    QUIT_SIGNALS = (signal.SIGQUIT, signal.SIGTERM, signal.SIGINT)

    def __init__(self):
        self.signal_handlers = []

    def start(self, loop, manager):
        self.loop = loop
        self.manager = manager

        # quit signals handling
        for sig in self.QUIT_SIGNALS:
            s = Signal(self.loop)
            s.start(self.handle_quit, sig)
            self.signal_handlers.append(s)

        # reload signal
        s = Signal(self.loop)
        s.start(self.handle_reload, signal.SIGHUP)
        self.signal_handlers.append(s)

        # chld
        s = Signal(self.loop)
        s.start(self.handle_chld, signal.SIGCHLD)
        self.signal_handlers.append(s)

    def stop(self):
        # stop all signals handlers
        for h in self.signal_handlers:
            h.stop()

    def restart(self):
        # we never restart, just return
        return

    def handle_quit(self, handle, *args):
        self.manager.stop()

    def handle_reload(self, handle, *args):
        self.manager.restart()

    def handle_chld(self, handle, *args):
        pass
