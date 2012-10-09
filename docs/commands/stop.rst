.. _stop:


Stop a process
===============

This command dynamically stop a process.


HTTP Message:
-------------

::

    HTTP/1.1 POST /processes/<name>/_stop

The response return {"ok": true} with an http status 200 if
everything is ok.

Properties:
-----------

- **name**: name of the process


Command line:
-------------

::

    gafferctl stop name

Options
+++++++

- <name>: name of the process to start
