# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from ...lookupd.client import LookupServer
from .base import Command

import pyuv

class LookupSessions(Command):
    """
    usage: gaffer lookup:sessions [<nodeid>] (-L ADDR|--lookupd-address=ADDR)...

      <node>  a gafferd id

      -h, --help
      -L ADDR --lookupd-address=ADDR  lookupd HTTP address
    """

    name = "lookup:sessions"
    short_descr = "list all sessions in lookupd servers"


    def run(self, config, args):
        lookupd_addresses = set(args['--lookupd-address'])

        sessions = {}
        loop = pyuv.Loop.default_loop()
        for addr in lookupd_addresses:
            s = LookupServer(addr, loop=loop, **config.client_options)
            if args['<nodeid>']:
                resp = s.sessions(args['<nodeid>'])
            else:
                resp = s.sessions()

            for session in resp['sessions']:
                sid = session['sessionid']
                if sid not in sessions:
                     sessions[sid] = session["jobs"]
                else:
                    current_jobs = sessions[sid]
                    new_jobs = session["jobs"]

                    for job_name, new in new_jobs.items():
                        if job_name in current_jobs:
                            current = current_jobs[job_name]
                            sessions[sid][job_name] = list(set(current + new))
        loop.run()

        print("%s session(s) found\n" % len(sessions))
        for sid, jobs in sessions.items():
            lines = ["*** session: %s" % sid, ""]
            for job_name, sources in jobs.items():
                lines.extend(["=== job: %s" % job_name])
                for source in sources:
                    version = source['node_info']['version']
                    name = source['node_info']['name']
                    origin = source['node_info']['origin']

                    lines.append("%s - name: %s, protocol: %s" % (origin,
                        name, version))
                lines.append("")
            print("\n".join(lines))
