from gaffer import Plugin

__plugins__ = ['DummyPlugin']

class DummyApp(object):

    def start(self, loop, manager):
        print("start dummy app")

    def stop(sef):
        print("stop dummy")

    def rester(self):
        print("restart dummy")

class DummyPlugin(Plugin):
    name = "dummy"
    version = "1.0"
    description = "test"


    def app(self, cfg):
        return DummyApp()
