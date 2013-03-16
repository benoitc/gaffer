# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import signal

import pyuv

class BaseSigHandler(object):
    """ A simple gaffer application to handle signals """

    QUIT_SIGNALS = (signal.SIGQUIT, signal.SIGTERM, signal.SIGINT)

    def __init__(self):
        self._sig_handlers = []

    def start(self, loop):
        self.loop = loop

         # quit signals handling
        for signum in self.QUIT_SIGNALS:
            self._start_signal(self.handle_quit, signum)

        # reload signal
        self._start_signal(self.handle_reload, signal.SIGHUP)

    def _start_signal(self, callback, signum):
        h = pyuv.Signal(self.loop)
        h.start(callback, signum)
        h.unref()
        self._sig_handlers.append(h)

    def stop(self):
        for h in self._sig_handlers:
            try:
                h.stop()
            except:
                pass

    def restart(self):
        # we never restart, just return
        return

    def handle_quit(self, handle, signum):
        raise NotImplementedError

    def handle_reload(self, handle, signum):
        raise NotImplementedError



class SigHandler(BaseSigHandler):
    """ A simple gaffer application to handle signals """

    def start(self, loop, manager):
        self.manager = manager
        super(SigHandler, self).start(loop)

    def handle_quit(self, handle, *args):
        self.manager.stop()

    def handle_reload(self, handle, *args):
        self.manager.restart()
