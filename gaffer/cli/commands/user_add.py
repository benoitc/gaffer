# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
from getpass import getpass

try:
    input = raw_input
except NameError:
    pass

from ...gafferd.util import confirm
from ...httpclient.base import GafferConflict
from ...httpclient.users import Users
from .base import Command

class UserAdd(Command):
    """
    usage: gaffer user:add [<username>] [-p PASSWORD] [-k KEY] [-t TYPE]

      <username>  name of the user

      -p PASSWORD  the user password
      -k KEY       the user API key
      -t TYPE      the user type [default 1].
    """

    name = "user:add"
    short_descr = "add a user"

    def run(self, config, args):
        server = config.get('server')

        username = args['<username>']
        password = args['-p']
        api_key = args['-k']
        user_type = args["-t"]

        try:
            if username is None:
                while True:
                    username = input("username: ")
                    if username and username is not None:
                        break

                    print("username is empty. Please enter a username.")

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

                    print("Passwords are different.")

            if api_key is None:
                api_key = input("api key: ")
                if not api_key:
                    api_key = None

            if user_type is None or not user_type.isdigit():

                while True:
                    user_type = input("type [1]: ")
                    if user_type.isdigit() or not user_type:
                        break
                    print("invalid user type")


        except KeyboardInterrupt:
            return

        if not user_type:
            user_type = "1"

        print("")
        print("Creating the user %r with the following infos:" % username)
        print("API Key: %s" % api_key)
        print("Type: %s" % user_type)
        print("")

        if not confirm("Confirm the creation of the user %r" % username):
            return

        users = Users(server)
        try:
            user = users.create_user(username, password,
                    user_type=int(user_type), key=api_key)
        except GafferConflict:
            raise RuntimeError("User %r alerady exists" % username)


        print("User %r created" % username)
