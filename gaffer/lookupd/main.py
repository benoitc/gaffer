# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

"""
usage: gaffer_lookupd [--version] [-v] [--daemon] [--pidfile=PIDFILE]
                      [--bind=ADDRESS] [--backlog=BACKLOG]
                      [--certfile=CERTFILE] [--keyfile=KEYFILE]

Options

    -h --help                   show this help message and exit
    --version                   show version and exit
    -v                          verbose mode
    --daemon                    Start gaffer in daemon mode
    --pidfile=PIDFILE
    --bind=ADDRESS              default HTTP binding [default: 0.0.0.0:5010]
    --certfile=CERTFILE         SSL certificate file
    --keyfile=KEYFILE           SSL key file
    --backlog=BACKLOG           default backlog [default: 128].
"""
import os
import socket
import sys

# patch tornado IOLoop
from ..tornado_pyuv import IOLoop, install
install()

import pyuv
import six

from .. import __version__
from ..docopt import docopt
from ..loop import patch_loop
from ..pidfile import Pidfile
from ..sig_handler import BaseSigHandler
from ..util import bind_sockets, daemonize, setproctitle_

from .http import http_server


class LookupSigHandler(BaseSigHandler):

    def __init__(self, server):
        self.server = server
        super(LookupSigHandler, self).__init__()

    def handle_quit(self, handle, *args):
        self.server.stop()

    def handle_reload(self, handle, *args):
        # HUP is ignored
        return


class LookupServer(object):

    def __init__(self, args, loop=None):
        self.loop = patch_loop(loop or pyuv.Loop.default_loop())
        self.io_loop = IOLoop(_loop=self.loop)
        self.args = args

        # initialize the signal handler
        self._sig_handler = LookupSigHandler(self)

        # get arguments
        self.addr = args["--bind"]
        if args["--backlog"]:
            try:
                self.backlog = int(args["--backlog"])
            except ValueError:
                raise RuntimeError("backlog should be an integer")
        else:
            self.backlog = 128

        if (args["--certfile"] is not None and
                self.args["--keyfile"] is not None):
            self.ssl_options = {'certfile': args["--certfile"],
                                'keyfile':args["--keyfile"]}
        else:
            self.ssl_options = None

        self.started = False

    def start(self):
        if self.started:
            return

        # start the sighandler
        self._sig_handler.start(self.loop)

        # initialize the server
        listener = bind_sockets(self.addr, backlog=self.backlog,
                allows_unix_socket=True)
        self.hserver = http_server(self.io_loop, listener,
                ssl_options=self.ssl_options)
        self.hserver.start()

        self.started = True

    def run(self):
        if not self.started:
            self.start()

        self.loop.run()

    def stop(self):
        self.hserver.stop()
        self.io_loop.close(True)
        self.started = False

def main():
    args = docopt(__doc__, version=__version__)
    if args["--daemon"]:
        daemonize()
    setproctitle_("gaffer_lookupd")

    # create pidfile
    pidfile = None
    if args["--pidfile"]:
        pidfile = Pidfile(args["--pidfile"])

        try:
            pidfile.create(os.getpid())
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

    try:
        s = LookupServer(args)
        s.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(str(e))
        sys.exit(1)
    finally:
        if pidfile is not None:
            pidfile.unlink()

    sys.exit(0)

if __name__ == "__main__":
    main()
