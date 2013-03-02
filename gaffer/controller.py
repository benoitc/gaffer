# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from .error import ProcessError, CommandError
from .process import ProcessConfig

COMMANDS_TABLE= {
        # generic commands
        "sessions": "sessions",
        "jobs": "jobs",
        "pids": "pids",
        # job config management commands
        "load": "load",
        "unload": "unload",
        "reload": "reload",
        "update": "update",
        # job commands
        "start_job": "start_job",
        "stop_job": "stop_job",
        "scale": "scale",
        "info": "info",
        "stats": "stats",
        "stopall": "stopall",
        "killall": "killall",
        "commit": "commit",
        # process commands
        "process_info": "process_info",
        "process_stats": "process_stats",
        "stop_process": "stop_process",
        "send": "send",
        "kill": "kill"}


class Command(object):

    def __init__(self, name, args=None, kwargs=None):
        self.name = name
        self.args = args or ()
        self.kwargs = kwargs or {}

    def reply(self, result):
        raise NotImplementedError

    def reply_error(self, error):
        raise NotImplementedError

class Controller(object):
    """ a controller is class that allows a client to pass commands to the
    manager asynchronously. It should be the main object used by plugins and
    is used to pass command using a websocket.

    The main method to call is `process_command` it accept a `Command`
    instance. This instance will be passed to accepted commands by the
    controller. Arguments and Named arguments of the manager are passed via
    the command instance properties """

    def __init__(self, manager):
        self.manager = manager

    def process_command(self, cmd):
        if cmd.name not in COMMANDS_TABLE:
            cmd.reply_error({"errno": 404, "reason": "command_not_found"})
            return

        try:
            fun = getattr(self, COMMANDS_TABLE[cmd.name])
            fun(cmd)
        except ProcessError as pe:
            cmd.reply_error({"errno": pe.errno, "reason": pe.reason})
        except CommandError as ce:
            cmd.reply_error({"errno": ce.errno, "reason": ce.reason})
        except Exception as e:
            cmd.reply_error({"errno": 500, "reason": str(e)})

    def sessions(self, cmd):
        cmd.reply({"sessions": self.manager.sessions})

    def jobs(self, cmd):
        if not cmd.args:
            cmd.reply({"jobs": self.manager.jobs()})
        else:
            sessionid = cmd.args[0]
            jobs = self.manager.jobs(sessionid)
            cmd.reply({"sessionid": sessionid, "jobs": jobs})

    def pids(self, cmd):
        if not cmd.args:
            cmd.reply({"pids": self.manager.pids()})
        else:
            sessionid = cmd.args[0]
            pids = self.manager.pids(sessionid)
            cmd.reply({"sessionid": sessionid, "pids": pids})

    def load(self, cmd):
        if not cmd.args:
            raise CommandError("config_missing")

        config = cmd.args[0]
        if not isinstance(config, dict):
            raise CommandError("invalid_config")

        pconfig = ProcessConfig.from_dict(config)
        self.manager.load(pconfig, **cmd.kwargs)
        cmd.reply({"ok": True})

    def unload(self, cmd):
        if not cmd.args:
            raise CommandError()

        self.manager.unload(cmd.args[0], **cmd.kwargs)
        cmd.reply({"ok": True})


    def reload(self, cmd):
        if not cmd.args:
            raise CommandError()

        self.manager.reload(cmd.args[0], **cmd.kwargs)
        cmd.reply({"ok": True})


    def update(self, cmd):
        if not cmd.args:
            raise CommandError("config_missing")

        config = cmd.args[0]
        if not isinstance(config, dict):
            raise CommandError("invalid_config")

        pconfig = ProcessConfig.from_dict(config)
        self.manager.update(pconfig, **cmd.kwargs)
        cmd.reply({"ok": True})

    def start_job(self, cmd):
        if not cmd.args:
            raise CommandError()

        self.manager.start_job(cmd.args[0])
        cmd.reply({"ok": True})

    def stop_job(self, cmd):
        if not cmd.args:
            raise CommandError()

        self.manager.stop_job(cmd.args[0])
        cmd.reply({"ok": True})

    def commit(self, cmd):
        if not cmd.args:
            raise CommandError()

        pid = self.manager.commit(cmd.args[0], *cmd.args[1:])
        cmd.reply({"ok": True, "pid": pid})


    def scale(self, cmd):
        if len(cmd.args) < 2:
            raise CommandError()

        numprocesses = self.manager.scale(cmd.args[0], cmd.args[1])
        cmd.reply({"numprocesses": numprocesses})

    def info(self, cmd):
        if not cmd.args:
            raise CommandError()

        cmd.reply({"info": self.manager.info(cmd.args[0])})

    def stats(self, cmd):
        if not cmd.args:
            raise CommandError()

        cmd.reply({"stats": self.manager.stats(cmd.args[0])})

    def stopall(self, cmd):
        if not cmd.args:
            raise CommandError()

        self.manager.stopall(cmd.args[0])
        cmd.reply({"ok": True})

    def killall(self, cmd):
        if len(cmd.args) < 2:
            raise CommandError()

        self.manager.killall(cmd.args[0], cmd.args[1])
        cmd.reply({"ok": True})

    def process_info(self, cmd):
        if not cmd.args:
            raise CommandError()

        process = self.manager.get_process(cmd.args[0])
        cmd.reply({"info": process.info})

    def process_stats(self, cmd):
        if not cmd.args:
            raise CommandError()

        process = self.manager.get_process(cmd.args[0])
        cmd.reply({"stats": process.stats})

    def stop_process(self, cmd):
        if not cmd.args:
            raise CommandError()

        self.manager.stop_process(cmd.args[0])
        cmd.reply({"ok": True})

    def kill(self, cmd):
        if len(cmd.args) < 2:
            raise CommandError()

        self.manager.kill(cmd.args[0], cmd.args[1])
        cmd.reply({"ok": True})

    def send(self, cmd):
        if len(cmd.args) < 2 or len(cmd.args) > 3:
            raise CommandError()

        self.manager.send(*cmd.args)
        cmd.reply({"ok": True})
