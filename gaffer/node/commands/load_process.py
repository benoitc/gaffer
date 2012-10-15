# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import json
import os
import sys

from .base import Command

class AddProcess(Command):
    """\
        Load a process from a file
        ==========================

        Like the command ``add``, his command dynamically add a process
        to monitor in gafferd. Informations are gathered from a file or
        stdin if the name of file is ``-``. The file sent is a json file
        that have the same format described for the HTTP message.


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

            gafferctl load_process [--start] <file>

        Options
        +++++++

        - <name>: name of the process to create
        - <file>: path to a json file or stdin ``-``
        - --start: start the watcher immediately

        Example of usage::

            $ gafferctl load_process ../test.json
            $ cat ../test.json | gafferctl load_process -
            $ gafferctl load_process - < ../test.json

    """

    name = "load_process"

    options = [('', 'start', False, "start immediately the watcher")]
    args = ['name', 'cmd']

    def run(self, server, args, options):
        fname = args[0]

        if fname == "-":
            content = []
            while True:
                data = sys.stdin.readline()
                if not data:
                    break
                content.append(data)
            content = ''.join(content)
        else:
            if not os.path.isfile(fname):
                raise RuntimeError("%r not found")

            with open(fname, 'rb') as f:
                content = f.read()

        if isinstance(content, bytes):
            content = content.decode('utf-8')
        obj = json.loads(content)

        if not 'name' in obj or not 'cmd' in obj:
            raise RuntimeError('name or cmd properties are missing')

        name = obj.pop('name')
        cmd = obj.pop('cmd')

        obj['start'] = options.get('start', False)
        return server.add_process(name, cmd, **obj)

