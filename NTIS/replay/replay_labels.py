"""
NTIS Replay Labels
"""
class ReplayLabels:
    @staticmethod
    def apply(record, **labels):
        item = dict(record)
        item.update(labels)
        return item
