#!/usr/bin/env python
import os
import signal
import sys
import time


class Echo(object):

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
        while self.alive:
            c = sys.stdin.readline()
            sys.stdout.write(c)
            sys.stdout.flush()
            time.sleep(0.1)
if __name__ == "__main__":
    Echo().run()
