"""
=========================================================
NTIS Replay Factory
Version : 1.0
Purpose :
    Factory for creating Replay Strategy
    instances.
=========================================================
"""

from replay_strategy import ReplayStrategy


class ReplayFactory:

    _strategies = {}

    @classmethod
    def register(cls, name, strategy):

        if not issubclass(strategy, ReplayStrategy):
            raise TypeError(
                "Strategy must inherit ReplayStrategy."
            )

        cls._strategies[name] = strategy

    @classmethod
    def create(cls, name, *args, **kwargs):

        if name not in cls._strategies:
            raise ValueError(
                f"Replay strategy '{name}' not registered."
            )

        return cls._strategies[name](*args, **kwargs)

    @classmethod
    def available(cls):

        return sorted(cls._strategies.keys())