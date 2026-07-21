"""
NTIS Replay Tagger
"""
class ReplayTagger:
    @staticmethod
    def tag(record, *tags):
        record = dict(record)
        record["tags"] = list(tags)
        return record
