# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from io import StringIO
import json
import sys

from .base import Command

class Export(Command):
    """
    usage: gaffer export [-c concurrency|--concurrency concurrency]...
                         [--format=format] [--out=filename] [<name>]

      -h, --help
      -c concurrency,--concurrency concurrency  Specify the number processesses
                                                to run.
      --format=format                           json or ini
      --out=filename
    """

    name = "export"
    short_descr = "export a Procfile"

    def run(self, config, args):
        concurrency = self.parse_concurrency(args)
        if args['--format'] == "json":
            if not args['<name>']:
                print("you should provide a process type to export")
                sys.exit(1)

            try:
                obj = config.procfile.as_dict(args["<name>"], concurrency)
            except KeyError:
                raise KeyError("%r is not found" % args["<name>"])

            if args['--out']:
                with open(args['--out'], 'w') as f:
                    json.dump(obj, f, indent=True)

            else:
                print(json.dumps(obj, indent=True))
        else:
            config = config.procfile.as_configparser(concurrency)
            if args['--out']:
                with open(args['--out'], 'w') as f:
                    config.write(f, space_around_delimiters=True)
            else:
                buf = StringIO()
                config.write(buf, space_around_delimiters=True)
                print(buf.getvalue())
