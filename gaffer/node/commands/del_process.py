# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command

class DelProcess(Command):
    """\
        Get a process description
        =========================

        This command stop a process and remove it from the monitored
        process.

        HTTP Message:
        -------------

        ::

            HTTP/1.1 DELETE /processes/<name>


        The response return {"ok": true} with an http status 200 if
        everything is ok.

        Properties:
        -----------

        - **name**: name of the process

        Command line:
        -------------

        ::

            gafferctl del_process name


        Options
        +++++++

        - <name>: name of the process to remove
    """

    name = "del_process"
    args  = ['name']

    def run(self, server, args, options):
        return server.remove_process(args[0])
