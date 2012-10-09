.. _running:


Number of running processes for this process description
========================================================

This command return the number of processes that are currently
running.


HTTP Message:
-------------

::

    HTTP/1.1 GET /status/<name>

The response return::

    {
        "active": true,
        "running": 1,
        "numprocesses": 1
    } 

with an http status 200 if everything is ok.

Properties:
-----------

- **name**: name of the process


Command line:
-------------

::

    gafferctl running name

Options
+++++++

- <name>: name of the process to start
