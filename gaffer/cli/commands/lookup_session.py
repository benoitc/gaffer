# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from ...lookupd.client import LookupServer
from .base import Command

import pyuv

class LookupSession(Command):
    """
    usage: gaffer lookup:session <sid> (-L ADDR|--lookupd-address=ADDR)...

      <sid>  a session id (or application name)

      -h, --help
      -L ADDR --lookupd-address=ADDR  lookupd HTTP address
    """

    name = "lookup:session"
    short_descr = "list all jobs for a session in lookupd servers"


    def run(self, config, args):
        lookupd_addresses = set(args['--lookupd-address'])

        loop = pyuv.Loop.default_loop()
        all_jobs = {}
        for addr in lookupd_addresses:
            # connect to the lookupd server channel
            s = LookupServer(addr, loop=loop, **config.client_options)
            resp = s.find_session(args['<sid>'])

            for job in resp['jobs']:
                job_name = job['name']
                if job_name in all_jobs:
                    all_jobs[job_name] = list(
                            set(all_jobs[job_name] + job['sources'])
                    )
                else:
                    all_jobs[job_name] = job['sources']
        loop.run()
        print("%s job(s) found\n" % len(all_jobs))
        for job_name, sources in all_jobs.items():
            lines = ["=== %s" % job_name]

            for source in sources:
                name = source['node_info']['name']
                origin = source['node_info']['origin']
                version = source['node_info']['version']

                lines.append("%s - name: %s, protocol: %s" % (origin, name,
                    version))
            lines.append("")
            print("\n".join(lines))
