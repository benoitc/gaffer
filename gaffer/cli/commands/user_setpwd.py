# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from getpass import getpass

from ...gafferd.util import confirm
from ...httpclient.base import GafferNotFound
from ...httpclient.users import Users
from .base import Command

class UserSetPassword(Command):
    """
    usage: gaffer user:setpassword <username> [-p PASSWORD]

      <username>  name of the user

      -p PASSWORD  the user password
    """

    name = "user:setpassword"
    short_descr = "change the password of a user"

    def run(self, config, args):
        server = config.get('server')

        password = args['-p']
        try:
            if password is None:
                while True:
                    password = getpass("password: ")
                    if password and password is not None:
                        break
                    print("password is empty. Please enter a password.")

                # confirm password

                while True:
                    confirm_password = getpass("confirm password: ")
                    if confirm_password == password:
                        break
        except KeyboardInterrupt:
            return


        if not confirm("Confirm the change %s's password" % args['<username>']):
            return

        users = Users(server)
        try:
            user = users.set_password(args['<username>'], password)
        except GafferNotFound:
            raise RuntimeError("User %r not found" % args['<username>'])

        print("%s's password changed" % args['<username>'])
