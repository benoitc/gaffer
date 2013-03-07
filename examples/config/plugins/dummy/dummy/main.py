from gaffer import Plugin

__all__ = ['DummyPlugin']

from .app import DummyApp


class DummyPlugin(Plugin):
    name = "dummy"
    version = "1.0"
    description = "test"


    def app(self, cfg):
        return DummyApp()
