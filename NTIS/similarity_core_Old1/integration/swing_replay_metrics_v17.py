
"""
Swing Replay Metrics V17
"""

class SwingReplayMetricsV17:

    def calculate(self, df):

        if df.empty:
            return df

        out = df.copy()
        out["MFE %"] = None
        out["MAE %"] = None
        out["Holding Days"] = None

        return out
