.. gaffer documentation master file, created by
   sphinx-quickstart on Tue Oct  9 21:10:46 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to gaffer's documentation!
==================================

Gaffer
======

Application deployement, monitoring and supervision made simple.

Gaffer is a set of Python modules and tools to easily maintain and
interact with your applications.

.. raw:: html

    <iframe src="http://player.vimeo.com/video/51674172" width="500"
    height="163" frameborder="0" webkitAllowFullScreen
    mozallowfullscreen allowFullScreen></iframe>

Features
--------

    - Framework to manage and interact your processes
    - Fully evented. Use the libuv event loop using the
      `pyuv library <http://pyuv.readthedocs.org>`_
    - Server and :doc:`command-line` tools to manage your
      processes
    - Procfile applications support (see :doc:`gaffer`)
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

.. note::
    gaffer source code is hosted on `Github <http://github.com/benoitc/gaffer.git>`_

Contents:
---------

.. toctree::
   :titlesonly:

   getting-started
   overview
   news
   command-line
   http
   webhooks
   processframework
   httpclient
   applications

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

