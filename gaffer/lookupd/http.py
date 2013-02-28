# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.
import json

from tornado.web import Application
from tornado.httpserver import HTTPServer

from gaffer import __version__
from ..gafferd.http_handlers import sockjs
from ..gafferd.http_handlers.util import CorsHandler


from .protocol import LookupWebSocket
from .registry import Registry, JobNotFound


def http_server(io_loop, listener, ssl_options=None, registration_db=None):

    # initialize the registry
    registration_db = registration_db or Registry(loop=io_loop._loop)

    # lookup routes
    user_settings = { "registration_db": registration_db }
    lookup_router = sockjs.SockJSRouter(LookupConnection, "/lookup",
            io_loop=io_loop, user_settings=user_settings)

    # initialize handlers
    handlers = [
            (r'/', WelcomeHandler),
            (r'/ping', PingHandler),
            (r'/version', VersionHandler),
            (r'/nodes', NodesHandler),
            (r'/sessions', SessionsHandler),
            (r'/sessions/([^/]+)', SessionsHandler),
            (r'/jobs', JobsHandler),
            (r'/findJob', FindJobHandler),
            (r'/ws', LookupWebSocket)] + lookup_router.urls

    # initialize the server
    app = Application(handlers, registration_db=registration_db)
    server = HTTPServer(app, io_loop=io_loop, ssl_options=ssl_options)
    server.add_sockets(listener)
    return server



class WelcomeHandler(CorsHandler):

    def get(self):
        self.preflight()
        self.write({"welcome": "gaffer-lookupd", "version": __version__})


class VersionHandler(CorsHandler):

    def get(self):
        self.preflight()
        self.write({"version": __version__})


class PingHandler(CorsHandler):

    def get(self):
        self.preflight()
        self.set_status(200)
        self.write("OK")


class LookupConnection(sockjs.SockJSConnection):

    def on_open(self, info):
        self.db = self.session.server.settings.get('registration_db')
        self.db.bind_all(self.on_event)

    def on_close(self):
        self.db.unbind_all(self.on_event)

    def on_event(self, event, message):
        if event in ('add_node', 'remove_node', 'identify', ):
            message = message.infodict()
        else:
            message['node'] = message['node'].infodict()
        # add event to the message
        message['event'] = event
        self.write_message(message)

    def write_message(self, msg):
        if isinstance(msg, dict):
            self.send(json.dumps(msg))
        else:
            self.send(msg)

class NodesHandler(CorsHandler):

    def get(self, *args, **kwargs):
        self.preflight()
        db = self.settings.get('registration_db')

        registered = db.all_nodes()
        self.write({"nodes": [node.infodict() for node in registered]})


class SessionsHandler(CorsHandler):

    def get(self, *args, **kwargs):
        self.preflight()
        db = self.settings.get('registration_db')

        if len(args) > 0:
            node = args[0]
        else:
            node = '*'

        registered = db.sessions(with_node=node)

        sessions = []
        for sessionid, session_jobs in registered.items():
            all_jobs = {}
            for job_name, jobs in session_jobs.items():
                sources = [{"hostname": job.node.hostname,
                            "pids": job.pids,
                            "node_info": job.node.infodict()} for job in jobs]

                all_jobs[job_name] = sources
            sessions.append({"sessionid": sessionid, "jobs": all_jobs})

        self.write({"nb_sessions": len(sessions), "sessions": sessions})


class JobsHandler(CorsHandler):

    def get(self, *args, **kwargs):
        self.preflight()
        db = self.settings.get('registration_db')

        registered = db.jobs()

        all_jobs = []
        for job_name, jobs in registered.items():
            sources = [{"hostname": job.node.hostname,
                        "pids": job.pids,
                        "node_info": job.node.infodict()} for job in jobs]
            all_jobs.append({"name": job_name, "sources": sources})

        self.write({"nb_jobs": len(all_jobs), "jobs": all_jobs})


class FindJobHandler(CorsHandler):

    def get(self, *args, **kwargs):
        self.preflight()
        db = self.settings.get('registration_db')

        job_name = self.get_argument("name")
        try:
            found = db.find_job(job_name)
        except JobNotFound:
            self.set_status(404)
            return self.write({"error": "not_found"})

        jobs = []
        for job in found:
            jobs.append({"hostname": job.node.hostname, "pids": job.pids,
                "node_info": job.node.infodict()})

        self.write({"sources": jobs})
