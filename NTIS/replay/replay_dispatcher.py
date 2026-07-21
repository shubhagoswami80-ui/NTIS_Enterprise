"""
NTIS Replay Dispatcher
"""
class ReplayDispatcher:
    def dispatch(self, handlers, event):
        for handler in handlers:
            handler(event)
