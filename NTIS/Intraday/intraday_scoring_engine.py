from datetime import datetime
"""
=========================================================
NTIS Intraday Scoring Engine
Version : 1.0

Purpose:
    Score intraday stocks from normalized market master.

Input:
    intraday_market_master_schema.csv

Output:
    intraday_scored_stocks.csv

Independent Intraday Engine
Does not modify EOD NTIS logic.
=========================================================
"""

from pathlib import Path
import pandas as pd


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_market_master_schema.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_scored_stocks.csv"
)


class IntradayScoringEngine:


    def score_row(self, row):

        score = 0
        reasons = []


        # Price momentum
        price = row.get("Price Chg %")

        if pd.notna(price):

            if price > 1:
                score += 20
                reasons.append("Positive Price Momentum")

            elif price < -1:
                score -= 20
                reasons.append("Negative Price Momentum")


        # OI buildup
        oi = row.get("OI Chg %")

        if pd.notna(oi):

            if oi > 2:
                score += 20
                reasons.append("Fresh OI Buildup")

            elif oi < -2:
                score -= 10
                reasons.append("OI Reduction")


        # Volume confirmation
        volume = row.get("Volume Chg %")

        if pd.notna(volume):

            if volume > 50:
                score += 15
                reasons.append("Volume Expansion")


        # Futures buildup
        fut = str(
            row.get("Fut Buildup")
        )

        if "long" in fut.lower():

            score += 20
            reasons.append("Long Futures")

        elif "short" in fut.lower():

            score -= 20
            reasons.append("Short Futures")


        # PCR
        pcr = row.get("PCR")

        if pd.notna(pcr):

            if pcr > 1:
                score += 10
                reasons.append("Bullish PCR")

            elif pcr < 0.7:
                score -= 10
                reasons.append("Bearish PCR")


        score = max(
            0,
            min(score,100)
        )


        if score >= 70:
            bias = "BUY"

        elif score <= 30:
            bias = "SELL"

        else:
            bias = "NEUTRAL"


        return pd.Series(
            [
                score,
                bias,
                "; ".join(reasons)
            ]
        )


    def run(self):

        df = pd.read_csv(
            INPUT_FILE
        )


        result = df.apply(
            self.score_row,
            axis=1
        )


        result.columns = [
            "NTIS Intraday Score",
            "Trade Bias",
            "Reason"
        ]


        df = pd.concat(
            [
                df,
                result
            ],
            axis=1
        )


        df = df.sort_values(
            "NTIS Intraday Score",
            ascending=False
        )


        df.to_csv(
            OUTPUT_FILE,
            index=False
        )


        return OUTPUT_FILE



if __name__ == "__main__":

    output = IntradayScoringEngine().run()

    print("=" * 60)
    print("INTRADAY SCORING COMPLETE")
    print(output)
    print("=" * 60)
