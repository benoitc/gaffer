# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import sys

from .base import Command
from ...httpclient import GafferNotFound

class Stop(Command):

    """
    usage: gaffer ps:stop [<args>]... [--app=appname] [--no-input]

      <args>  pid or job label

      --app=appname  name of the procfile application.
      --no-input        don't prompt a confirmation
    """

    name = "ps:stop"
    short_descr = "stop a process or pid"

    def run(self, config, args):
        appname = self.default_appname(config, args)
        server, procfile = config.get("server", "procfile")

        if not args['<args>']:
            if (not args["--no-input"] and
                    self.confirm("Do you want to stop all jobs in %r" %
                        appname)):

                apps = server.sessions()
                if appname not in apps:
                    raise RuntimeError("%r not found\n" % appname)

                #  stop all the jobs the complete app
                server.jobs_walk(lambda s, job: self._stop(s, job))
                print("==> all jobs in %r stopped" % appname)
        else:
            for name in args['<args>']:
                # confirm that we can stop this job or pid
                if (not args["--no-input"] and
                    not self.confirm("Do you want to stop %r" % name)):
                    continue

                if name.isdigit():
                    # we want to stop a process from a job
                    try:
                        process = server.get_process(int(name))
                    except GafferNotFound:
                        sys.stderr.write("%r not found\n" % name)
                        sys.stderr.flush()
                        continue
                    process.stop()
                else:
                    # we want to stop a job
                    appname, job_name = self.parse_name(name, appname)
                    if (self.use_procfile(config, appname) and
                            job_name not in procfile.cfg):
                        print("Ignore %r" % name)
                        continue

                    pname = "%s.%s" % (appname, job_name)
                    try:
                        job = server.get_job(pname)
                    except GafferNotFound:
                        sys.stderr.write("%r not found\n" % name)
                        sys.stderr.flush()
                        continue
                    job.stop()

                print("%r stopped" % name)

    def _stop(self, server, job):
        try:
            job.stop()
            print("job %r stopped" % job.name)
        except GafferNotFound:
            pass
