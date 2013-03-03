# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from ...lookupd.client import LookupServer
from .base import Command

import pyuv

class LookupJobs(Command):
    """
    usage: gaffer lookup:jobs (-L ADDR|--lookupd-address=ADDR)...

      -h, --help
      -L ADDR --lookupd-address=ADDR  lookupd HTTP address
    """

    name = "lookup:jobs"
    short_descr = "list all jobs in  lookupd servers"


    def run(self, config, args):
        lookupd_addresses = set(args['--lookupd-address'])

        loop = pyuv.Loop.default_loop()
        all_jobs = {}
        for addr in lookupd_addresses:
            s = LookupServer(addr, loop=loop)
            resp = s.jobs()

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
                port = source['node_info']['port']
                hostname = source['node_info']['hostname']
                broadcast_address = source['node_info']['broadcast_address']
                version = source['node_info']['version']
                uri = "http://%s:%s" % (broadcast_address, port)

                lines.append("%s - hostname: %s, protocol: %s" %
                        (uri, hostname, version))
            lines.append("")
            print("\n".join(lines))
