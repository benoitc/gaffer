Manager controllers
===================

Documentation of the manager controllers provided by gaffer. A
controller is responsible of fetching infos from the manager and
handling actions.

A controller is a class with the following structure::

    class Mycontroller(object):

        def __init__(self):
            # do inti

        def start(self, loop, manager):
            # this method is call by the manager to start the controller

        def stop(self):
            # method called when the manager stop

        def restart(self):
            # methhod called when the manager restart

Following controllers are provided by gaffer:
---------------------------------------------

.. toctree::
   :maxdepth: 2

   http_handler
   sig_handler
