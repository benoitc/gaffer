#!/usr/bin/env python

from __future__ import print_function

import os

stream = os.fdopen(3, 'w+')
c = stream.readline()
print(c, file=stream)
stream.flush()
