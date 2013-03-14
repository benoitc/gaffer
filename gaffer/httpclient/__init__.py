# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

"""
Gaffer provides you a simple Client to control a gaffer node via HTTP.

Example of usage::

    import pyuv

    from gaffer.httpclient import Server

    # initialize a loop
    loop = pyuv.Loop.default_loop()

    s = Server("http://localhost:5000", loop=loop)

    # add a process without starting it
    process = s.add_process("dummy", "/some/path/to/dummy/script", start=False)

    # start a process
    process.start()

    # increase the number of process by 2 (so 3 will run)
    process.add(2)

    # stop all processes
    process.stop()

    loop.run()

"""

from .base import (GafferNotFound, GafferConflict, GafferUnauthorized,
        GafferForbidden, HTTPClient, BaseClient)
from .process import Process
from .job import Job
from .server import Server
from .websocket import WebSocket, GafferCommand, Channel
