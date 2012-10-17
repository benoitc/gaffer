# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from datetime import datetime
import copy
import sys

from .base import Command
from gaffer.console_output import colored, GAFFER_COLORS
from gaffer.sig_handler import BaseSigHandler

class SigHandler(BaseSigHandler):

    def start(self, loop, watcher):
        self.watcher = watcher
        super(SigHandler, self).start(loop)

    def stop(self):
        try:
            self._sig_handler.stop()
        except:
            pass

        self.watcher.stop()

    def handle_quit(self, handle, *args):
        self.stop()

    def handle_reload(self, handle, *args):
        self.stop()


class Watch(Command):
    """\
        Watch changes in gaffer
        =======================

        This command allows you to watch changes n a locla or remote
        gaffer node.


        .. image:: ../_static/gaffer_watch.png


        HTTP Message
        ------------

        ::

            HTTP/1.1 GET /watch/<p1>[/<p2>/<p3>]

        It accepts the following query parameters:

        - **feed** : continuous, longpoll, eventsource
        - **heartbeat**: true or seconds, send an empty line each sec
          (if true 60)

        Ex::

            $ curl "http://127.0.0.1:5000/watch?feed=eventsource&heartbeat=true"
            event: exit
            data: {"os_pid": 3492, "exit_status": 0, "pid": 1, "event": "exit", "term_signal": 0, "name": "priority0"}
            event: exit
            event: proc.priority0.exit
            ...


        The path passed can be any accepted patterns by the manager :

        - ``create`` will become ``http://127.0.0.1:5000/watch/create``
        - ``proc.dummy`` will become ``http://127.0.0.1:5000/watch/proc/dummy``

        ...

        Accepted genetic patterns
        +++++++++++++++++++++++++

        =====================  =========================================
        Patterns               Description
        =====================  =========================================
        create                 to follow all templates creattion
        start                  start all processes in a tpl
        stop                   all processes in a tpl are stopped
        restart                restart all processes in a tpl
        update                 update a tpl (can happen on add/sub)
        spawn                  a new process is spawned
        reap                   a process is reaped
        exit                   a process exited
        stop_pid               a process has been stopped
        proc.<name>.start      process template with <name> start
        proc.<name>.stop       process template with <name> stop
        proc.<name>.stop_pid   a process from <name> is stopped
        proc.<name>.spawn      a process from <name> is spawned
        proc.<name>.exit       a process from <name> exited
        proc.<name>.reap       a process from <name> has been reaped
        =====================  =========================================


        Command line:
        -------------

        ::

            gafferctl watch <p1>[.<p2>.<p3>] 

        .. note::

            <p1[2,3]> are the parts of the parttern separrated with a
            '.' .

        Options:

        - **heartbeat**: by default true, can be an int
        - **colorize**: by default true: colorize the output

    """
    name = "watch"

    options = [
            ('', 'heartbeat', 60, "define connection heartbeat"),
            ('', 'colorize', True, "return colorized output")
    ]

    args = ["pattern"]

    def run(self, server, args, options):

        heartbeat = options.get('heartbeat', 60)
        self.colorize = options.get('colorize', True)

        if not args:
            pattern = "."
        else:
            pattern = args[0].strip()

        self._balance = copy.copy(GAFFER_COLORS)
        self._process_colors = {}

        sig_handler = SigHandler()
        watcher = server.get_watcher(heartbeat=heartbeat)
        watcher.subscribe(pattern, self._on_event)
        watcher.start()
        sig_handler.start(watcher.loop, watcher)

        try:
            watcher.run()
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as e:
            sys.stderr.write(str(e))
            sys.stderr.flush()
        finally:
            watcher.stop()

        return ""

    def _on_event(self, event, msg):
        name = msg['name']
        if '_os_pid' in msg:
            line = self._print(name, '%s process with pid %s' % (event,
                msg['os_pid']))
        else:
            line = self._print(name, '%s %s' % (event, name))

        self._write(name, line)

    def _write(self, name, lines):
        if self.colorize:
            sys.stdout.write(colored(self._get_process_color(name), lines))
        else:
            sys.stdout.write(''.joint(lines))
        sys.stdout.flush()

    def _print(self, name, line):
        now = datetime.now().strftime('%H:%M:%S')
        prefix = '{time} {name} | '.format(time=now, name=name)
        return ''.join([prefix, line, '\n'])

    def _set_process_color(self, name):
        code = self._balance.pop(0)
        self._process_colors[name] = code
        self._balance.append(code)

    def _get_process_color(self, name):
        if name not in self._process_colors:
            self._set_process_color(name)
        return self._process_colors[name]
