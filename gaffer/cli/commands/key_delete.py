# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from ...gafferd.util import confirm
from ...httpclient.base import GafferNotFound
from ...httpclient.keys import Keys
from .base import Command

class KeyDelete(Command):
    """
    usage: gaffer key:delete <apikey>

      <apikey> the KEY to delete

    """

    name = "key:delete"
    short_descr = "Delete a key"

    def run(self, config, args):
        server = config.get('server')
        try:
            if not confirm("Delete the key %r" % args['<apikey>']):
                return
        except KeyboardInterrupt:
            return

        keys = Keys(server)
        try:
            key = keys.delete_key(args['<apikey>'])
        except GafferNotFound:
            raise RuntimeError("Key %r not found" % args['<apikey>'])
        print("The key %r has been deleted." % args['<apikey>'])
