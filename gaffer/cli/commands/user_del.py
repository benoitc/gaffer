# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from ...gafferd.util import confirm
from ...httpclient.base import GafferNotFound
from ...httpclient.users import Users
from .base import Command

class UserDelete(Command):
    """
    usage: gaffer user:del <username>

      <username>  name of the user
    """

    name = "user:del"
    short_descr = "delete a user"

    def run(self, config, args):
        server = config.get('server')

        if not confirm("Confirm deletion of the user %r" % args['<username>']):
            return

        users = Users(server)
        try:
            user = users.delete_user(args['<username>'])
        except GafferNotFound:
            raise RuntimeError("User %r not found" % args['<username>'])

        print("User %r deleted" % args['<username>'])
