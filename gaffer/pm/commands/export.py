# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from io import StringIO
import json

from .base import Command

class Export(Command):
    """\
        Export a Procfile
        =================

        This command export a Procfile to a gafferd process settings
        format. It can be either a JSON that you could send to gafferd
        via the JSON API or an ini file that can be included to the
        gafferd configuration.

        Command Line
        ------------

        ::

            $ gaffer export [ini|json] [filename]

    """

    name = "export"

    def run(self, procfile, pargs):
        args = pargs.args
        concurrency = self.parse_concurrency(pargs)

        if len(args) < 1:
            raise RuntimeError("format is missing")

        if args[0] == "json":
            if len(args) < 2:
                raise RuntimeError("procname is missing")
            try:
                obj = procfile.as_dict(args[1], concurrency)
            except KeyError:
                raise KeyError("%r is not found" % args[1])

            if len(args) == 3:
                with open(args[2], 'w') as f:
                    json.dump(obj, f, indent=True)

            else:
                print(json.dumps(obj, indent=True))
        else:
            config = procfile.as_configparser(concurrency)
            if len(args) == 2:
                with open(args[1], 'w') as f:
                    config.write(f, space_around_delimiters=True)
            else:
                buf = StringIO()
                config.write(buf, space_around_delimiters=True)
                print(buf.getvalue())
