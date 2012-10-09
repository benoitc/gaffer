.. _processes:


Add a process to monitor
========================

This command dynamically add a process to monitor in gafferd.


HTTP Message:
-------------

::

    HTTP/1.1 GET /processes?running=true

The response return a list of processes. If running=true it will
return the list of running processes by pids (pids are internal
process ids).

Command line:
-------------

::

    gafferctl processes [--running]

Options
+++++++

- <name>: name of the process to create
- --running: return the list of process by pid
