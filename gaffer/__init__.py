# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

version_info = (0, 5, 0)
__version__ = ".".join(map(str, version_info))

from gaffer.manager import Manager
from gaffer.gafferd.plugins import Plugin
