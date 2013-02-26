# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command
from ...httpclient import GafferNotFound

class Scale(Command):
    """
    usage: gaffer ps:scale [--app=appname] (<args>)...

      --app=appname  name of the procfile application.
    """

    name = "ps:scale"
    short_descr = "scaling your process"

    def run(self, config, args):
        appname = self.default_appname(config, args)
        server, procfile = config.get("server", "procfile")
        use_procfile = self.use_procfile(config, appname)
        ops = self.parse_scaling(args["<args>"])

        for name, op, val in ops:
            appname, name = self.parse_name(name, default=appname)
            pname = "%s.%s" % (appname, name)

            # if we are using a procfile check first if the app contains this
            # job. We don't need to make an HTTP request in this case.
            if use_procfile and name not in procfile.cfg:
                continue

            try:
                job = server.get_job(pname)
                ret = job.scale("%s%s" % (op, val))
                print("Scaling %s processes... done, now running %s" %
                        (pname,ret))
            except GafferNotFound:
                print("%r not found" % pname)

    def parse_scaling(self, args):
        ops = []
        for arg in args:
            if "=" in arg:
                op = "="
            elif "+" in arg:
                op = "+"
            elif "-" in arg:
                op = "-"

            k,v = arg.split(op)
            try:
                v = int(v)
            except:
                continue

            ops.append((k, op, v))
        return ops
