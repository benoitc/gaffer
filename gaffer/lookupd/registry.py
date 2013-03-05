# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from collections import OrderedDict
from threading import RLock
import time

import pyuv

from ..events import EventEmitter
from ..util import parse_job_name


class NoIdent(Exception):
    """ exception raised when the not hasn't send its identity """

class JobNotFound(Exception):
    """ exception raised when a job isn't registered for a node """

class AlreadyIdentified(Exception):
    """ exception raised when a job is already identified """

class IdentExists(Exception):
    """ exception raised a node has already been registered with this hostname
    """

class AlreadyRegistered(Exception):
    """ exception raised when a job is alreay registered """


class RemoteJob(object):

    def __init__(self, node, name):
        self.node = node
        self.name = name
        self._pids = set()

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self.name)

    @property
    def pids(self):
        return list(self._pids)

    def add(self, pid):
        self._pids.add(pid)

    def remove(self, pid):
        try:
            self._pids.remove(pid)
        except KeyError:
            return


class GafferNode(object):
    """ class to maintain jobs & process / nodes """

    def __init__(self, conn):
        self.conn = conn
        self.sessions = dict()
        self.update()
        self.name = None
        self.origin = None
        self.version = None

    def __str__(self):
        return "node: %s" % self.name

    def identify(self, name, origin, version):
        self.name = name
        self.origin = origin
        self.version = version
        self.update()

    def update(self):
        self.updated = time.time()

    def add_job(self, job_name):
        sessionid, name = parse_job_name(job_name)

        if sessionid in self.sessions:
            session = self.sessions[sessionid]
        else:
            session = self.sessions[sessionid] = {}

        if name in session:
            raise AlreadyRegistered("job %r is already registered" % job_name)

        session[name] = RemoteJob(self, job_name)
        self.update()

    def remove_job(self, job_name):
        """ remove the job registered for this node """
        sessionid, name = parse_job_name(job_name)
        if sessionid not in self.sessions:
            return

        # remove the job if it exists
        session = self.sessions[sessionid]
        try:
            del session[name]
        except KeyError:
            return

        # if session is empty, remove it from the list
        if not session:
            try:
                del self.sessions[sessionid]
            except KeyError:
                return

        self.update()

    def add_process(self, job_name, pid):
        job = self.get_job(job_name)
        job.add(pid)
        self.update()

    def remove_process(self, job_name, pid):
        job = self.get_job(job_name)
        if pid in job.pids:
            job.remove(pid)
            return True
        return False
        self.update()

    def get_job(self, job_name):
        sessionid, name = parse_job_name(job_name)

        try:
            session = self.sessions[sessionid]
        except KeyError:
            raise JobNotFound()

        try:
            job = session[name]
        except KeyError:
            raise JobNotFound()

        return job

    def to_dict(self):
        info = self.infodict()
        sessions = {}
        for sessionid, job in self.sessions.items():
            sessions[sessionid] = { "job_name": job.name, "pids": job.pids }

        info['sessions'] = sessions
        return info

    def infodict(self):
        return dict(name=self.name, origin=self.origin, version=self.version)


class Registry(object):

    def __init__(self, loop=None):
        self.loop = loop or pyuv.Loop.default_loop()
        self.nodes = OrderedDict()
        self._emitter = EventEmitter(self.loop)
        self._lock = RLock()

    def close(self):
        self._emitter.close()

    def bind(self, event, callback):
        self._emitter.subscribe(event, callback)

    def unbind(self, event, callback):
        self._emitter.unsubscribe(event, callback)

    def bind_all(self, callback):
        self._emitter.subscribe(".", callback)

    def unbind_all(self, callback):
        self._emitter.unsubscribe(".", callback)

    def add_node(self, conn):
        """ register a connection. """
        with self._lock:
            node = self.nodes[conn] = GafferNode(conn)
            self._emitter.publish('add_node', node)
            return node

    def remove_node(self, conn):
        """ remove a connection from the registry """
        with self._lock:
            try:
                node = self.nodes.pop(conn)
                node.sessions = {}
                self._emitter.publish('remove_node', node)
            except KeyError:
                pass

    def identify(self, conn, name, origin, version):
        """ identify a node """
        with self._lock:
            # check if we already identified this node
            if self.nodes[conn].name is not None:
                raise AlreadyIdentified()

            # check if we already identified a node with this identity
            for _, node in self.nodes.items():
                if node.name == name and node.origin == origin:
                    raise IdentExists()

            self.nodes[conn].identify(name, origin, version)
            self._emitter.publish('identify', self.nodes[conn])


    def update(self, conn):
        with self._lock:
            # we can update a non identified Node
            if not conn in self.nodes:
                return
            self.nodes[conn].update()

    def all_nodes(self):
        """ get all identified nodes """
        with self._lock:
            nodes = [node for _, node in self.nodes.items() if node is not None]
            return nodes

    def get_node(self, conn):
        """ get a node """
        with self._lock:
            return self._get_node(conn)

    def sessions(self, with_node='*'):
        """ get all sessions from the registry. If ``with_node != '*'`` then
        only the sessions for this node will be returned. """
        if not with_node:
            raise ValueError("with_node should be '*' or a node identity")

        with self._lock:
            sessions = OrderedDict()
            for _, node in self.nodes.items():
                # if the node isn't identified, continue
                if node is None:
                    continue

                # if we filter by node, check if we can add the session
                if with_node != '*' and node.name != with_node:
                    continue

                for sessionid, jobs in node.sessions.items():
                    if not sessionid in sessions:
                        sessions[sessionid] = {}

                    for _, job in jobs.items():
                        if job.name not in sessions[sessionid]:
                            sessions[sessionid][job.name] = []
                        sessions[sessionid][job.name].append(job)

            return sessions

    def find_session(self, sessionid):
        with self._lock:
            all_jobs = []
            for _, node in self.nodes.items():
                # if the node isn't identified, continue
                if node is None:
                    continue
                for session, jobs in node.sessions.items():
                    if sessionid == session:
                        for _, job in jobs.items():
                            all_jobs.append(job)
                        break
            return all_jobs

    def node_by_name(self, name):
        """ get a node by its identity """
        with self._lock:
            nodes = []
            for node in self.nodes:
                if node is None:
                    continue

                if node.name == name:
                    nodes.append(node)
            return nodes

    def find_job(self, job_name):
        """ find a job in the registry, return a list of all remote job
        possible for this ``sessionid.name`` """
        sessionid, name = parse_job_name(job_name)
        with self._lock:
            jobs = []
            for _, node in self.nodes.items():
                # is not identified?
                if node is None:
                    continue

                # does this node support this session?
                if sessionid not in node.sessions:
                    continue

                # finally does this session support this job?
                if name not in node.sessions[sessionid]:
                    continue

                jobs.append(node.sessions[sessionid][name])

            if not jobs:
                raise JobNotFound()
            return jobs

    def jobs(self):
        """ return all remote jobs by their name """
        with self._lock:
            all_jobs = OrderedDict()
            for _, node in self.nodes.items():
                # is not identified?
                if node is None:
                    continue

                for sessionsid, jobs in node.sessions.items():
                    for _, job in jobs.items():
                        if job.name not in all_jobs:
                            all_jobs[job.name] = []

                        all_jobs[job.name].append(job)
            return all_jobs

    def add_job(self, conn, job_name):
        """ add a job to the registry """
        with self._lock:
            node = self._get_node(conn)
            node.add_job(job_name)
            event = {"node": self.nodes[conn], "job_name":  job_name}
            self._emitter.publish('add_job', event)

    def remove_job(self, conn, job_name):
        """ remove a job from the registry """
        with self._lock:
            node = self._get_node(conn)
            node.remove_job(job_name)
            event = {"node": self.nodes[conn], "job_name":  job_name}
            self._emitter.publish('remove_job', event)


    def add_process(self, conn, job_name, pid):
        """ add a process for this job """
        with self._lock:
            node = self._get_node(conn)
            node.add_process(job_name, pid)
            event = {"node": self.nodes[conn], "job_name":  job_name,
                    "pid": pid}
            self._emitter.publish('add_process', event)

    def remove_process(self, conn, job_name, pid):
        """ remove a process for this job """
        with self._lock:
            node = self._get_node(conn)
            # only send an event if we removed the process. It can also means
            # that the process has already been unregistered.
            if node.remove_process(job_name, pid):
                event = {"node": self.nodes[conn], "job_name":  job_name,
                    "pid": pid}
                self._emitter.publish('remove_process', event)

    ### private functions

    def _get_node(self, conn):
        node = self.nodes[conn]
        if node.name is None:
            raise NoIdent("need to send IDENTIFY message first")
        return node
