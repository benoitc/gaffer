# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import array
import base64
from collections import deque
import functools
import hashlib
import json
import logging
import os
import re
import socket
import struct
import threading
import time
import uuid

import pyuv
import tornado.escape
from tornado import iostream
from tornado.httputil import HTTPHeaders
from tornado.util import bytes_type

from ..tornado_pyuv import IOLoop, install
install()

from ..error import AlreadyRead
from ..events import EventEmitter
from ..message import (Message, decode_frame, FRAME_ERROR_TYPE,
        FRAME_RESPONSE_TYPE, FRAME_MESSAGE_TYPE)
from ..util import urlparse, ord_

# The initial handshake over HTTP.
WS_INIT = """\
GET %(path)s HTTP/1.1
Host: %(host)s:%(port)s
Upgrade: websocket
Connection: Upgrade
Sec-Websocket-Key: %(key)s
Sec-Websocket-Version: 13
"""

# Magic string defined in the spec for calculating keys.
WS_MAGIC = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

LOGGER = logging.getLogger("gaffer")

def frame(data, opcode=0x01):
    """Encode data in a websocket frame."""
    # [fin, rsv, rsv, rsv] [opcode]
    frame = struct.pack('B', 0x80 | opcode)

    # Our next bit is 1 since we're using a mask.
    length = len(data)
    if length < 126:
        # If length < 126, it fits in the next 7 bits.
        frame += struct.pack('B', 0x80 | length)
    elif length <= 0xFFFF:
        # If length < 0xffff, put 126 in the next 7 bits and write the length
        # in the next 2 bytes.
        frame += struct.pack('!BH', 0x80 | 126, length)
    else:
        # Otherwise put 127 in the next 7 bits and write the length in the next
        # 8 bytes.
        frame += struct.pack('!BQ', 0x80 | 127, length)

    # Clients must apply a 32-bit mask to all data sent.
    mask = [ord_(c) for c in os.urandom(4)]
    frame += struct.pack('!BBBB', *mask)
    # Mask each byte of data using a byte from the mask.
    msg = [ord_(c) ^ mask[i % 4] for i, c in enumerate(data)]
    frame += struct.pack('!' + 'B' * length, *msg)
    return frame


class WebSocket(object):
    """Websocket client for protocol version 13 using the Tornado IO loop."""

    def __init__(self, loop, url, **kwargs):
        ports = {'ws': 80, 'wss': 443}

        self.loop = loop
        self._io_loop = IOLoop(_loop=loop)

        self.url = urlparse(url)
        self.scheme = self.url.scheme
        self.host = self.url.hostname
        self.port = self.url.port or ports[self.url.scheme]
        self.path = self.url.path or '/'

        # support the query argument in the path
        self.path += self.url.query and "?%s" % self.url.query or ""

        self.client_terminated = False
        self.server_terminated = False
        self._final_frame = False
        self._frame_opcode = None
        self._frame_length = None
        self._fragmented_message_buffer = None
        self._fragmented_message_opcode = None
        self._waiting = None
        self._pending_messages = []
        self._started = False

        self.key = base64.b64encode(os.urandom(16))

        # initialize the stream
        if 'ssl_options' in kwargs:
            self.stream = iostream.SSLIOStream(socket.socket(),
                    io_loop=self._io_loop, **kwargs)
        else:
            self.stream = iostream.IOStream(socket.socket(),
                    io_loop=self._io_loop)

        self.graceful_shutdown = kwargs.get('graceful_shutdown', 0)

    def start(self):
        # start the stream
        self.stream.connect((self.host, self.port), self._on_connect)


    def on_open(self):
        pass

    def on_message(self, data):
        pass

    def on_ping(self):
        pass

    def on_pong(self):
        pass

    def on_close(self):
        pass

    def write_message(self, message, binary=False):
        """Sends the given message to the client of this Web Socket."""
        if binary:
            opcode = 0x2
        else:
            opcode = 0x1
        message = tornado.escape.utf8(message)
        assert isinstance(message, bytes_type)

        if not self._started:
            self._pending_messages.append(message)
        else:
            self._write_frame(True, opcode, message)

    def ping(self):
        self._write_frame(True, 0x9, b'')

    def close(self):
        """Closes the WebSocket connection."""
        self._started = False

        if not self.server_terminated:
            if not self.stream.closed():
                self._write_frame(True, 0x8, b'')
            self.server_terminated = True

        if self.graceful_shutdown:
            if self.client_terminated:
                if self._waiting is not None:
                    try:
                        self.stream.io_loop.remove_timeout(self._waiting)
                    except KeyError:
                        pass
                    self._waiting = None
                self._terminate()
            elif self._waiting is None:
                # Give the client a few seconds to complete a clean shutdown,
                # otherwise just close the connection.
                self._waiting = self.stream.io_loop.add_timeout(
                    time.time() + self.graceful_shutdown, self._abort)
        else:
            if self.client_terminated:
                return

            self._terminate()

    def _terminate(self):
        self.client_terminated = True
        self.stream.close()
        self.stream.io_loop.close()

    def _write_frame(self, fin, opcode, data):
        self.stream.write(frame(data, opcode))

    def _on_connect(self):
        req_params = dict(path = self.path, host = self.host,
                key = tornado.escape.native_str(self.key),
                port = self.port)
        request = '\r\n'.join(WS_INIT.splitlines()) % req_params + '\r\n\r\n'
        self.stream.write(request.encode('latin1'))
        self.stream.read_until(b'\r\n\r\n', self._on_headers)

    def _on_headers(self, data):
        first, _, rest = data.partition(b'\r\n')
        headers = HTTPHeaders.parse(tornado.escape.native_str(rest))
        # Expect HTTP 101 response.
        assert re.match('HTTP/[^ ]+ 101',
                tornado.escape.native_str(first))
        # Expect Connection: Upgrade.
        assert headers['Connection'].lower() == 'upgrade'
        # Expect Upgrade: websocket.
        assert headers['Upgrade'].lower() == 'websocket'
        # Sec-WebSocket-Accept should be derived from our key.
        accept = base64.b64encode(hashlib.sha1(self.key + WS_MAGIC).digest())
        assert headers['Sec-WebSocket-Accept'] == tornado.escape.native_str(accept)

        self._started = True
        if self._pending_messages:
            for msg in self._pending_messages:
                self.write_message(msg)
            self._pending_messages = []

        self._async_callback(self.on_open)()
        self._receive_frame()

    def _receive_frame(self):
        self.stream.read_bytes(2, self._on_frame_start)

    def _on_frame_start(self, data):
        header, payloadlen = struct.unpack("BB", data)
        self._final_frame = header & 0x80
        reserved_bits = header & 0x70
        self._frame_opcode = header & 0xf
        self._frame_opcode_is_control = self._frame_opcode & 0x8
        if reserved_bits:
            # client is using as-yet-undefined extensions; abort
            return self._abort()
        if (payloadlen & 0x80):
            # Masked frame -> abort connection
            return self._abort()
        payloadlen = payloadlen & 0x7f
        if self._frame_opcode_is_control and payloadlen >= 126:
            # control frames must have payload < 126
            return self._abort()
        if payloadlen < 126:
            self._frame_length = payloadlen
            self.stream.read_bytes(self._frame_length, self._on_frame_data)
        elif payloadlen == 126:
            self.stream.read_bytes(2, self._on_frame_length_16)
        elif payloadlen == 127:
            self.stream.read_bytes(8, self._on_frame_length_64)

    def _on_frame_length_16(self, data):
        self._frame_length = struct.unpack("!H", data)[0]
        self.stream.read_bytes(self._frame_length, self._on_frame_data)

    def _on_frame_length_64(self, data):
        self._frame_length = struct.unpack("!Q", data)[0]
        self.stream.read_bytes(self._frame_length, self._on_frame_data)

    def _on_frame_data(self, data):
        unmasked = array.array("B", data)

        if self._frame_opcode_is_control:
            # control frames may be interleaved with a series of fragmented
            # data frames, so control frames must not interact with
            # self._fragmented_*
            if not self._final_frame:
                # control frames must not be fragmented
                self._abort()
                return
            opcode = self._frame_opcode
        elif self._frame_opcode == 0:  # continuation frame
            if self._fragmented_message_buffer is None:
                # nothing to continue
                self._abort()
                return
            self._fragmented_message_buffer += unmasked
            if self._final_frame:
                opcode = self._fragmented_message_opcode
                unmasked = self._fragmented_message_buffer
                self._fragmented_message_buffer = None
        else:  # start of new data message
            if self._fragmented_message_buffer is not None:
                # can't start new message until the old one is finished
                self._abort()
                return
            if self._final_frame:
                opcode = self._frame_opcode
            else:
                self._fragmented_message_opcode = self._frame_opcode
                self._fragmented_message_buffer = unmasked

        if self._final_frame:
            self._handle_message(opcode, unmasked.tostring())

        if not self.client_terminated:
            self._receive_frame()

    def _abort(self):
        """Instantly aborts the WebSocket connection by closing the socket"""
        self.client_terminated = True
        self.server_terminated = True
        self._started = False
        self.stream.close()
        self.close()

    def _handle_message(self, opcode, data):
        if self.client_terminated:
            return

        if opcode == 0x1:
            # UTF-8 data
            try:
                decoded = data.decode("utf-8")
            except UnicodeDecodeError:
                self._abort()
                return
            self._async_callback(self.on_message)(decoded)
        elif opcode == 0x2:
            # Binary data
            self._async_callback(self.on_message)(data)
        elif opcode == 0x8:
            # Close
            self.client_terminated = True
            self.close()
        elif opcode == 0x9:
            # Ping
            self._write_frame(True, 0xA, data)
            self._async_callback(self.on_ping)()
        elif opcode == 0xA:
            # Pong
            self._async_callback(self.on_pong)()
        else:
            self._abort()

    def _async_callback(self, callback, *args, **kwargs):
        """Wrap callbacks with this if they are used on asynchronous requests.

        Catches exceptions properly and closes this WebSocket if an exception
        is uncaught.
        """
        if args or kwargs:
            callback = functools.partial(callback, *args, **kwargs)

        def wrapper(*args, **kwargs):
            try:
                return callback(*args, **kwargs)
            except Exception:
                logging.error('Uncaught exception', exc_info=True)
                self._abort()
        return wrapper


class Channel(object):

    def __init__(self, loop, topic):
        self.topic = topic
        self._emitter = EventEmitter(loop)

    def __str__(self):
        return "channel: %s" % self.topic

    def bind(self, event, callback):
        self._emitter.subscribe(event, callback)

    def unbind(self, event, callback):
        self._emitter.unsubscribe(event, callback)

    def bind_all(self, callback):
        self._emitter.subscribe(".", callback)

    def unbind_all(self, callback):
        self._emitter.unsubscribe(".", callback)

    def send(self, event, message):
        self._emitter.publish(event, message)

    def close(self):
        self._emitter.close()


class GafferCommand(object):

    def __init__(self, *args, **kwargs):
        self.identity = uuid.uuid4().hex
        self.name = args[0]
        self.args = args[1:]
        self.kwargs = kwargs

        self._callbacks = []
        self._result = None
        self._error = None
        self._sock = None
        self.active = False

        self._lock = threading.Lock()
        self._condition = threading.Condition()

    def __str__(self):
        return "GafferCommand:%s (%s)" % (self.name, self.identity)

    def done(self):
        """ return True if the command has been completed or returned an error
        """
        return (self._result is not None or self._error is not None)

    def result(self):
        """ Return the value returned by the call. If the call hasn't been
        completed it will return None """
        with self._condition:
            return self._result

    def error(self):
        """ Return the error returned by the call. If the call hasn't been
        completed it will return None """
        with self._condition:
            return self._error

    def add_done_callback(self, callback):
        self._callbacks.append(callback)

    def _start(self, sock):
        self._sock = sock
        self.active = True

    def _set_result(self, result):
        with self._lock:
            self._result = result
            self.active = False

        self._handle_callbacks()

    def _set_error(self, error):
        with self._lock:
            self._error = error
            self.active = False

        self._handle_callbacks()

    def _handle_callbacks(self):
        for cb in self._callbacks:
            try:
                cb(self)
            except Exception:
                logging.error('Uncaught exception', exc_info=True)


class GafferSocket(WebSocket):

    def __init__(self, loop, url, api_key=None, **kwargs):
        loop = loop

        try:
            self.heartbeat_timeout = kwargs.pop('heartbeat')
        except KeyError:
            self.heartbeat_timeout = 15.0

        self.api_key = api_key

        # define status
        self.active = False
        self.closed = False

        # dict to maintain opened channels
        self.channels = dict()

        # dict to maintain commands
        self.commands = dict()

        # emitter for global events
        self._emitter = EventEmitter(loop)
        self._heartbeat = pyuv.Timer(loop)
        super(GafferSocket, self).__init__(loop, url, **kwargs)

        # make sure we authenticate first
        if self.api_key is not None:
            self.write_message("AUTH:%s" % self.api_key)

    def start(self):
        if self.active:
            return

        super(GafferSocket, self).start()
        self.active = True

    def subscribe(self, topic):
        # we already subsribed to this topic
        if topic in self.channels:
            return

        # make sure we started the socket
        assert self.active == True

        # create a new channel.
        # we don't wait the response for it so we make sure we won't send
        # twice the same message until we really want it.
        self.channels[topic] = Channel(self.loop, topic)

        # send subscription message
        msg = {"event": "SUB", "data": {"topic": topic}}
        self.write_message(json.dumps(msg))
        return self.channels[topic]

    def unsubscribe(self, topic):
        # we are not subscribed to this topic
        if topic not in self.channels:
            return

        # make sure we started the socket
        assert self.active == True

        # remove the channels from the list
        channel = self.channels.pop(topic)
        channel.close()

        # send unsubscription message
        msg = {"event": "UNSUB", "data": {"topic": topic}}
        self.write_message(json.dumps(msg))

    def send_command(self, *args, **kwargs):
        # register a new command
        cmd0 = GafferCommand(*args, **kwargs)
        cmd = self.commands[cmd.identity] = cmd0

        # send the new command
        data = {"identity": cmd.identity, "name": cmd.name, "args": cmd.args,
                "kwargs": cmd.kwargs}
        msg = {"event": "CMD", "data": data}
        self.write_message(json.dumps(msg))

        # return the command object
        return cmd

    def bind(self, event, callback):
        """ bind to a global event """
        self._emitter.subscribe(event, callback)

    def unbind(self, event, callback):
        """ unbind to a global event """
        self._emitter.unsubscribe(event, callback)

    def bind_all(self, callback):
        """ bind to all global events """
        self._emitter.subscribe(".", callback)

    def unbind_all(self, callback):
        """ unbind to all global events """
        self._emitter.unsubscribe(".", callback)

    def __getitem__(self, topic):
        try:
            channel = self.channels[topic]
        except KeyError:
            raise KeyError("%s channel isn't subscribed" % topic)
        return channel

    def __delitem__(self, topic):
        self.unsubcribe(topic)

    ### websocket methods

    def on_open(self):
        # start the heartbeat
        self._heartbeat.start(self.on_heartbeat, self.heartbeat_timeout,
                self.heartbeat_timeout)
        self._heartbeat.unref()

    def on_close(self):
        self.active = False
        self.closed = True
        self._heartbeat.stop()

    def on_message(self, raw):
        msg = json.loads(raw)
        assert "event" in msg

        event = msg['event']

        if event == "gaffer:subscription_success":
            self._emitter.publish("subscription_success", msg)
        elif event == "gaffer:subscription_error":
            self._emitter.publish("subscription_error", msg)

            # get topic
            topic = msg['topic']

            # remove the channel from the subscribed list
            if topic in self.channels:
                channel = self.channels.pop(topic)
                channel.close()

        elif event == "gaffer:command_success":
            identity = msg['data']['id']
            result = msg['data']['result']
            if identity in self.commands:
                cmd = self.commands.pop(identity)
                cmd._set_result(result)
                self._emitter.publish("command_success", cmd)
        elif event == "gaffer:command_error":
            identity = msg['data']['id']
            if identity in self.commands:
                cmd = self.commands.pop(identity)
                cmd._set_error(msg['data']['error'])
                self._emitter.publish("command_error", cmd)
        elif event == "gaffer:event":
            # if message type is an event then it should contain a data
            # property
            assert "data" in msg
            data = msg['data']

            topic = data['topic']
            event = data['event']
            if topic in self.channels:
                channel = self.channels[topic]
                channel.send(event, data)

    def on_heartbeat(self, h):
        # on heartbeat send a nop message to the channel
        # it will maintain the connection open
        self.write_message(json.dumps({"event": "NOP"}))


class IOChannel(WebSocket):

    def __init__(self, loop, url, mode=3, api_key=None, **kwargs):
        loop = loop
        self.api_key = api_key

        # initialize the capabilities
        self.mode = mode
        self.readable = False
        self.writable = False
        if mode & pyuv.UV_READABLE:
            self.readable = True

        if mode & pyuv.UV_WRITABLE:
            self.writable = True

        # set heartbeat
        try:
            self.heartbeat_timeout = kwargs.pop('heartbeat')
        except KeyError:
            self.heartbeat_timeout = 15.0
        self._heartbeat = pyuv.Timer(loop)

        # pending messages queue
        self._queue = deque()
        self.pending = {}

        # define status
        self.active = False
        self.closed = False

        # read callback
        self._read_callback = None

        super(IOChannel, self).__init__(loop, url, **kwargs)

        # make sure we authenticate first
        if self.api_key is not None:
            msg = Message("AUTH:%s" % self.api_key)
            self.write_message(msg.encode())

    def start(self):
        if self.active:
            return

        super(IOChannel, self).start()
        self.active = True

    def start_read(self, callback):
        if not self.readable:
            raise IOError("not_readable")

        if self._read_callback is not None:
            raise AlreadyRead()
        self._read_callback = callback

    def stop_read(self):
        self._read_callback = None


    def write(self, data, callback=None):
        if not self.writable:
            raise IOError("not_writable")

        msg = Message(data)
        if callback is not None:
            self.pending[msg.id] = callback

        self.write_message(msg.encode())

    ### websocket methods

    def on_open(self):
        # start the heartbeat
        self._heartbeat.start(self.on_heartbeat, self.heartbeat_timeout,
                self.heartbeat_timeout)
        self._heartbeat.unref()

    def on_close(self):
        self.active = False
        self.closed = True
        self._heartbeat.stop()

    def on_error(self, cb):
        self._on_error_cb = cb

    def on_message(self, raw):
        msg = decode_frame(raw)
        if msg.type in (FRAME_ERROR_TYPE, FRAME_RESPONSE_TYPE):
            # did we received an error?
            error = None
            result = None
            if msg.type == FRAME_ERROR_TYPE:
                error = json.loads(msg.body.decode('utf-8'))
                self.close()
            else:
                result = msg.body

            if msg.id == "gaffer_error":
                if self._on_error_cb is not None:
                    return self._async_callback(self._on_error_cb)(self, error)

            # handle message callback if any
            try:
                callback = self.pending.pop(msg.id)
            except KeyError:
                return

            self._async_callback(callback)(self, result, error)

        elif msg.type == FRAME_MESSAGE_TYPE:
            if self._read_callback is not None:
                self._async_callback(self._read_callback)(self, msg.body)

    def on_heartbeat(self, h):
        # on heartbeat send a nop message to the channel
        # it will maintain the connection open
        self.ping()
