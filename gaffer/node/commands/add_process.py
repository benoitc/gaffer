# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command

class AddProcess(Command):
    """\
        Add a process to monitor
        ========================

        This command dynamically add a process to monitor in gafferd.


        HTTP Message:
        -------------

        ::

            HTTP/1.1 POST /processes
            Content-Type: application/json
            Accept: application/json

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

        The response return {"ok": true} with an http status 200 if
        everything is ok.

        It return a 409 error in case of a conflict (a process with
        this name has already been created.

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

            gafferctl add_process [--start] name cmd

        Options
        +++++++

        - <name>: name of the process to create
        - <cmd>: full command line to execute in a process
        - --start: start the watcher immediately
    """

    name = "add_process"

    options = [('', 'start', False, "start immediately the watcher")]
    args = ['name', 'cmd']

    def run(self, server, args, options):
        return server.add_process(*args, **options)
