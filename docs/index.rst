.. gaffer documentation master file, created by
   sphinx-quickstart on Tue Oct  9 21:10:46 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to gaffer's documentation!
==================================

Gaffer
======

Control, Watch and Launch your applications and jobs over HTTP.

Gaffer is a set of Python modules and tools to easily maintain and
interact with your applications or jobs launched on different machines over
HTTP and websockets.

It promotes distributed and decentralized topologies without single points of
failure, enabling fault tolerance and high availability.

.. raw:: html

    <iframe src="http://player.vimeo.com/video/51674172" width="500"
    height="163" frameborder="0" webkitAllowFullScreen
    mozallowfullscreen allowFullScreen></iframe>

Features
--------

    - RESTful HTTP Api
    - Websockets and `SOCKJS <http://sockjs.org>`_ support to interact with
      a gaffer node from any browser or SOCKJS client.
    - Framework to manage and interact your applications and jobs on
      differerent machines
    - Server and :doc:`command-line` tools to manage and interact with your
      processes
    - manages topology information. Clients query gaffer_lookupd to discover
      gaffer nodes for a specific job or application.
    - Possibility to interact with STDIO and PIPES to interact with your
      applications and processes
    - Subscribe to process statistics per process or process templates
      and get them in quasi RT.
    - Procfile applications support (see :doc:`gaffer`) but also JSON config
      support.
    - Supervisor-like features.
    - Fully evented. Use the libuv event loop using the
      `pyuv library <https://pyuv.readthedocs.io>`_
    - Flapping: handle cases where your processes crash too much
    - Easily extensible: add your own endpoint, create your client,
      embed gaffer in your application, ...
    - Compatible with python 2.7x, 3.x

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

