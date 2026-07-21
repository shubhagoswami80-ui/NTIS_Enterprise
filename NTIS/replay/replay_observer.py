"""
=========================================================
NTIS Replay Observer
Version : 1.0
Purpose :
    Observer pattern implementation for
    Historical Replay Engine events.
=========================================================
"""


class ReplayObserver:

    def update(self, event):
        """
        Override in derived classes.
        """
        pass


class ReplayObservable:

    def __init__(self):

        self._observers = []

    def register(self, observer):

        if observer not in self._observers:
            self._observers.append(observer)

    def unregister(self, observer):

        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event):

        for observer in self._observers:
            observer.update(event)

    def clear(self):

        self._observers.clear()

    @property
    def observers(self):

        return self._observers.copy()