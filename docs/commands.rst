.. _cli:

==============
Console tools
==============

gafferd
=======

Gafferd is a server able to launch and manage processes. It can be
controlled via the :doc:<http> .

Usage
+++++

::

    $ gafferd --help
    usage: gafferd [-h] [--daemon] [--pidfile PIDFILE] config

    Run some watchers.

    positional arguments:
      config             configuration file

    optional arguments:
      -h, --help         show this help message and exit
      --daemon           Start gaffer in the background
      --pidfile PIDFILE

Config file example
+++++++++++++++++++

::

    [gaffer]
    http_endpoints = public

    [endpoint:public]
    bind = 127.0.0.1:5000
    ;certfile=
    ;keyfile=

    [process:dummy]
    cmd = ./dummy.py
    ;cwd = .
    ;uid =
    ;gid =
    ;detach = false
    ;shell = false
    ; flapping format: attempts=2, window=1., retry_in=7., max_retry=5
    ;flapping = 2, 1., 7., 5
    numprocesses = 1
    redirect_output = stdout, stderr


    [process:echo]
    cmd = ./echo.py
    numprocesses = 1
    redirect_output = stdout, stderr
    redirect_input  = true

gafferctl
=========

*gafferctl* can be used to run any command listed below. For
example, you can get a list of all processes templates::

    $ gafferctl processes


*gafferctl* is an HTTP client able to connect to a UNIX pipe or a tcp
connection and connect to a gaffer node. It is using the httpclient
module to do it.

You can create your own client either by using the client API provided
in the httpclient module or by reading the doc here an dpassing your own
message to the gaffer node. All messages are encoded in JSON.


gafferctl commands
-------------------

- **status**: :doc:`commands/status`
- **processes**: :doc:`commands/processes`
- **sub**: :doc:`commands/sub`
- **add_process**: :doc:`commands/add_process`
- **get_process**: :doc:`commands/get_process`
- **stop**: :doc:`commands/stop`
- **running**: :doc:`commands/running`
- **start**: :doc:`commands/start`
- **add**: :doc:`commands/add`
- **update_process**: :doc:`commands/update_process`
- **kill**: :doc:`commands/kill`
- **numprocesses**: :doc:`commands/numprocesses`
- **del_process**: :doc:`commands/del_process`
- **pids**: :doc:`commands/pids`

.. toctree::
   :hidden:
   :glob:

   commands/*
