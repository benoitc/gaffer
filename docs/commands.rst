.. _cli:

==============
Console tools
==============

gafferctl
=========

*gafferctl* can be used to run any command listed below. For
example, you can get a list of all processes templates::

    $ gafferctl processes


*gafferctl* is an HTTP client able to connect to a UNIX pipe or a tcp
connection and connect to a gaffer node. It is using the httpclient
module to do it.

You can create your own client either by using the client API provided
in the httpclient module or by reading the doc here an dpassing your own
message to the gaffer node. All messages are encoded in JSON.


gafferctl commands
-------------------

- **status**: :doc:`commands/status`
- **processes**: :doc:`commands/processes`
- **sub**: :doc:`commands/sub`
- **add_process**: :doc:`commands/add_process`
- **get_process**: :doc:`commands/get_process`
- **stop**: :doc:`commands/stop`
- **running**: :doc:`commands/running`
- **start**: :doc:`commands/start`
- **add**: :doc:`commands/add`
- **update_process**: :doc:`commands/update_process`
- **kill**: :doc:`commands/kill`
- **numprocesses**: :doc:`commands/numprocesses`
- **del_process**: :doc:`commands/del_process`
- **pids**: :doc:`commands/pids`

.. toctree::
   :hidden:
   :glob:

   commands/*
