Overview
========

Gaffer is a set of Python modules and tools to easily maintain and
interract with your processes.

Depending on your needs you ca simply use the gaffer tools (eventually
extend them) or embed the gaffer possibilities in your own apps.

Design
------

Gaffer is internally based on an event loop using the `libuv <https://github.com/joyent/libuv/>`_ from Joyent via the `pyuv binding <https://pyuv.readthedocs.org>`_

All gaffer events are added to the loop and processes asynchrnously wich
make it pretty performant to handle multiple process and their control.

At the lowest level you will find the manager. A manager is responsible
of maintaining process alive and manage actions on them:

- increase/decrease the number of processes / process template
- start/stop processes
- add/remove process templates to manage


A process template describe the way a process will be launched and how
many OS processes you want to handle for this template. This number can
be changed dynamically. Current propertiers of this templates are:

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
- **os_env**: boolean, pass the os environment to the program
- **numprocesses**: int the number of OS processes to launch for
  this description
- **flapping**: a FlappingInfo instance or, if flapping detection
  should be used. flapping parameters are:

  - **attempts**: maximum number of attempts before we stop the
    process and set it to retry later
  - **window**: period in which we are testing the number of
    retry
  - **retry_in**: seconds, the time after we restart the process
    and try to spawn them
  - **max_retry**: maximum number of retry before we give up
    and stop the process.
- **redirect_output**: list of io to redict (max 2) this is a list of custom
  labels to use for the redirection. Ex: ["a", "b"] will
  redirect stdoutt & stderr and stdout events will be labeled "a"
- **redirect_input**: Boolean (False is the default). Set it if
  you want to be able to write to stdin.


The manager is also responsible of starting and stopping contollers (e
better wording need to be found) or rather gaffer applications that you add
add to he manager to react on different events. A controller is
responsible of fetching infos from the manager and handling actions.

Running a controller is done like this::

    # initialize the controller with the default loop
    loop = pyuv.Loop.default_loop()
    manager = Manager(loop=loop)

    # start the controller
    manager.start(controllers=[HttpHandler])

    .... # do smth

    manager.stop() # stop the controlller
    manager.run() # run the event loop


For now only 1 HTTP controller is proposed and allows you to interract
with gaffer via HTTP.  It is used by the gafferd server which is abble
for now to load process templates via an ini files and maintain an HTTP
endoint which can be configured to be accessible on multiples interfaces
and transports (tcp & unix sockets) .

Building your own controller is easy, basically a contoller has the
following structure::

    class Mycontroller(object):

        def __init__(self):
            # do inti

        def start(self, loop, manager):
            # this method is call by the manager to start the controller

        def stop(self):
            # method called when the manager stop

        def restart(self):
            # methhod called when the manager restart

You can use this structure for anything you want, even add an app to the
loop.

To help you in your work a :doc:`pyuv implementation <tornado_pyuv>` of
tornado is integrated and a powerfull :doc:`events <events>` modules
will allows you to manage PUB/SUB events (or anything evented) inside
your app. An EventEmitter is a threadsafe class to manage subscriber and
publisher of events. It is interrnally used to broadcast processes and
manager events.


Watch stats
-----------

Stats of a process ca, be monitored continuously (there is a refresh
interval of 0.1s to fetch CPU informations) using the following
mettod::

    manager.monitor(<nameorid>, <listener>)

Where `<nameorid>` is the name of the process template. In this case
the statistics of all the the OS processes using this template will be
emitted. Stats events are collected in the listener callback.

Callback signature: ``callback(evtype, msg)``.

**evtype** is always "STATS" here and **msg** is a dict::

    {
        "mem_info1: int,
        "mem_info2: int,
        "cpu": int,
        "mem": int,
        "ctime": int,
        "pid": int,
        "username": str,
        "nicce": int,
        "cmdline": str,
        "children": [{ stat dict, ... }]
    }

To unmonitor the process in your app run::

    manager.unmonitor(<nameorid>, <listener>)

.. note::

    Internally a monitor subscribe you to an EventEmitter. A timer is
    running until there are subscribers to the process stats events.

Of course you can monitor directly to a process using the internal pid::

    process = manager.running[pid]
    process.monitor(<listener>)

    ...

    process.unmonitor(<listener>)

IO Events
---------

Subscribe to stdout/stderr process stream
+++++++++++++++++++++++++++++++++++++++++

You can subscribe to stdout/stderr process stream and even write to
stdin if you want.

To be abble to receive the stdour/stderr streas in your application,
you need to create a process with the *redirect_output* setting::


    manager.add_process("nameofprocestemplate", cmd,
        redirect_output["stdout", "stderr"])


.. note::

    Name of outputs can be anything, only the order count so if you want
    to name *stdout* as *a* just replace *stdout* by *a* in the
    declaration.

    If you don't want to receive *stderr*, just omit it in the list.
    Alos if you want to redirect stderr to stdout just use the same
    name.


Then for example, to monitor the stdout output do::

    process.monitor_io("stdout", somecallback)

Callback signature: ``callback(evtype, msg)``.

And to unmonitor::

    process.unmonitor_io("stdout", somecallback)

.. note::

    To subscribe to all process streams replace the stream name by
    `'.'`` .


Write to STDIN
++++++++++++++

Writing to stdin is pretty easy. Just do::

    process.write("somedata")

or to send multiple lines::

    process.writelines(["line", "line"])

You can write lines from multiple publisher and multiple publishers can
write at the same time. This method is threadsafe.


HTTP API
--------

See the :doc:`HTTP api description <http>` for more informations.

Tools
-----

Gaffer propose different tools (and more will come soon) to manage yoir
process without have to code. It can be used like `supervisor
<http://supervisord.org/>`_, `god <http://godrb.com/>`_, `runit
<http://smarden.org/runit/>`_  or other tools around. Speaking of runit
a similar controlling will be available in 0.2 .

See the :doc:`console tools <commands>` for more informations.
