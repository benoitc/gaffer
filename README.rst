Gaffer
======

Application deployement, monitoring and supervision made simple.

Gaffer is a set of Python modules and tools to easily maintain and
interact with your applications.

.. image::
    https://secure.travis-ci.org/benoitc/gaffer.png?branch=master
    :alt: Build Status
    :target: https://travis-ci.org/benoitc/gaffer

Features
--------

    - Framework to manage and interact your processes
    - Fully evented. Use the libuv event loop using the
      `pyuv library <http://pyuv.readthedocs.org>`_
    - Server and `command line
      <http://gaffer.readthedocs.org/en/latest/command-line.html>`_ tools to manage
      your processes
    - Procfile applications support (see `gaffer
      <http://gaffer.readthedocs.org/en/latest/gaffer.html>`_)
    - HTTP Api (multiple binding, unix sockets & HTTPS supported)
    - Flapping: handle cases where your processes crash too much
    - Possibility to interact with STDIO:
        - websocket stream to write to stdin and receive from stdout
          (muliple clients can read and write at the same time)
        - subscribe on stdout/stderr feed via longpolling, continuous
          stream, eventsource or websockets
        - write your own client/server using the framework
    - Subscribe to process statistics per process or process templates
      and get them in quasi RT.
    - Easily extensible: add your own endpoint, create your client,
      embed gaffer in your application, ...
    - Compatible with python 2.6x, 2.7x, 3.x


Documentation
-------------

http://gaffer.readthedocs.org

Getting Started
---------------

http://gaffer.readthedocs.org/en/latest/getting-started.html

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


From pypi::

    $ pip install gaffer


License
-------

gaffer is available in the public domain (see UNLICENSE). gaffer is also
optionally available under the MIT License (see LICENSE), meant
especially for jurisdictions that do not recognize public domain
works.

