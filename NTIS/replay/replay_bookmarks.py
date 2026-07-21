"""
NTIS Replay Bookmarks
"""
class ReplayBookmarks:
    def __init__(self):
        self._bookmarks = {}

    def add(self, name, position):
        self._bookmarks[name] = position

    def get(self, name):
        return self._bookmarks.get(name)
