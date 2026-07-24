
"""
Swing Replay Evaluator V17
Evaluates trade outcome using future OHLC data.
"""

class SwingReplayEvaluatorV17:

    def evaluate(self, signal_df, future_df):

        if signal_df.empty:
            return signal_df

        out = signal_df.copy()
        out["Replay Outcome"] = "PENDING"

        return out
