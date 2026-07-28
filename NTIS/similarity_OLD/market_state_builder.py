"""
HMME-19 Market State Builder
"""

class MarketStateBuilder:

    def build_state(self, data, snapshot="EOD"):
        state = data.copy()
        state["Snapshot"] = snapshot
        return state
