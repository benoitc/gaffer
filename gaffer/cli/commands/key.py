# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from ...httpclient.base import GafferNotFound
from ...httpclient.keys import Keys
from .base import Command

class Key(Command):
    """
    usage: gaffer key <apikey>

      <apikey> API key
    """

    name = "key"
    short_descr = "Fetch the key infos"

    def run(self, config, args):
        server = config.get('server')

        keys = Keys(server)
        try:
            key = keys.get_key(args['<apikey>'])
        except GafferNotFound:
            raise RuntimeError("Key %r not found" % args['<apikey>'])


        permissions = key.get('permissions', {})
        print("Key %r found." % args['<apikey>'])
        print("Label: %s" % key.get("label", ""))
        print("Permisssions:")
        display_permissions(permissions)

def display_permissions(permissions):
    is_admin = permissions.get('admin') == True
    print("  admin: %s" % permissions.get('admin', False))
    if is_admin:
        print("  create_user: True")
        print("  create_key: True")
        print("  manage: *")
        print("  read: *")
        print("  write: *")
    else:
        print("  create_key: %s" % permissions.get('create_key', False))
        print("  create_user: %s" % permissions.get('create_user',
            False))
        print("  manage: %s" % ",".join(permissions.get("manage", [])))
        print("  read: %s" % ",".join(permissions.get("read", [])))
        print("  write: %s" % ",".join(permissions.get("write", [])))
