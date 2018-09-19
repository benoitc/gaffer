.. _gaffer:

Gaffer
======

The **gaffer** command line tool is an interface to the :doc:`gaffer
HTTP api <http>` and include support for loading/unloading Procfile
applications, scaling them up and down, ... .

It can also be used as a manager for Procfile-based applications similar to
foreman but using the :doc:`gaffer framework <processframework>`. It is
running your application directly using a Procfile or export it to a
gafferd configuration file or simply to a JSON file that you could send
to gafferd using the :doc:`HTTP api <http>`.

Example of use
--------------

For example using the following **Procfile**::

    dummy: python -u dummy_basic.py
    dummy1: python -u dummy_basic.py


You can launch all the programs in this procfile using the following
command line::

    $ gaffer start


.. image:: _static/gafferp.png


Or load them on a gaffer node::

    $ gaffer load

and then scale them up and down::

    $ gaffer scale dummy=3 dummy1+2
    Scaling dummy processes... done, now running 3
    Scaling dummy1 processes... done, now running 3


.. image:: _static/gaffer_ps.png

OPTIONS
-------

    -h --help                           show this help message and exit
    --version                           show version and exit
    -f procfile,--procfile procfile     Specify an alternate Procfile to load
    -d root,--directory root            Specify an alternate application root
                                        This defaults to the  directory
                                        containing the Procfile [default: .]
    -e k=v,--env k=v                    Specify one or more .env files to load
    --endpoint endpoint                 gafferd node URL to connect
                                        [default: http://127.0.0.1:5000]


SUBCOMMANDS
-----------

    **export** [-c concurrency|--concurrency concurrency]
               [--format=format] [--out=filename] [<name>]

                Export a Procfile

                This command export a Procfile to a gafferd process settings
                format. It can be either a JSON that you could send to gafferd
                via the JSON API or an ini file that can be included to the
                gafferd configuration.

                <format>        ini or json
                --out=filename  path of filename where the export will be saved

    **load** [-c concurrency|--concurrency concurrency] [--nostart] [<name>]
                Load a Procfile application to gafferd

                <name> is the name of the application recorded in
                        gafferd. By default it will be the name of your
                        project folder.You can use ``.`` to specify the current
                        folder.

    **ps** [<appname>]
                List your processes information

                <appname> he name of the application (session) of process
                recoreded in gafferd.  By default it will be the name of your
                project folder.You can use ``.`` to specify the current
                folder.

    **run** [-c] [<args>]...
            Run one-off commands using the same environment as your
            defined processes

            -c concurrency
                Specify the number of each process type to run. The value
                passed in should be in the format process=num,process=num
            --concurrency concurrency
                same as the -c option.

    **scale** [<appname>] [process=value]...
            Scaling your process

            Procfile applications can scale up or down instantly from the
            command line or API.

            Scaling a process in an application is done using the scale
            command:

                ::

                    $ gaffer scale dummy=3
                    Scaling dummy processes... done, now running 3


            Or both at once:

                ::

                    $ gaffer scale dummy=3 dummy1+2
                    Scaling dummy processes... done, now running 3
                    Scaling dummy1 processes... done, now running 3




    **start** [-c concurrency|--concurrency concurrency]

            Start a process type or all process types from the Procfile.

            -c concurrency
                Specify the number of each process type to run. The value
                passed in should be in the format process=num,process=num
            --concurrency concurrency
                same as the -c option.


    **unload** [<name>]
            Unload a Procfile application from a gafferd node
