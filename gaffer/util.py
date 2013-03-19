# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import platform
import signal
import socket
import ssl
import string
import sys
import time

IS_WINDOWS = platform.system() == 'Windows'
if not IS_WINDOWS:
    import grp
    import pwd
    import resource
else:
    grp = None
    pwd = None
    resource = None

import six
from tornado import netutil

DEFAULT_CA_CERTS = os.path.dirname(__file__) + '/cacert.pem'

if six.PY3:
    def bytestring(s):
        return s

    def ord_(c):
        return c

    import urllib.parse
    urlparse = urllib.parse.urlparse
    quote = urllib.parse.quote
    quote_plus = urllib.parse.quote_plus
    unquote = urllib.parse.unquote
    urlencode = urllib.parse.urlencode
else:
    def bytestring(s):
        if isinstance(s, unicode):
            return s.encode('utf-8')
        return s

    def ord_(c):
        return ord(c)

    import urlparse
    urlparse = urlparse.urlparse

    import urllib
    quote = urllib.quote
    quote_plus = urllib.quote_plus
    unquote = urllib.unquote
    urlencode = urllib.urlencode


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
    if isinstance(val, six.integer_types):
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
    if not isinstance(n, six.integer_types):
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

def bind_sockets(addr, backlog=128, allows_unix_socket=False):
    # initialize the socket
    addr = parse_address(addr)
    if isinstance(addr, six.string_types):
        if not allows_unix_socket:
            raise RuntimeError("unix addresses aren't supported")

        sock = netutil.bind_unix_socket(addr)
    elif is_ipv6(addr[0]):
        sock = netutil.bind_sockets(addr[1], address=addr[0],
                family=socket.AF_INET6, backlog=backlog)
    else:
        sock = netutil.bind_sockets(addr[1], backlog=backlog)
    return sock

def hostname():
    return socket.getfqdn(socket.gethostname())


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

    if IS_WINDOWS:
        raise RuntimeError('Daemonizing is not supported on Windows.')

    if os.fork():
        os._exit(0)
    os.setsid()

    if os.fork():
        os._exit(0)

    os.umask(0)
    maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if (maxfd == resource.RLIM_INFINITY):
        maxfd = MAXFD
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

def substitute_env(s, env):
    return string.Template(s).substitute(env)

def parse_signal_value(sig):
    if sig is None:
        raise ValueError("invalid signal")

    # value passed is a string
    if isinstance(sig, six.string_types):
        if sig.isdigit():
            # if number in the string, try to parse it
            try:
                return int(sig)
            except ValueError:
                raise ValueError("invalid signal")

        # else try to get the signal number from its name
        signame = sig.upper()
        if not signame.startswith('SIG'):
            signame = "SIG%s" % signame
        try:
            signum = getattr(signal, signame)
        except AttributeError:
            raise ValueError("invalid signal name")
        return signum

    # signal is a number, just return it
    return sig

def parse_job_name(name, default='default'):
    if "." in name:
        appname, name = name.split(".", 1)
    elif "/" in name:
        appname, name = name.split("/", 1)
    else:
        appname = default

    return appname, name

def is_ssl(url):
    return url.startswith("https") or url.startswith("wss")

def parse_ssl_options(client_options):
    ssl_options = {}
    if client_options.get('validate_cert'):
        ssl_options["cert_reqs"] = ssl.CERT_REQUIRED
    if client_options.get('ca_certs') is not None:
        ssl_options["ca_certs"] = client_options['ca_certs']
    else:
        ssl_options["ca_certs"] = DEFAULT_CA_CERTS
    if client_options.get('client_key') is not None:
        ssl_options["keyfile"] = client_options['client_key']
    if client_options.get('client_cert') is not None:
        ssl_options["certfile"] = client_options['client_cert']


    # disable SSLv2
    # http://blog.ivanristic.com/2011/09/ssl-survey-protocol-support.html
    if sys.version_info >= (2, 7):
        ssl_options["ciphers"] = "DEFAULT:!SSLv2"
    else:
        # This is really only necessary for pre-1.0 versions
        # of openssl, but python 2.6 doesn't expose version
        # information.
        ssl_options["ssl_version"] = ssl.PROTOCOL_SSLv3
    return ssl_options

