# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import pyuv

class Manager(object):

    def __init__(self, loop=None):

        self.loop = loop or pyuv.Loop.default_loop()


