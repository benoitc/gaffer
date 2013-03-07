from gaffer import Plugin

__all__ = ['DummyPlugin1']

class DummyApp1(object):

    def start(self, loop, manager):
        print("start dummy 1 app")

    def stop(sef):
        print("stop dummy 1")

    def restart(self):
        print("restart dummy")

class DummyPlugin1(Plugin):
    name = "dummy1"
    version = "1.0"
    description = "test"


    def app(self, cfg):
        return DummyApp1()
