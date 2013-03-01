# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from ...httpclient import GafferNotFound
from .base import Command

class Info(Command):
    """
    usage: gaffer ps:info <target>  [--app APP]

      <target> job name or process id

      -h, --help
      --app APP  application name
    """

    name = "ps:info"
    short_descr = "get job info"

    def run(self, config, args):
        if args['<target>'].isdigit():
            # get a process info
            try:
                p = config.server.get_process(int(args['<target>']))
            except GafferNotFound:
                raise RuntimeError('process %r not found' % args['<target>'])

            lines = ["%s: %s" % (k, v) for k, v in p.info.items()]
        else:
            # get a job info
            appname, name = self.parse_name(args['<target>'],
                    self.default_appname(config, args))

            try:
                job = config.server.get_job("%s.%s" % (appname, name))
            except GafferNotFound:
                raise RuntimeError('job %r not found' % args['<target>'])
            info = job.info()
            pids = [str(pid) for pid in info['processes']]

            lines = ["active: %s" % info['active'],
                     "running: %s" % info['running'],
                     "num_processes: %s" % info['max_processes'],
                     "pids: %s" % ",".join(pids)]

        # finally print the result
        print("\n".join(lines))

