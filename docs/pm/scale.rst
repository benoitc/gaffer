.. _gaffer_scale:


Scaling your process
====================

Procfile applications can scal up or down instantly from the
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


Command line
------------

::

    $ gaffer scale [group] process[=|-|+]3


Options
+++++++

**--endpoint**

    Gaffer node URL to connect.


Operations supported are +,-,=
