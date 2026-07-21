"""
=========================================================
NTIS Replay Registry
Version : 1.0
Purpose :
    Central registry for Replay Engine
    components.
=========================================================
"""

from replay_factory import ReplayFactory


class ReplayRegistry:

    @staticmethod
    def register(name, strategy):

        ReplayFactory.register(
            name=name,
            strategy=strategy,
        )

    @staticmethod
    def get(name, *args, **kwargs):

        return ReplayFactory.create(
            name,
            *args,
            **kwargs,
        )

    @staticmethod
    def list():

        return ReplayFactory.available()