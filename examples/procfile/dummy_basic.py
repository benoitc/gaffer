#!/usr/bin/env python
import os
import signal
import sys
import time


class Dummy(object):

    def __init__(self):
        # init signal handling
        signal.signal(signal.SIGQUIT, self.handle_quit)
        signal.signal(signal.SIGTERM, self.handle_quit)
        signal.signal(signal.SIGINT, self.handle_quit)
        signal.signal(signal.SIGCHLD, self.handle_chld)
        self.alive = True

    def handle_quit(self, *args):
        self.alive = False
        sys.exit(0)

    def handle_chld(self, *args):
        return

    def run(self):
        print("hello, dummy (pid: %s) is alive" % os.getpid())
        while self.alive:
            time.sleep(0.01)

if __name__ == "__main__":
    Dummy().run()
