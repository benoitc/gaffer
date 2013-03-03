# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .base import Command
from ...httpclient import GafferNotFound


class Run(Command):
    """
    usage: gaffer run <job> [--graceful-timeout=TIMEOUT]
                            [--app=appname] [-p k=v]...

      <job>  job name: the config to use to launch this process

      -h --help
      -p k=v                 an environnemnt variable to add to the process  environmenet
      --graceful-timeout=T  graceful time before we send a  SIGKILL to the
                            process (which definitely kill it).  This is a time
                            we let to a process to exit cleanly.
      --app=appname         name of the procfile application (or session).

    """

    name = "run"
    short_descr = "run one-off command using a job config"

    def run(self, config, args):
        appname, name = self.parse_name(args['<job>'],
                default=self.default_appname(config, args))
        pname = "%s.%s" % (appname, name)
        server, procfile = config.get("server", "procfile")

        graceful_timeout = args['--graceful-timeout']
        if graceful_timeout is not None:
            if not graceful_timeout.isdigit():
                raise RuntimeError('invalid graceful timeout value')
            graceful_timeout = int(graceful_timeout)

        env = config.env.copy()
        env.update(self.parse_env(args))

        try:
            job = server.get_job(pname)
            pid = job.commit(graceful_timeout=graceful_timeout, env=env)
            print("%r: new process %r launched" % (pname, pid))
        except GafferNotFound:
            print("%r not found" % pname)

    def parse_env(self, args):
        if not args['-p']:
            return {}

        env = {}
        for kvs in set(args['-p']):
            kv = kvs.split("=")
            if len(kv) == 2:
                key = kv[0].strip()
                val = kv[1].strip()
                env[key] = val
        return env
