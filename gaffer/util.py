# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import pwd

import six

if six.PY3:
    def bytestring(s):
        return s
else:
    def bytestring(s):
        if isinstance(s, unicode):
            return s.encode('utf-8')
        return s

_SYMBOLS = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')

def getcwd():
    """Returns current path, try to use PWD env first"""
    try:
        a = os.stat(os.environ['PWD'])
        b = os.stat(os.getcwd())
        if a.ino == b.ino and a.dev == b.dev:
            working_dir = os.environ['PWD']
        else:
            working_dir = os.getcwd()
    except:
        working_dir = os.getcwd()
    return working_dir

def check_uid(val):
    """Return an uid, given a user value.
    If the value is an integer, make sure it's an existing uid.

    If the user value is unknown, raises a ValueError.
    """
    if isinstance(val, int):
        try:
            pwd.getpwuid(val)
            return val
        except (KeyError, OverflowError):
            raise ValueError("%r isn't a valid user id" % val)

    if not isinstance(val, str):
        raise TypeError(val)

    try:
        return pwd.getpwnam(val).pw_uid
    except KeyError:
        raise ValueError("%r isn't a valid user val" % name)


def check_gid(val):
    """Return a gid, given a group value

    If the group value is unknown, raises a ValueError.
    """
    if isinstance(val, int):
        try:
            grp.getgrgid(val)
            return val
        except (KeyError, OverflowError):
            raise ValueError("No such group: %r" % val)

    if not isinstance(val, str):
        raise TypeError(val)
    try:
        return grp.getgrnam(val).gr_gid
    except KeyError:
        raise ValueError("No such group: %r" % val)


def bytes2human(n):
    """Translates bytes into a human repr.
    """
    if not isinstance(n, int):
        raise TypeError(n)

    prefix = {}
    for i, s in enumerate(_SYMBOLS):
        prefix[s] = 1 << (i + 1) * 10

    for s in reversed(_SYMBOLS):
        if n >= prefix[s]:
            value = int(float(n) / prefix[s])
            return '%s%s' % (value, s)
    return "%sB" % n
