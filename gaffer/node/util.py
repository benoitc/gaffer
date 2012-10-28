# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os

if os.name == 'nt':
    def user_path():
        home = os.path.expanduser('~')
        return os.path.join(home, '_gafferd')
else:
    def user_path():
        return os.path.expanduser('~/.gafferd')
