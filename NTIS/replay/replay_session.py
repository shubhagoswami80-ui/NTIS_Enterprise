"""
=========================================================
NTIS Replay Session
Version : 1.0
Purpose :
    Manage a Historical Replay session.
=========================================================
"""

from datetime import datetime


class ReplaySession:

    def __init__(self, name="Replay Session"):

        self.name = name

        self.started = None
        self.finished = None

        self.status = "NOT STARTED"

    def start(self):

        self.started = datetime.now()
        self.status = "RUNNING"

    def finish(self):

        self.finished = datetime.now()
        self.status = "COMPLETED"

    @property
    def duration(self):

        if self.started is None or self.finished is None:
            return None

        return self.finished - self.started

    def summary(self):

        return {
            "Session": self.name,
            "Status": self.status,
            "Started": self.started,
            "Finished": self.finished,
            "Duration": self.duration,
        }