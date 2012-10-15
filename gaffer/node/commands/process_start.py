# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command

class ProcessStart(Command):
    """\
        Start a process
        ===============

        This command dynamically start a process.


        HTTP Message:
        -------------

        ::

            HTTP/1.1 POST /processes/<name>/_start

        The response return {"ok": true} with an http status 200 if
        everything is ok.

        Properties:
        -----------

        - **name**: name of the process


        Command line:
        -------------

        ::

            gafferctl start name

        Options
        +++++++

        - <name>: name of the process to start
    """

    name = "start"

    args = ['name']

    def run(self, server, args, options):
        p = server.get_process(args[0])
        return p.start()
