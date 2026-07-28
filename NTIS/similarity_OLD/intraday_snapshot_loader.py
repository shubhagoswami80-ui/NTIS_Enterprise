"""
HMME-18 Intraday Snapshot Loader
"""

class IntradaySnapshotLoader:

    def filter_snapshot(self, data, snapshot):
        if "Snapshot" not in data.columns:
            return data
        return data[data["Snapshot"] == snapshot]
