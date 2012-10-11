# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import signal

import pyuv

class SigHandler(object):
    """ A simple controller to handle signals """

    QUIT_SIGNALS = (signal.SIGQUIT, signal.SIGTERM, signal.SIGINT)

    def __init__(self):
        self._sig_handler = None

    def start(self, loop, manager):
        self.loop = loop
        self.manager = manager

        need_unref = False
        if hasattr(pyuv, "SignalChecker"):
            self._sig_handler = pyuv.SignalChecker(self.loop)
        else:
            self._sig_handler = pyuv.Signal(self.loop)
            need_unref = True

        # quit signals handling
        for signum in self.QUIT_SIGNALS:
            signal.signal(signum, self.handle_quit)

        # reload signal
        signal.signal(signal.SIGHUP, self.handle_reload)

        # chld
        signal.signal(signal.SIGCHLD, self.handle_chld)

        self._sig_handler.start()
        if need_unref:
            self._sig_handler.unref()

    def stop(self):
        try:
            self._sig_handler.stop()
        except:
            pass

    def restart(self):
        # we never restart, just return
        return

    def handle_quit(self, handle, *args):
        self.manager.stop()

    def handle_reload(self, handle, *args):
        self.manager.restart()

    def handle_chld(self, handle, *args):
        pass
