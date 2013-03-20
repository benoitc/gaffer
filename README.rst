Gaffer
======


Control, Watch and Launch your applications and jobs over HTTP.

Gaffer is a set of Python modules and tools to easily maintain and
interact with your applications or jobs launched on different machines over
HTTP and websockets.

It promotes distributed and decentralized topologies without single points of
failure, enabling fault tolerance and high availability.

Features
--------

    - RESTful HTTP Api
    - Websockets and `SOCKJS <http://sockjs.org>`_ support to interact with
      a gaffer node from any browser or SOCKJS client.
    - Framework to manage and interact your applications and jobs on
      differerent machines
    - Server and :doc:`command-line` tools to manage and interract with your
      processes
    - manages topology information. Clients query gaffer_lookupd to discover
      gaffer nodes for a specific job or application.
    - Possibility to interact with STDIO and PIPES to interact with your
      applications and processes
    - Subscribe to process statistics per process or process templates
      and get them in quasi RT.
    - Procfile applications support (see :doc:`gaffer`) but also JSON config
      support.
    - Fully evented. Use the libuv event loop using the
      `pyuv library <http://pyuv.readthedocs.org>`_
    - Flapping: handle cases where your processes crash too much
    - Easily extensible: add your own endpoint, create your client,
      embed gaffer in your application, ...
    - Compatible with python 2.7x, 3.x

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

Build status
------------

**Master branch**:

.. image::
    https://secure.travis-ci.org/benoitc/gaffer.png?branch=master
    :alt: Build Status
    :target: https://travis-ci.org/benoitc/gaffer
    :align: left

**Develop branch**:

.. image::
    https://secure.travis-ci.org/benoitc/gaffer.png?branch=develop
    :alt: Build Status
    :target: https://travis-ci.org/benoitc/gaffer
    :align: left

License
-------

gaffer is available in the public domain (see UNLICENSE). gaffer is also
optionally available under the MIT License (see LICENSE), meant
especially for jurisdictions that do not recognize public domain
works.

