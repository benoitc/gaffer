.. _watch:


Watch changes in gaffer
=======================

This command allows you to watch changes n a locla or remote
gaffer node.


.. image:: ../_static/gaffer_watch.png


HTTP Message
------------

::

    HTTP/1.1 GET /watch/<p1>[/<p2>/<p3>]

It accepts the following query parameters:

- **feed** : continuous, longpoll, eventsource
- **heartbeat**: true or seconds, send an empty line each sec
  (if true 60)

Ex::

    $ curl "http://127.0.0.1:5000/watch?feed=eventsource&heartbeat=true"
    event: exit
    data: {"os_pid": 3492, "exit_status": 0, "pid": 1, "event": "exit", "term_signal": 0, "name": "priority0"}
    event: exit
    event: proc.priority0.exit
    ...


The path passed can be any accepted patterns by the manager :

- ``create`` will become ``http://127.0.0.1:5000/watch/create``
- ``proc.dummy`` will become ``http://127.0.0.1:5000/watch/proc/dummy``

...

Accepted genetic patterns
+++++++++++++++++++++++++

=====================  =========================================
Patterns               Description
=====================  =========================================
create                 to follow all templates creattion
start                  start all processes in a tpl
stop                   all processes in a tpl are stopped
restart                restart all processes in a tpl
update                 update a tpl (can happen on add/sub)
delete                 a template has been removed
spawn                  a new process is spawned
reap                   a process is reaped
exit                   a process exited
stop_pid               a process has been stopped
proc.<name>.start      process template with <name> start
proc.<name>.stop       process template with <name> stop
proc.<name>.stop_pid   a process from <name> is stopped
proc.<name>.spawn      a process from <name> is spawned
proc.<name>.exit       a process from <name> exited
proc.<name>.reap       a process from <name> has been reaped
=====================  =========================================


Command line:
-------------

::

    gafferctl watch <p1>[.<p2>.<p3>] 

.. note::

    <p1[2,3]> are the parts of the parttern separrated with a
    '.' .

Options:

- **heartbeat**: by default true, can be an int
- **colorize**: by default true: colorize the output
