import os
from gaffer.node.commands import get_commands

_HEADER = """\
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
    usage: gafferd [-h] [-v] [-vv] [--daemon] [--pidfile PIDFILE] [--bind BIND]
                   [--certfile CERTFILE] [--keyfile KEYFILE] [--backlog BACKLOG]
                   [config]

    Run some watchers.

    positional arguments:
      config               configuration file

    optional arguments:
      -h, --help           show this help message and exit
      -v                   verbose mode
      -vv                  like verbose mode but output stream too
      --daemon             Start gaffer in the background
      --pidfile PIDFILE
      --bind BIND          default HTTP binding
      --certfile CERTFILE  SSL certificate file for the default binding
      --keyfile KEYFILE    SSL key file for the default binding
      --backlog BACKLOG    default backlog

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


"""


def generate_commands(app):
    path = os.path.join(app.srcdir, "commands")
    ext = app.config['source_suffix']
    if not os.path.exists(path):
        os.makedirs(path)

    tocname = os.path.join(app.srcdir, "commands%s" % ext)

    with open(tocname, "w") as toc:
        toc.write(_HEADER)
        toc.write("gafferctl commands\n")
        toc.write("-------------------\n\n")

        commands = get_commands()
        for name, cmd in commands.items():
            toc.write("- **%s**: :doc:`commands/%s`\n" % (name, name))

            # write the command file
            refline = ".. _%s:" % name
            fname = os.path.join(path, "%s%s" % (name, ext))
            with open(fname, "w") as f:
                f.write("\n".join([refline, "\n", cmd.desc, ""]))

        toc.write("\n")
        toc.write(".. toctree::\n")
        toc.write("   :hidden:\n")
        toc.write("   :glob:\n\n")
        toc.write("   commands/*\n")

def setup(app):
    app.connect('builder-inited', generate_commands)
