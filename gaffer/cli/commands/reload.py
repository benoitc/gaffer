# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import sys

from .base import Command
from ...httpclient import GafferNotFound

class Reload(Command):
    """
    usage: gaffer reload [<jobs>]... [--app APP] [--from-file JSON]
                         [--no-input]

      --app APP         name of the procfile application.
      --no-input        don't prompt a confirmation
      --from-file JSON  unload from a JSON config file
    """

    name = "reload"
    short_descr = "reload a job from a gafferd node"

    def run(self, config, args):
        appname = self.default_appname(config, args)
        server, procfile = config.get('server', 'procfile')

        if not args['<jobs>'] and not args['--from-file']:
            # unload from a procfile
            if not args["--no-input"]:
                if not self.confirm("Do you want to reload %r?" % appname):
                    return
            apps = server.sessions()
            if appname not in apps:
                raise RuntimeError("%r not found" % appname)

            # unload the complete app
            server.jobs_walk(lambda s, job: self._reload(s, job, appname))
            print("==> app %r reloaded" % appname)
        elif args['--from-file']:
            # unload from a JSON config file
            fname = args['--from-file']

            # load configs
            configs = self.load_jsonconfig(fname)

            # finally unload all jobs from the give config
            for conf in configs:
                try:
                    job_name = conf.pop('name')
                except KeyError:
                    raise ValueError("invalid job config")

                # parse job name and eventually extract the appname
                appname, name = self.parse_name(job_name,
                        self.default_appname(config, args))
                # always force the appname if specified
                if args['--app']:
                    appname = args['--app']

                # unload the job
                pname = "%s.%s" % (appname, name)
                if not args["--no-input"]:
                    if not self.confirm("Do you want to reload %r?" %
                            pname):
                        continue

                try:
                    server.reload(name, appname)
                    print("job %r reloaded" % pname)
                except GafferNotFound:
                    sys.stderr.write("%r not found in %r\n" % (name,
                        appname))
                    sys.stderr.flush()
        else:
            # unload all jobs given on the command line. it can be either a
            # job specified in the Procfile or any job in the gafferd node.
            for job_name in args['<jobs>']:
                appname, name = self.parse_name(job_name, appname)
                if (self.use_procfile(config, appname) and
                        name not in procfile.cfg):
                    print("Ignore %r" % name)
                    continue

                if not args["--no-input"]:
                    if not self.confirm("Do you want to reload %r?" %
                            job_name):
                        continue

                # unload the job
                try:
                    server.reload(name, appname)
                    print("job %r reloaded" % job_name)
                except GafferNotFound:
                    sys.stderr.write("%r not found in %r\n" % (job_name,
                        appname))
                    sys.stderr.flush()

    def _reload(self, server, job, appname):
        try:
            server.reload(job, appname)
            print("job %r reloaded" % job.name)
        except GafferNotFound:
            sys.stderr.write("%r not found in %r\n" % (job.name, appname))
            sys.stderr.flush()
