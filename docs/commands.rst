.. _cli:

==============
Console tools
==============

gafferp
=======

**gafferp** is a manager for Procfile-based applications similar to
foreman but using the :doc:`gaffer framework <processframework>`. It is
running your application directly using a Procfile or export it to a
gafferd configuration file or simply to a JSON file that you could send
to gafferd using the :doc:`HTTP api <http>`.

For example using the following **Procfile**::

    dummy: python -u dummy_basic.py
    dummy1: python -u dummy_basic.py


You can launch all the programs in this procfile using the following
command line::

    $ gafferp start

.. image:: _static/gafferp.png

Command line usage
++++++++++++++++++

::

    $ gafferp
    usage: gafferp [options] command [args]

    manage Procfiles applications.

    optional arguments:
      -h, --help            show this help message and exit
      -c CONCURRENCY, --concurrency CONCURRENCY
                            Specify the number of each process type to run. The
                            value passed in should be in the format
                            process=num,process=num
      -e ENVS [ENVS ...], --env ENVS [ENVS ...]
                            Specify one or more .env files to load
      -f FILE, --procfile FILE
                            Specify an alternate Procfile to load
      -d ROOT, --directory ROOT
                            Specify an alternate application root. This defaults
                            to the directory containing the Procfile
      --version             show program's version number and exit

    Commands:

        start [name]   	start a process
        run <cmd>      	run one-off commands
        export [format]	export


gafferd
=======

Gafferd is a server able to launch and manage processes. It can be
controlled via the :doc:`http` .

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

    [webhooks]
    ;create = http://some/url
    ;proc.dummy.spawn = http://some/otherurl


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
    ; redirect_input  = true
    ; graceful_timeout = 30

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
in the httpclient module or by reading the doc here and passing your own
message to the gaffer node. All messages are encoded in JSON.

.. image:: _static/gaffer_watch.png

Usage
+++++

::

    $ gafferctl help
    usage: gafferctl [--version] [--connect=<endpoint>]
                     [--certfile] [--keyfile]
                     [--help]
                     <command> [<args>]

    Commands:
        add           	Increment the number of OS processes
        add_process   	Add a process to monitor
        del_process   	Get a process description
        get_process   	Fetch a process template
        help          	Get help on a command
        kill          	Send a signal to a process
        load_process  	Load a process from a file
        numprocesses  	Number of processes that should be launched
        pids          	Get launched process ids for a process template
        processes     	Add a process to monitor
        running       	Number of running processes for this process description
        start         	Start a process
        status        	Return the status of a process
        stop          	Stop a process
        sub           	Decrement the number of OS processes
        update_process	Update a process description


gafferctl commands
-------------------

- **status**: :doc:`commands/status`
- **processes**: :doc:`commands/processes`
- **sub**: :doc:`commands/sub`
- **add_process**: :doc:`commands/add_process`
- **get_process**: :doc:`commands/get_process`
- **stop**: :doc:`commands/stop`
- **running**: :doc:`commands/running`
- **load_process**: :doc:`commands/load_process`
- **watch**: :doc:`commands/watch`
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
