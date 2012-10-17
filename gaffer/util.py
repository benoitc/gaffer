# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import grp
import os
import pwd
import resource
import socket
import time

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

MAXFD = 1024
if hasattr(os, "devnull"):
    REDIRECT_TO = os.devnull
else:
    REDIRECT_TO = "/dev/null"

try:
    from setproctitle import setproctitle
    def setproctitle_(title):
        setproctitle(title)
except ImportError:
    def setproctitle(_title):
        return

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
        raise ValueError("%r isn't a valid user val" % val)


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

def parse_address(netloc, default_port=8000):
    if netloc.startswith("unix:"):
        return netloc.split("unix:")[1]

    # get host
    if '[' in netloc and ']' in netloc:
        host = netloc.split(']')[0][1:].lower()
    elif ':' in netloc:
        host = netloc.split(':')[0].lower()
    elif netloc == "":
        host = "0.0.0.0"
    else:
        host = netloc.lower()

    #get port
    netloc = netloc.split(']')[-1]
    if ":" in netloc:
        port = netloc.split(':', 1)[1]
        if not port.isdigit():
            raise RuntimeError("%r is not a valid port number." % port)
        port = int(port)
    else:
        port = default_port
    return (host, port)

def is_ipv6(addr):
    try:
        socket.inet_pton(socket.AF_INET6, addr)
    except socket.error: # not a valid address
        return False
    return True



def get_maxfd():
    maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if (maxfd == resource.RLIM_INFINITY):
        maxfd = MAXFD
    return maxfd

try:
    from os import closerange
except ImportError:
    def closerange(fd_low, fd_high):    # NOQA
        # Iterate through and close all file descriptors.
        for fd in range(fd_low, fd_high):
            try:
                os.close(fd)
            except OSError:    # ERROR, fd wasn't open to begin with (ignored)
                pass


# http://www.svbug.com/documentation/comp.unix.programmer-FAQ/faq_2.html#SEC16
def daemonize():
    """Standard daemonization of a process.
    """
    #if not 'CIRCUS_PID' in os.environ:
    if os.fork():
        os._exit(0)
    os.setsid()

    if os.fork():
        os._exit(0)

    os.umask(0)
    maxfd = get_maxfd()
    closerange(0, maxfd)

    os.open(REDIRECT_TO, os.O_RDWR)
    os.dup2(0, 1)
    os.dup2(0, 2)


def nanotime(s=None):
    """ convert seconds to nanoseconds. If s is None, current time is
    returned """
    if s is not None:
        return int(s) * 1000000000
    return time.time() * 1000000000

def from_nanotime(n):
    """ convert from nanotime to seconds """
    return n / 1.0e9
