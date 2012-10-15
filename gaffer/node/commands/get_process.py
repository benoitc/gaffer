# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json

from .base import Command, prettify

class GetProcess(Command):
    """\
        Fetch a process template
        ========================

        This command stop a process and remove it from the monitored
        process.

        HTTP Message:
        -------------

        ::

            HTTP/1.1 GET /processes/<name>

        The response return::

            {
                "name": "somename",
                "cmd": "cmd to execute":
                "args": [],
                "env": {}
                "uid": int or "",
                "gid": int or "",
                "cwd": "working dir",
                "detach: False,
                "shell": False,
                "os_env": False,
                "numprocesses": 1
            }


        with an http status 200 if everything is ok.


        Properties:
        -----------

        - **name**: name of the process
        - **cmd**: program command, string)
        - **args**: the arguments for the command to run. Can be a list or
          a string. If **args** is  a string, it's splitted using
          :func:`shlex.split`. Defaults to None.
        - **env**: a mapping containing the environment variables the command
          will run with. Optional
        - **uid**: int or str, user id
        - **gid**: int or st, user group id,
        - **cwd**: working dir
        - **detach**: the process is launched but won't be monitored and
          won't exit when the manager is stopped.
        - **shell**: boolean, run the script in a shell. (UNIX
          only),
        - os_env: boolean, pass the os environment to the program
        - numprocesses: int the number of OS processes to launch for
          this description


        Command line:
        -------------

        ::

            gafferctl get_process name

        Options
        +++++++

        - <name>: name of the process details to fetch

    """

    name = "get_process"
    args = ['name']

    def run(self, server, args, options):
        p = server.get_process(*args)
        return prettify(json.dumps(p.process))

