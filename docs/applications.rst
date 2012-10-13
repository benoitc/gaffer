Gaffer applications
===================

Gaffer applications are applications that are started by the manager. A
gaffer application can be used to interract with the manager or
listening on events.

An application is a class with the following structure::

    class Myapplication(object):

        def __init__(self):
            # do inti

        def start(self, loop, manager):
            # this method is call by the manager to start the
            application

        def stop(self):
            # method called when the manager stop

        def restart(self):
            # methhod called when the manager restart

Following applications are provided by gaffer:
----------------------------------------------

.. toctree::
   :maxdepth: 2

   http_handler
   sig_handler
