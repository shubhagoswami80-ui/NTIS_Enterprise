"""
=========================================================
NTIS Replay Context
Version : 1.0
Purpose :
    Runtime context shared across
    Historical Replay Engine modules.
=========================================================
"""


class ReplayContext:

    def __init__(self):

        self._context = {}

    def set(self, key, value):

        self._context[key] = value

    def get(self, key, default=None):

        return self._context.get(key, default)

    def remove(self, key):

        self._context.pop(key, None)

    def clear(self):

        self._context.clear()

    def keys(self):

        return list(self._context.keys())

    def values(self):

        return list(self._context.values())

    def items(self):

        return self._context.items()

    def exists(self, key):

        return key in self._context

    def __contains__(self, key):

        return key in self._context

    def __len__(self):

        return len(self._context)