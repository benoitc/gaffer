Gaffer
======

**gafferp** is a manager for Procfile-based applications similar to
foreman but using the :doc:`gaffer framework <processframework>`. It is
running your application directly using a Procfile or export it to a
gafferd configuration file or simply to a JSON file that you could send
to gafferd using the :doc:`HTTP api <http>`.

For example using the following **Procfile**::

    dummy: python -u dummy_basic.py
    dummy1: python -u dummy_basic.py


You can launch all the programs in this procfile using the following
command line::

    $ gafferp start

.. image:: _static/gafferp.png

Command line usage
++++++++++++++++++

::

    $ gaffer
    usage: gaffer [options] command [args]

    manage Procfiles applications.

    optional arguments:
      -h, --help            show this help message and exit
      -c CONCURRENCY, --concurrency CONCURRENCY
                            Specify the number of each process type to run. The
                            value passed in should be in the format
                            process=num,process=num
      -e ENVS [ENVS ...], --env ENVS [ENVS ...]
                            Specify one or more .env files to load
      -f FILE, --procfile FILE
                            Specify an alternate Procfile to load
      -d ROOT, --directory ROOT
                            Specify an alternate application root. This defaults
                            to the directory containing the Procfile
      --version             show program's version number and exit

    Commands:

        start [name]   	start a process
        run <cmd>      	run one-off commands
        export [format]	export
