# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from getpass import getpass

try:
    input = raw_input
except NameError:
    pass

from ...gafferd.util import confirm
from ...httpclient.base import GafferNotFound
from ...httpclient.users import Users
from .base import Command

class UserSetPassword(Command):
    """
    usage: gaffer user:setkey <username> [-k KEY]

      <username>  name of the user

      -k KEY  the user key
    """

    name = "user:setkey"
    short_descr = "change the key of a user"

    def run(self, config, args):
        server = config.get('server')

        key = args['-k']
        try:
            if key is None:
                key = input("api key: ")
        except KeyboardInterrupt:
            return

        if not confirm("Confirm the change %s's key" % args['<username>']):
            return

        users = Users(server)
        try:
            user = users.set_key(args['<username>'], key)
        except GafferNotFound:
            raise RuntimeError("User %r not found" % args['<username>'])

        print("%s's key changed" % args['<username>'])
