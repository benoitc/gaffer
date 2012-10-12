.. _add:


Increment the number of OS processes
====================================

This command dynamically increase the number of OS processes for
this process description to monitor in gafferd.


HTTP Message:
-------------

::

    HTTP/1.1 POST /processes/<name>/_add/<inc>

The response return {"ok": true} with an http status 200 if
everything is ok.

Properties:
-----------

- **name**: name of the process
- **inc**: The number of new OS processes to start


Command line:
-------------

::

    gafferctl add name inc

Options
+++++++

- <name>: name of the process to create
- <inc>: The number of new OS processes to start
