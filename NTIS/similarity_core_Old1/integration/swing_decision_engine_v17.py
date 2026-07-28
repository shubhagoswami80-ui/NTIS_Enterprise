"""
Swing Decision Engine V17

Combines swing intelligence outputs into final trade decision.
"""


class SwingDecisionEngineV17:

    def decide(self, df):

        if df.empty:
            return df

        out = df.copy()

        out["Trade Decision"] = "WAIT"

        if "Swing Setup" in out.columns:
            out.loc[
                out["Swing Setup"] == "BUY_SETUP",
                "Trade Decision"
            ] = "BUY"

            out.loc[
                out["Swing Setup"] == "SELL_SETUP",
                "Trade Decision"
            ] = "SELL"

        return out
