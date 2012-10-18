# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os

from .base import Command
from ...httpclient import Server

class Scale(Command):
    """\
        Scaling your process
        ====================

        Procfile applications can scal up or down instantly from the
        command line or API.

        Scaling a process in an application is done using the scale
        command:

        ::

            $ gaffer scale dummy=3
            Scaling dummy processes... done, now running 3

        Or both at once:

        ::

            $ gaffer scale dummy=3 dummy1+2
            Scaling dummy processes... done, now running 3
            Scaling dummy1 processes... done, now running 3


        Command line
        ------------

        ::

            $ gaffer scale [group] process[=|-|+]3


        Options
        +++++++

        **--endpoint**

            Gaffer node URL to connect.


        Operations supported are +,-,=

    """

    name = "scale"

    def run(self, procfile, pargs):
        args = pargs.args
        uri = pargs.endpoint or "http://127.0.0.1:5000"
        s = Server(uri)

        group = procfile.get_groupname()
        if len(args) > 1:
            if ("=" not in args[0] and
                    "+" not in args[0] and
                    "-" not in args[0]):
                group = args[0]

        ops = self.parse_scaling(args)
        for name, op, val in ops:
            if name in procfile.cfg:
                pname = "%s:%s" % (group, name)

                p = s.get_process(pname)
                if op == "=":
                    curr = p.numprocesses
                    if curr > val:
                        p.sub(curr - val)
                    else:
                        p.add(val - curr)
                elif op == "+":
                    p.add(val)
                else:
                    p.sub(val)
                print("Scaling %s processes... done, now running %s" % (name,
                    p.numprocesses))


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
