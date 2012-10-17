.. _gaffer_run:


Run one-off command
-------------------

gaffer run is used to run one-off commands using the same
environment as your defined processes.

Command line:
-------------

::

    $ gaffer run /some/script



Options
+++++++

**-c**, **--concurrency**:

    Specify the number of each process type to run. The value
    passed in should be in the format process=num,process=num

**--env**
    Specify one or more .env files to load

**-f**, **--procfile**:
    Specify an alternate Procfile to load

**-d**, **--directory**:

    Specify an alternate application root. This defaults to the
    directory containing the Procfile
