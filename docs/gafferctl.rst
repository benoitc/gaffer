.. _cli:

Gafferctl
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
