CHANGES
=======


2012/10/18 - version 0.3.1
--------------------------

- add environment variables substitution in the process command line.

2012/10/18 - version 0.3.0
--------------------------

- add the :doc:`gaffer` command line tool: load, unload your procfile
  applications to gaffer, scale them up and down. Or just use it as a
  procfile manager just like `foreman <https://github.com/ddollar/foreman>`_ .
- add gafferctl :doc:`commands/watch` command to watch a node activity
  remotely.
- add priority feature: now processes can be launch in order
- add the possibility to manipulate `groups of processes <https://github.com/benoitc/gaffer/commit/05951328e5f80017cf23f0a9721347da67049224>`_
- add the possibility to set the default endpoint in gafferd from the
  command line
- add ``-v`` and ``--vv`` options to gafferd to have a verbose output.
- add an eventsource client in the framework to manipulate gaffer
  streams.
- add ``Manager.start_processes`` method. Start all processes.
- add console_output application to the framework
- add new global :doc:`events` to the manager: spawn, reap, stop_pid,
  exit.
- fix shutdown
- fix heartbeat


2012/10/15 - version 0.2.0
--------------------------

- add :doc:`webhooks`: post to an url when a gaffer event is triggered
- add graceful shutdown. kill processes after a graceful time
- add :doc:`commands/load_process` command
- code refactoring: make the code simpler

2012/10/12 - version 0.1.0
--------------------------

Initial release
