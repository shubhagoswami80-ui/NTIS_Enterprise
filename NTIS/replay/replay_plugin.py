"""
=========================================================
NTIS Replay Plugin Interface
Version : 1.0
Purpose :
    Base interface for Replay Engine
    plugins.
=========================================================
"""

from abc import ABC, abstractmethod


class ReplayPlugin(ABC):

    @property
    @abstractmethod
    def name(self):
        """Plugin name."""
        pass

    @property
    @abstractmethod
    def version(self):
        """Plugin version."""
        pass

    @abstractmethod
    def initialize(self, context):
        """Initialize the plugin."""
        pass

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Execute plugin logic."""
        pass

    @abstractmethod
    def shutdown(self):
        """Cleanup resources."""
        pass