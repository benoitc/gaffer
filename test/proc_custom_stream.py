#!/usr/bin/env python

from __future__ import print_function

import os
import sys

PY3 = sys.version_info[0] == 3

if PY3:
    stream = os.fdopen(3, 'wb+', buffering=0)
else:
    stream =  os.fdopen(3, "w+")

c = stream.readline()
stream.write(c)
stream.flush()
