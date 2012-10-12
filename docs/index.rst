.. gaffer documentation master file, created by
   sphinx-quickstart on Tue Oct  9 21:10:46 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to gaffer's documentation!
==================================

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
      `pyuv library <https://pyuv.readthedocs.com>`_
    - Server and console tool to manage your process via HTTP on TCP and
      UNIX sockets.
    - HTTPS supported
    - Flapping: handle cases where your processes crash too much
    - Possibility to interract with STDIO:
        - websocket stream to write to stdin and receive from stdout
          (muliple clients can write at the same time)
        - subscribe on stdout/stderr feed via longpolling, continuous
          stream, eventsource or websockets
        - write your own client/server using the framework
    - Subscribe to process statistics per process or process templates
      and get them in quasi RT.
    - Flapping: handle cases where your processes crash too much
    - Easily extensible: add your own endpoint, create your client,
      embed gaffer in your application, ...
    - Compatible with python 2.6x, 2.7x, 3.x

.. note::
    gaffer source code is hosted on `Github <http://github.com/benoitc/gaffer.git>`_

Contents:
---------

.. toctree::
   :titlesonly:

   overview
   commands
   processframework
   http
   httpclient
   controllers


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

