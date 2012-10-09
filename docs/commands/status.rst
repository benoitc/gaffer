.. _status:


Return the status of a process
==============================

This command dynamically add a process to monitor in gafferd.


HTTP Message:
-------------

::

    HTTP/1.1 GET /status/name
    Content-Type: application/json


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

    gafferctl status name

Options
+++++++

- <name>: name of the process to create
