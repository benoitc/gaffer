.. _del_process:


Get a process description
=========================

This command stop a process and remove it from the monitored
process.

HTTP Message:
-------------

::

    HTTP/1.1 DELETE /processes/<name>


The response return {"ok": true} with an http status 200 if
everything is ok.

Properties:
-----------

- **name**: name of the process

Command line:
-------------

::

    gafferctl del_process name


Options
+++++++

- <name>: name of the process to remove
