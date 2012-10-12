Gaffer
======

.. image:: https://secure.travis-ci.org/benoitc/gaffer.png?branch=master
    :target: http://travis-ci.org/benoitc/gaffer

Simple process management

Gaffer is a set of Python modules and tools to easily maintain and
interract with your processes.

Features
--------

    - Framework to manage and interract your processes
    - Fully evented. Use the libuv event loop using the
      `pyuv library <https://pyuv.readthedocs.org>`_
    - Server and console tool to manage your process via HTTP on TCP and
      UNIX sockets.
    - HTTPS supported
    - Flapping: handle cases where your processes crash too much
    - Watch a dir to launch any processe inside
    - Control your processes by only using cat & echo on unix
    - Compatible with python 2.6x, 2.7x, 3.x


Documentation
-------------

http://gaffer.readthedoc.org

Installation
------------

Gaffer requires Python superior to 2.6 (yes Python 3 is supported)

To install gaffer using pip you must make sure you have a
recent version of distribute installed::

    $ curl -O http://python-distribute.org/distribute_setup.py
    $ sudo python distribute_setup.py
    $ easy_install pip


To install from source, run the following command::

    $ git clone https://github.com/benoitc/gaffer.git
    $ cd gaffer && pip install -r requirements.txt

License
-------

gaffer is available in the public domain (see UNLICENSE). gaffer is also
optionally available under the MIT License (see LICENSE), meant
especially for jurisdictions that do not recognize public domain
works.

