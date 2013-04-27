Command Line
============

Gaffer is a :doc:`process management framework <processframework>` but
also a set of command lines tools allowing yout to manage on your
machine or a cluster. All the command line tools are obviously using the
framework.


:doc:`gaffer`is an interface to the :doc:`gaffer HTTP api <http>` and
inclusde support for loading/unloadin apps, scaling them up and down,
... . It can also be used as a manager for Procfile-based applications
similar to foreman but using the :doc:`gaffer framework
<processframework>`. It is running your application directly using a
Procfile or export it to a gafferd configuration file or simply to a
JSON file that you could send to gafferd using the :doc:`HTTP api
<http>`.

:doc:`gafferd` is a server able to launch and manage processes. It
can be controlled via the :doc:`http`. It is controlled by gafferctl and
can be used to handle many processes.

The tool :doc:`gafferctl`  allows you to control a local or remote gafferd
node via the HTTP API. You can show processes informations, add new
processes, changes their configureation, get changes on the nodes in rt
....



.. toctree::
   :titlesonly:

   gaffer
   gafferd
   gafferctl
