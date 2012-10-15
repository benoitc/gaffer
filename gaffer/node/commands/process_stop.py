# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command

class ProcessStop(Command):
    """\
        Stop a process
        ===============

        This command dynamically stop a process.


        HTTP Message:
        -------------

        ::

            HTTP/1.1 POST /processes/<name>/_stop

        The response return {"ok": true} with an http status 200 if
        everything is ok.

        Properties:
        -----------

        - **name**: name of the process


        Command line:
        -------------

        ::

            gafferctl stop name

        Options
        +++++++

        - <name>: name of the process to start
    """

    name = "stop"

    args = ['name']

    def run(self, server, args, options):
        p = server.get_process(args[0])
        return p.stop()

