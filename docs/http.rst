HTTP api
========

an http API provided by the ``gaffer.http_handler.HttpHandler```
gaffer application can be used to control gaffer via HTTP. To embed it in your
app just initialize your manager with it::

    manager = Manager(apps=[HttpHandler()])

The HttpHandler can be configured to accept multiple endpoinds and can
be extended with new HTTP handlers. Internally we are using Tornado so
you can either extend it with rules using pure totrnado handlers or wsgi
apps.


.. _api-format:

Request Format and Responses
----------------------------

Gaffer supports **GET**, **POST**, **PUT**, **DELETE**, **OPTIONS** HTTP
verbs.

All messages (except some streams) are JSON encoded. All messages sent
to gaffers should be json encoded.

Gaffer supports cross-origin resource sharing (aka CORS).

HTTP endpoints
--------------

Main http endpoints are described in the description of the gafferctl
commands in :doc:`commands`:

.. toctree::
    :maxdepth: 1
    :hidden:
    :glob:

    commands/*

Gafferctl is using extensively this HTTP api.

Output streams
--------------

The output streams can be fetched by doing::

    GET /streams/<pid>/<nameofeed>

It accepts the following query parameters:

- **feed** : continuous, longpoll, eventsource
- **heartbeat**: true or seconds, send an empty line each sec (if true
  60)

ex::

    $ curl localhost:5000/streams/1/stderr?feed=continuous
    STDERR 12
    STDERR 13
    STDERR 14
    STDERR 15
    STDERR 16
    STDERR 17
    STDERR 18
    STDERR 19
    STDERR 20
    STDERR 21
    STDERR 22
    STDERR 23
    STDERR 24
    STDERR 25
    STDERR 26
    STDERR 27
    STDERR 28
    STDERR 29
    STDERR 30
    STDERR 31

    $ curl localhost:5000/streams/1/stderr?feed=longpoll
    STDERR 215

    $ curl localhost:5000/streams/1/stderr?feed=eventsource
    event: stderr
    data: STDERR 20

    event: stderr
    data: STDERR 21

    event: stderr
    data: STDERR 22

    $ curl localhost:5000/streams/1/stdout?feed=longpoll
    STDOUTi 14


Write to STDIN
--------------

It is now possible to write to stdin via the HTTP api by sending::

    POST to /streams/<pid>/ttin

Where <pid> is an internal process ide that you can retrieve by
calling `GET /processses/<name>/_pids`

ex::

    $ curl -XPOST -d $'ECHO\n' localhost:5000/streams/2/stdin
    {"ok": true}

    $ curl localhost:5000/streams/2/stdout?feed=longpoll
    ECHO


Websocket stream for STDIN/STDOUT
---------------------------------

It is now possible to get stin/stdout via a websocket. Writing to
``ws://HOST:PORT/wstreams/<pid>`` will send the data to stdin any
information written on stdout will be then sent back to the websocket.

See the echo client/server example in the example folder::

    $ python echo_client.py
    Sent
    Reeiving...
    Received 'ECHO

    '
    (test)enlil:examples benoitc$ python echo_client.py
    Sent
    Reeiving...
    Received 'ECHO

.. note::

    unfortunately the echo_client script can only be launched with
    python 2.7 :/

.. note::

    to redirect stderr to stdout just use the same name when you setting
    the redirect_output property on process creation.
