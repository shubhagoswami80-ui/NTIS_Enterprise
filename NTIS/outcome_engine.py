"""
NTIS Outcome Engine
Version : 1.3
Production Replacement
"""

import pandas as pd
from pathlib import Path

PREDICTION_FILE = Path("E:/NSE_Daily_Analysis/Output/ntis_probability_analysis.csv")
PRICE_FILE = Path("E:/NSE_Daily_Analysis/Output/market_master.csv")
OUTPUT_FILE = Path("E:/NSE_Daily_Analysis/Output/ntis_outcome_report.csv")


class OutcomeEngine:
    def __init__(self, predictions, prices):
        self.df = predictions.copy()
        self.price = prices.copy()

    def merge_price(self):
        if "Symbol" not in self.price.columns:
            print("Symbol column missing in price file")
            return self.df

        price_column = next((c for c in ("Close", "CMP", "Price", "Current Price")
                             if c in self.price.columns), None)

        if price_column is None:
            print("No supported market price column found.")
            return self.df

        self.df = self.df.merge(
            self.price[["Symbol", price_column]].rename(columns={price_column: "Close"}),
            on="Symbol",
            how="left",
        )
        return self.df

    def calculate_outcome(self):
        outcomes = []
        returns = []

        for _, row in self.df.iterrows():
            bias = row.get("Trade Bias", "WAIT")
            entry = row.get("Entry Close")
            current = row.get("Close")

            if pd.isna(entry) or pd.isna(current) or entry in (0, "0", ""):
                outcomes.append("PENDING")
                returns.append(0)
                continue

            try:
                entry = float(entry)
                current = float(current)
                if entry == 0:
                    raise ZeroDivisionError
                change = ((current - entry) / entry) * 100
            except (ValueError, TypeError, ZeroDivisionError):
                outcomes.append("PENDING")
                returns.append(0)
                continue

            returns.append(round(change, 2))

            if bias in ("BUY", "STRONG BUY"):
                outcomes.append("SUCCESS" if change > 0 else "FAILED")
            elif bias in ("SELL", "STRONG SELL"):
                outcomes.append("SUCCESS" if change < 0 else "FAILED")
            else:
                outcomes.append("NO TRADE")

        self.df["Actual Return %"] = returns
        self.df["Outcome"] = outcomes
        return self.df

    def calculate_accuracy(self):
        valid = self.df[self.df["Outcome"].isin(["SUCCESS", "FAILED"])]
        total = len(valid)
        success = len(valid[valid["Outcome"] == "SUCCESS"])
        accuracy = round((success / total) * 100, 2) if total else 0
        self.df["Model Accuracy %"] = accuracy
        return self.df

    def save(self):
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(OUTPUT_FILE, index=False)
        print("\nOutcome Report Created:")
        print(OUTPUT_FILE)


def main():
    print("=" * 60)
    print("NTIS OUTCOME ENGINE")
    print("=" * 60)

    if not PREDICTION_FILE.exists():
        print("Prediction file missing")
        return

    predictions = pd.read_csv(PREDICTION_FILE)
    prices = pd.read_csv(PRICE_FILE) if PRICE_FILE.exists() else pd.DataFrame()

    print("\nPredictions Loaded:", len(predictions))

    engine = OutcomeEngine(predictions, prices)
    engine.merge_price()
    engine.calculate_outcome()
    engine.calculate_accuracy()
    engine.save()

    cols = [c for c in [
        "Symbol", "Trade Bias", "BUY Probability %",
        "Actual Return %", "Outcome", "Model Accuracy %"
    ] if c in engine.df.columns]

    print("\nOUTCOME SUMMARY")
    print("-" * 60)
    print(engine.df[cols].head(20))
    print("\nOutcome Engine Completed")


if __name__ == "__main__":
    main()
