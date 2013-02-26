# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
from .base import Command
from ...httpclient import GafferNotFound

class kill(Command):

    """
    usage: gaffer ps:kill <proc> <sig> [--app=appname] [--no-input]

      <proc>  pid or job label
      <sig>   signal number or signal name

      --app=appname  name of the procfile application.
      --no-input        don't prompt a confirmation
    """

    name = "ps:kill"
    short_descr = "send a signal to a process or pid"

    def run(self, config, args):
        appname = self.default_appname(config, args)
        server, procfile = config.get("server", "procfile")
        name = args['<proc>']

        if name.isdigit():
            # we want to stop a process from a job
            try:
                process = server.get_process(int(name))
            except GafferNotFound:
                raise RuntimeError("%r not found" % name)
            process.kill(args['<sig>'])
        else:
            # we want to stop a job
            appname, job_name = self.parse_name(name, appname)
            if (self.use_procfile(config, appname) and
                    job_name not in procfile.cfg):
                raise RuntimeError("%r not found" % name)

            pname = "%s.%s" % (appname, name)
            try:
                job = server.get_job(pname)
            except GafferNotFound:
                raise RuntimeError("%r not found" % name)
            job.kill(args['<sig>'])

        print("%r sent to %r" % (args['<sig>'], name))
