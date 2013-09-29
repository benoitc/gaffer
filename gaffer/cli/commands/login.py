# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

try:
    input = raw_input
except NameError:
    pass

from getpass import getpass
import os
import sys

from ...httpclient import GafferUnauthorized
from .base import Command


class Login(Command):
    """
    usage: gaffer login [-u USERNAME] [-p PASSWORD]

      -u USERNAME  user name
      -p PASSWORD  password
    """

    name = "login"
    short_descr = "login to the gafferd node"

    def run(self, config, args):
        username = args["-u"]
        password = args["-p"]

        server = config.get("server")

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
        except KeyboardInterrupt:
            print("\nnot authenticated")
            return

        try:
            api_key = server.authenticate(username, password)
        except GafferUnauthorized:
            print("unauthorized: username or password is wrong")
            sys.exit(1)

        # store the key to use it later
        self.save_key(config, api_key)
        print("User %r authenticated." % username)

    def save_key(self, config, api_key):
        cfg = configparser.RawConfigParser()

        if os.path.isfile(config.user_config_path):
            with open(config.user_config_path) as f:
                cfg.readfp(f)

        section = "node \"%s\"" % config.server.uri

        if not cfg.has_section(section):
            cfg.add_section(section)

        cfg.set(section, "key", api_key)

        with open(config.user_config_path, 'w') as f:
            cfg.write(f)
