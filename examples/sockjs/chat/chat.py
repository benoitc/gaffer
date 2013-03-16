# -*- coding: utf-8 -*-
"""
    Simple sockjs-tornado chat application. By default will listen on port 8080.
"""

from tornado import ioloop
import tornado.web

from gaffer import sockjs
from gaffer import tornado_pyuv

class IndexHandler(tornado.web.RequestHandler):
    """Regular HTTP handler to serve the chatroom page"""
    def get(self):
        self.render('index.html')


class ChatConnection(sockjs.SockJSConnection):
    """Chat connection implementation"""
    # Class level variable
    participants = set()

    def on_open(self, info):
        # Send that someone joined
        self.broadcast(self.participants, "Someone joined.")

        # Add client to the clients list
        self.participants.add(self)

    def on_message(self, message):
        # Broadcast message
        self.broadcast(self.participants, message)

    def on_close(self):
        # Remove client from the clients list and broadcast leave message
        self.participants.remove(self)

        self.broadcast(self.participants, "Someone left.")

if __name__ == "__main__":
    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    import pyuv
    from gaffer.tornado_pyuv import IOLoop

    loop = pyuv.Loop.default_loop()
    ioloop = IOLoop(_loop=loop)

    # 1. Create chat router
    ChatRouter = sockjs.SockJSRouter(ChatConnection, '/chat',
            io_loop=ioloop)

    # 2. Create Tornado application
    app = tornado.web.Application(
            [(r"/", IndexHandler)] + ChatRouter.urls
    )

    # 3. Make Tornado app listen on port 8080
    app.listen(8080, io_loop=ioloop)

    # 4. Start IOLoop
    while True:
        try:
            if not loop.run(pyuv.UV_RUN_ONCE):
                break
        except KeyboardInterrupt:
            break
