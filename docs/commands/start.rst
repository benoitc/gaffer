.. _start:


Start a process
===============

This command dynamically start a process.


HTTP Message:
-------------

::

    HTTP/1.1 POST /processes/<name>/_start

The response return {"ok": true} with an http status 200 if
everything is ok.

Properties:
-----------

- **name**: name of the process


Command line:
-------------

::

    gafferctl start name

Options
+++++++

- <name>: name of the process to start
