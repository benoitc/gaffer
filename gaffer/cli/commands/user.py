# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from ...httpclient.base import GafferNotFound
from ...httpclient.users import Users
from .base import Command

class User(Command):
    """
    usage: gaffer user <username>

      <username>  name of the user
    """

    name = "user"
    short_descr = "Fetch the user infos"

    def run(self, config, args):
        server = config.get('server')

        users = Users(server)
        try:
            user = users.get_user(args['<username>'])
        except GafferNotFound:
            raise RuntimeError("User %r not found" % args['<username>'])

        print("User %r found" % args['<username>'])
        print("API Key: %s" % user['key'])
