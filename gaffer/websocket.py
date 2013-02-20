# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import array
import base64
import functools
import hashlib
import logging
import os
import re
import socket
import struct
import sys
import time

import tornado.escape
from tornado import iostream
from tornado.httputil import HTTPHeaders
from tornado.util import bytes_type, b

from .tornado_pyuv import IOLoop, install
install()

from .loop import patch_loop
from .util import urlparse, ord_

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

        self.loop = patch_loop(loop)
        self._io_loop = IOLoop(_loop=loop)

        self.url = urlparse(url)
        self.host = self.url.hostname
        self.port = self.url.port or ports[self.url.scheme]
        self.path = self.url.path or '/'

        self.client_terminated = False
        self.server_terminated = False
        self._final_frame = False
        self._frame_opcode = None
        self._frame_length = None
        self._fragmented_message_buffer = None
        self._fragmented_message_opcode = None
        self._waiting = None

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
        self._write_frame(True, opcode, message)

    def ping(self):
        self._write_frame(True, 0x9, b'')

    def close(self):
        """Closes the WebSocket connection."""

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
        self.stream.io_loop.close(True)

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
        print("%r" % data)
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
