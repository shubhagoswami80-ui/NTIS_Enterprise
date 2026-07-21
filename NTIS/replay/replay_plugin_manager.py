"""
=========================================================
NTIS Replay Plugin Manager
Version : 1.0
Purpose :
    Register, manage and execute
    Replay Engine plugins.
=========================================================
"""

from replay_plugin import ReplayPlugin


class ReplayPluginManager:

    def __init__(self):

        self._plugins = {}

    def register(self, plugin: ReplayPlugin):

        self._plugins[plugin.name] = plugin

    def unregister(self, name):

        self._plugins.pop(name, None)

    def get(self, name):

        return self._plugins.get(name)

    def initialize_all(self, context):

        for plugin in self._plugins.values():
            plugin.initialize(context)

    def execute_all(self, *args, **kwargs):

        for plugin in self._plugins.values():
            plugin.execute(*args, **kwargs)

    def shutdown_all(self):

        for plugin in self._plugins.values():
            plugin.shutdown()

    def list_plugins(self):

        return sorted(self._plugins.keys())

    def count(self):

        return len(self._plugins)