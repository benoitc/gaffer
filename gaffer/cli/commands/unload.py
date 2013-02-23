# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command

class UnLoad(Command):
    """
    usage: gaffer unload [<appname>]

      <appname>  name of the application recorded in hafferd. By default it
                 will be the name of your project folder. You can use ``.``
                 to specify the current folder. [default: .].
    """

    name = "unload"
    short_descr = "unload a Procfile application from a gafferd node"

    def run(self, config, args):
        procfile, server = config.get("procfile", "server")
        appname = args['<appname>']
        if not appname or appname == ".":
            # get the default appname
            appname = procfile.get_appname()

        apps = server.sessions()
        if appname not in apps:
            raise RuntimeError("%r not found" % appname)

        # remove the group
        server.jobs_walk(lambda s, job: s.unload(job, appname))
        print("%r unloaded" % appname)
