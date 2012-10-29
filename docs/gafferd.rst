Gafferd
=======

Gafferd is a server able to launch and manage processes. It can be
controlled via the :doc:`http` .

Usage
-----

::

    $ gafferd -h
    usage: gafferd [-h] [-c CONFIG_FILE] [-p PLUGINS_DIR] [-v] [-vv] [--daemon]
                   [--pidfile PIDFILE] [--bind BIND] [--certfile CERTFILE]
                   [--keyfile KEYFILE] [--backlog BACKLOG]
                   [config]

    Run some watchers.

    positional arguments:
      config                configuration file

    optional arguments:
      -h, --help            show this help message and exit
      -c CONFIG_FILE, --config CONFIG_FILE
                            configuration file
      -p PLUGINS_DIR, --plugins-dir PLUGINS_DIR
                            default plugin dir
      -v                    verbose mode
      -vv                   like verbose mode but output stream too
      --daemon              Start gaffer in the background
      --pidfile PIDFILE
      --bind BIND           default HTTP binding
      --certfile CERTFILE   SSL certificate file for the default binding
      --keyfile KEYFILE     SSL key file for the default binding
      --backlog BACKLOG     default backlog

Config file example
-------------------

::

    [gaffer]
    http_endpoints = public

    [endpoint:public]
    bind = 127.0.0.1:5000
    ;certfile=
    ;keyfile=

    [webhooks]
    ;create = http://some/url
    ;proc.dummy.spawn = http://some/otherurl


    [process:dummy]
    cmd = ./dummy.py
    ;cwd = .
    ;uid =
    ;gid =
    ;detach = false
    ;shell = false
    ; flapping format: attempts=2, window=1., retry_in=7., max_retry=5
    ;flapping = 2, 1., 7., 5
    numprocesses = 1
    redirect_output = stdout, stderr
    ; redirect_input  = true
    ; graceful_timeout = 30

    [process:echo]
    cmd = ./echo.py
    numprocesses = 1
    redirect_output = stdout, stderr
    redirect_input  = true

Plugins
-------

Plugins are a way to enhance the basic gafferd functionality in a custom manner.
Plugins allows you to load any gaffer application and site plugins. You
can for example use the plugin system to add a simple UI to administrate
gaffer using the HTTP interface.

A plugin has the following structure::

    /pluginname
        _site/
        plugin/
            __init__.py
            ...
            ***.py

A plugin can be discovered by adding one ore more module that expose a
class inheriting from ``gaffer.Plugin``. Every plugin file should have a
__all__ attribute containing the implemented plugin class. Ex::


    from gaffer import Plugin

    __all__ = ['DummyPlugin']

    from .app import DummyApp


    class DummyPlugin(Plugin):
        name = "dummy"
        version = "1.0"
        description = "test"

        def app(self, cfg):
            return DummyApp()


The dummy app here only print some info when started or stopped::


    class DummyApp(object):

        def start(self, loop, manager):
            print("start dummy app")

        def stop(sef):
            print("stop dummy")

        def rester(self):
            print("restart dummy")


See the :doc:`overview` for more infos. You can try it in the example
folder::

    $ cd examples
    $ gafferd -c gaffer.ini -p plugins/


Install plugins
+++++++++++++++

Installing plugins can be done by placing the plugin in the plugin
folder. The plugin folder is either set in the setting file using the
**plugin_dir** in the gaffer section or using the ``-p`` option of the
command line.

The default plugin dir is set to ``~/.gafferd/plugins`` .

Site plugins
++++++++++++

Plugins can have “sites” in them, any plugin that exists under the
plugins directory with a _site directory, its content will be statically
served when hitting ``/_plugin/[plugin_name]/`` url. Those can be added even
after the process has started.

Installed plugins that do not contain any Python related content, will
automatically be detected as site plugins, and their content will be
moved under _site.


Mandatory Plugins
+++++++++++++++++

If you rely on some plugins, you can define mandatory plugins using the
``mandatory`` attribute of a the plugin class, for example, here is a
sample config::


    class DummyPlugin(Plugin):
        ...
        mandatory = ['somedep']
