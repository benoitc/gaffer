#!/usr/bin/env python

import signal
import sys
import time

class DummyProcess(object):

    QUIT_SIGNALS = (signal.SIGQUIT, signal.SIGTERM,)

    def __init__(self, testfile):
        self.alive = True
        self.testfile = testfile
        self.queue = []
        signal.signal(signal.SIGHUP, self.handle)
        signal.signal(signal.SIGQUIT, self.handle)
        signal.signal(signal.SIGTERM, self.handle)
        signal.signal(signal.SIGCHLD, self.handle_chld)
        signal.signal(signal.SIGWINCH, self.handle_winch)

    def _write(self, msg):
        with open(self.testfile, 'a+') as f:
            f.write(msg)
            f.flush()

    def handle(self, signum, frame):
        self.queue.append(signum)

    def handle_quit(self):
        self._write('QUIT')
        self.alive = False

    def handle_chld(self, *args):
        self._write('CHLD')

    def handle_winch(self, *args):
        return

    def handle_hup(self):
        self._write('HUP')

    def run(self):
        self._write('START')

        # write to std
        sys.stdout.write("hello out")
        sys.stdout.flush()
        sys.stderr.write("hello err")
        sys.stderr.flush()

        while self.alive:
            sig = None
            try:
                sig = self.queue.pop(0)
            except IndexError:
                pass

            if sig is not None:
                if sig in self.QUIT_SIGNALS:
                    self.handle_quit()
                elif sig == signal.SIGHUP:
                    self.handle_hup()

            time.sleep(0.001)

        self._write('STOP')

if __name__ == "__main__":
    dummy = DummyProcess(sys.argv[1])
    dummy.run()
    sys.exit(1)


