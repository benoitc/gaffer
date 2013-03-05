#!/usr/bin/env python
from __future__ import print_function

import os
import signal
import sys
import time

PY3 = sys.version_info[0] == 3

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
        i = 0
        try:
            if PY3:
                stream = os.fdopen(3, 'wb+', buffering=0)
            else:
                stream =  os.fdopen(3, "w+")

            while self.alive:
                c = stream.readline()
                if PY3:
                    stream.write(c)
                else:
                    print(c, file=stream)

                stream.flush()
                time.sleep(0.1)
        except Exception as e:
            sys.stdout.write(str(e))
            sys.stdout.flush()

if __name__ == "__main__":
    Echo().run()
