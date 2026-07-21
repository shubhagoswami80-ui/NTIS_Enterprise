"""
=========================================================
NTIS Replay State
Version : 1.0
Purpose :
    Maintain execution state for the
    Historical Replay Engine.
=========================================================
"""


class ReplayState:

    IDLE = "IDLE"
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    def __init__(self):

        self._state = self.IDLE

    @property
    def current(self):

        return self._state

    def set(self, state):

        self._state = state

    def is_idle(self):

        return self._state == self.IDLE

    def is_running(self):

        return self._state == self.RUNNING

    def is_completed(self):

        return self._state == self.COMPLETED

    def is_failed(self):

        return self._state == self.FAILED

    def reset(self):

        self._state = self.IDLE