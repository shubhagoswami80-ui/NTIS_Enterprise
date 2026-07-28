
"""
NTIS Probability Metrics V17
"""

class NTISProbabilityMetricsV17:

    def calculate(self, df):

        if df.empty:
            return df

        out = df.copy()
        out["Probability Grade"] = "NORMAL"

        if "Probability %" in out.columns:
            out.loc[out["Probability %"] >= 70, "Probability Grade"] = "HIGH"
            out.loc[out["Probability %"] <= 30, "Probability Grade"] = "LOW"

        return out
