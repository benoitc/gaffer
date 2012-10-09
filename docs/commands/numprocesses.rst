.. _numprocesses:


Number of processes that should be launched
===========================================

This command return the number of processes that should be
launched


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

    gafferctl numprocesses name

Options
+++++++

- <name>: name of the process to start
