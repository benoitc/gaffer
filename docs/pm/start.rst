.. _gaffer_start:


Start a process
===============

Start a process or all process from the Procfile.

Command line
------------

::

    $ gaffer start [name]


Gaffer will run your application directly from the command line.

If no additional parameters are passed, gaffer  run one instance
of each type of process defined in your Procfile.

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
