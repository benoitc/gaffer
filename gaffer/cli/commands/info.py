# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command

class Info(Command):
    """
    usage: gaffer ps:info <job>  [--app APP]

      <job> job name

      -h, --help
      --app APP  application name
    """

    name = "ps:info"
    short_descr = "get job info"

    def run(self, config, args):
        appname, name = self.parse_name(args['<job>'],
                self.default_appname(config, args))
        job = config.server.get_job("%s.%s" % (appname, name))
        info = job.info()
        pids = [str(pid) for pid in info['processes']]

        lines = ["active: %s" % info['active'],
                 "running: %s" % info['running'],
                 "num_processes: %s" % info['max_processes'],
                 "pids: %s" % ",".join(pids)]

        print("\n".join(lines))

