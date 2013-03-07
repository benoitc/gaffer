# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import copy
import importlib
import logging
import os
import sys

from tornado import web

class Plugin(object):
    """ basic plugin interfacce """

    name = ""
    version = "?"
    descripton = ""
    mandatory = []

    def app(self, cfg):
        """ return a gaffer application """
        return None


class PluginDir(object):

    def __init__(self, name, rootdir):
        self.name = name
        self.root = rootdir
        self.plugins = []
        self.names = []
        self.mandatory = []

        # load plugins
        self._scan()

        site_path = os.path.join(rootdir, '_site')
        if os.path.isdir(site_path):
            self.site = site_path
        else:
            self.site = None

        if not self.plugins and self.site is None:
            if os.path.isfile(os.path.join(rootdir, 'index.html')):
                self.site = rootdir


    def _scan(self):
        plugins = []
        dirs = []

        # initial pass, read
        for name in os.listdir(self.root):
            if name in (".", "..",):
                continue

            path = os.path.join(self.root, name)
            if (os.path.isdir(path) and
                    os.path.isfile(os.path.join(path, '__init__.py'))):
                # no conflict
                if path not in sys.path:
                    dirs.append((name, path))
                    sys.path.insert(0, os.path.join(self.root, '..',
                        name))
                    sys.path.insert(0, os.path.join(self.root,  name))

        for (name, d) in dirs:
            try:
                for f in os.listdir(d):
                    if f.endswith(".py") and f != "__init__.py":
                        plugins.append(("%s.%s" % (name, f[:-3]), d))
            except OSError:
                sys.stderr.write("error, loading %s" % f)
                sys.stderr.flush()
                continue

        mod = None
        for (name, d) in plugins:
            mod = importlib.import_module(name)
            if hasattr(mod, "__all__"):
                for attr in mod.__all__:
                    plug = getattr(mod, attr)
                    if issubclass(plug, Plugin):
                        self._load_plugin(plug())

    def _load_plugin(self, plug):
        if not plug.name:
            raise RuntimeError("invalid plugin: %s [%s]" % (self.name,
                self.root))

        self.plugins.append(plug)
        self.names.append(plug.name)
        self.mandatory.extend(plug.mandatory or [])


class PluginManager(object):

    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.plugins = {}
        self.installed = []

        self.apps = []
        # scan all plugins
        self.scan()

    def scan(self):
        if not os.path.isdir(self.plugin_dir):
            logging.info("plugging dir %r not found" % self.plugin_dir)
            return

        for name in os.listdir(self.plugin_dir):
            if name in (".", "..",):
                continue
            path = os.path.abspath(os.path.join(self.plugin_dir, name))
            if os.path.isdir(path):
                plug = PluginDir(name, path)
                self.plugins[name] = plug
                self.installed.extend(plug.names)

    def check_mandatory(self):
        sinstalled = set(self.installed)
        for name, plug in self.plugins.items():
            smandatory = set(plug.mandatory)
            diff = smandatory.difference(sinstalled)
            if diff:
                raise RuntimeError("%s requires %s to be used" % (name,
                    diff))

    def get_sites(self):
        handlers = []
        for name, plug in self.plugins.items():
            if plug.site is not None:
                static_path = r"/_plugin/%s/(.*)" % name
                rule = (static_path, web.StaticFileHandler,
                        {"path": plug.site,
                         "default_filename": "index.html"})
                handlers.append(rule)
        return handlers

    def init_apps(self, cfg):
        for name, plugdir in self.plugins.items():
            for plug in plugdir.plugins:
                app = plug.app(cfg)
                if app is not None:
                    self.apps.append((app, plug))
        return self.apps

    ### apps handling

    def start_apps(self, config, loop, manager):
        apps = self.init_apps(config)
        for app, _plug in apps:
            try:
                app.start(loop, manager)
            except Exception:
                # we ignore all exception
                logging.error('Uncaught exception when starting a plugin',
                        exc_info=True)

    def stop_apps(self):
        for app, _plug in self.apps:
            try:
                app.stop()
            except Exception:
                # we ignore all exception
                logging.error('Uncaught exception when stopping a plugin',
                        exc_info=True)

        self.apps = []

    def restart_apps(self, config, loop, manager):
        if not os.path.isdir(config.plugin_dir):
            # the new plugin dir isn't found
            logging.error("config error plugging dir %r not found" %
                    config.plugin_dir)

            if self.plugin_dir != config.plugin_dir:
                logging.info("stop all current plugins")
                self.stop_apps()
            return

        # save all states
        old_plugins = self.plugins.copy()
        old_installed = self.installed
        old_apps = copy.copy(self.apps)
        old_plugin_dir = self.plugin_dir

        # scan the plugin dir
        self.plugin_dir = config.plugin_dir
        self.scan()

        try:
            self.check_mandatory()
        except RuntimeError as e:
            # one dependency is missing, return
            logging.error("Failed to reload plugins: %s" % str(e))

            if self.plugin_dir != old_plugin_dir:
                logging.info("stop all current plugins")
                self.stop_apps()

            # reset values
            self.plugin_dir = old_plugin_dir
            self.plugins = old_plugins
            self.installed = old_installed
            self.apps = old_apps
            return

        # initialize new apps
        apps = self.init_apps(config)

        # stop removed plugins
        for ap in old_apps:
            if ap not in apps:
                app, _ = ap
                try:
                    app.stop()
                except Exception:
                     # we ignore all exception
                    logging.error('Uncaught exception when stopping a plugin',
                        exc_info=True)

        # start or restart plugins
        for app, plug in apps:
            try:
                if (app, plug) in old_apps:
                    app.restart()
                else:
                    app.start(loop, manager)
            except Exception:
                # we ignore all exception
                logging.error('Uncaught exception when (re)starting a plugin',
                        exc_info=True)
