Gafferd
=======

Gafferd is a server able to launch and manage processes. It can be
controlled via the :doc:`http` .

Usage
+++++

::

    $ gafferd --help
    usage: gafferd [-h] [-v] [-vv] [--daemon] [--pidfile PIDFILE] [--bind BIND]
                   [--certfile CERTFILE] [--keyfile KEYFILE] [--backlog BACKLOG]
                   [config]

    Run some watchers.

    positional arguments:
      config               configuration file

    optional arguments:
      -h, --help           show this help message and exit
      -v                   verbose mode
      -vv                  like verbose mode but output stream too
      --daemon             Start gaffer in the background
      --pidfile PIDFILE
      --bind BIND          default HTTP binding
      --certfile CERTFILE  SSL certificate file for the default binding
      --keyfile KEYFILE    SSL key file for the default binding
      --backlog BACKLOG    default backlog

Config file example
+++++++++++++++++++

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
