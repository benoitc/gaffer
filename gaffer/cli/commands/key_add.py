# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from ...gafferd.util import confirm
from ...httpclient.base import GafferConflict
from ...httpclient.keys import Keys
from .base import Command
from .key import display_permissions

class KeyCreate(Command):
    """
    usage: gaffer key:create <args>... [--label LABEL]

      <args> permission to add to this key.
      --label LABEL  the key label

    Arguments:

        +a: give admin right
        +u: give create_user permission
        +k: give create_key permission
        +m manage all

        <session>+rwm where r is for read, w for write and m for manage
            permissions. You can mix them or just use one of them. (ex.
            <session>+r will oonly give the read permission on the session)
        <session.jobname>+rwm

    Example:

        gaffer key:create default+rw test+m

    will create a key with read andwrite permission on the default session and
    manae permissions on the test session.
    """

    name = "key:create"
    short_descr = "Create a key"

    def run(self, config, args):
        server = config.get('server')

        # parse permissions
        permissions = {"admin": False, "create_user": False,
                "create_key": False, "manage": [], "read": [], "write": []}
        is_admin = False
        for arg in args['<args>']:
            if arg == "+a":
                permissions['admin'] = True
                is_admin = True
            elif arg == "+u":
                permissions['create_user'] = True
            elif arg == "+k":
                permissions['create_key'] = True
            elif arg == "+m":
                permissions['manage'].append('*')
            else:
                try:
                    target, perms = arg.split("+")
                except ValueError:
                    continue

                for c in perms:
                    if c == "m":
                        permissions['manage'].append(target)
                    elif c == "r":
                        permissions['read'].append(target)
                    elif c == "w":
                        permissions['write'].append(target)

        if is_admin:
            permissions['create_key'] = True
            permissions['create_user'] = True

        print("A key with the following permissions will be created:\n")
        display_permissions(permissions)
        print("")

        try:
            if not confirm("Create the key"):
                return
        except KeyboardInterrupt:
            return

        keys = Keys(server)
        try:
            key = keys.create_key(permissions, label=args['--label'])
        except GafferConflict:
            raise RuntimeError("The key already exists")
        print("The key %r has been created." % key)
