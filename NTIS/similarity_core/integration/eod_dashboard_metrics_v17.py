
"""
EOD Dashboard Metrics V17
"""

class EODDashboardMetricsV17:

    def calculate(self, df):

        if df.empty:
            return {}

        metrics = {}

        if "Symbol" in df.columns:
            metrics["Total Stocks"] = len(df)

        if "Trade Decision" in df.columns:
            metrics["BUY Signals"] = (df["Trade Decision"] == "BUY").sum()
            metrics["SELL Signals"] = (df["Trade Decision"] == "SELL").sum()

        return metrics
