#!/usr/bin/env python

import sys
import signal
import time

class CrashProcess(object):

    def __init__(self):
        self.alive = True

    def run(self):
        while self.alive:
            time.sleep(0.1)
            break

if __name__ == "__main__":
    c = CrashProcess()
    c.run()
    sys.exit(1)

