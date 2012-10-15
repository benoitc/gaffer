# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command

class ProcessIds(Command):
    """\
        Get launched process ids for a process template
        ===============================================

        This command return the list of launched process ids for a
        process template. Process ids are internals ids (for some reason
        we don't expose the system process ids)


        HTTP Message:
        -------------

        ::

            HTTP/1.1 GET /processes/<name>/_pids

        The response return::

            {
                "ok": true,
                "pids": [1],
            } 

        with an http status 200 if everything is ok.

        Properties:
        -----------

        - **name**: name of the process


        Command line:
        -------------

        ::

            gafferctl pids name

        Options
        +++++++

        - <name>: name of the process to start
    """

    name = "pids"

    args = ['name']

    def run(self, server, args, options):
        p = server.get_process(args[0])
        return p.pids

