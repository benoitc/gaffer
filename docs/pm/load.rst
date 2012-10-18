.. _gaffer_load:


Load a Procfile application to gafferd
======================================

This command allows you to load your Procfile application
in gafferd.

Command line
------------

    $ gaffer load [name] [url]

Arguments
+++++++++

*name* is the name of the group of process recoreded in gafferd.
By default it will be the name of your project folder.You can use
``.`` to specify the current folder.

*uri*  is the url to connect to a gaffer node. By default
'http://127.0.0.1:5000'

Options
+++++++

**--endpoint**

    Gaffer node URL to connect.
