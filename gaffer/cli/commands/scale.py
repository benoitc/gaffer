# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command
from ...httpclient import GafferNotFound

class Scale(Command):
    """
    usage: gaffer ps:scale [--app=appname] (<args>)...

      --app=appname  name of the procfile applicatino. [default: .]
    """

    name = "ps:scale"
    short_descr = "scaling your process"

    def run(self, config, args):
        procfile, server = config.get("procfile", "server")
        appname = args["--app"]
        if not appname or appname == ".":
            appname = procfile.get_appname()

        ops = self.parse_scaling(args["<args>"])
        for name, op, val in ops:
            if name in procfile.cfg:
                pname = "%s.%s" % (appname, name)

                try:
                    job = server.get_job(pname)
                    ret = job.scale("%s%s" % (op, val))
                    print("Scaling %s processes... done, now running %s" %
                            (name,ret))

                except GafferNotFound as e:
                    print("Ignore %s: %s" % (name, str(e)))
                    pass


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
