import os
from gaffer.commands import get_commands

_HEADER = """\
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
