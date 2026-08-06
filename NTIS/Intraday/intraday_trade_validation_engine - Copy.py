"""
=========================================================
NTIS Intraday Trade Validation Engine
Version : 1.3

Purpose:
    Convert probability output into trade candidates.

Input:
    intraday_probability_analysis.csv

Output:
    intraday_trade_candidates.csv

Updates:
    - Dynamic date support
    - Historical replay support
    - BUY/SELL aware risk-reward
=========================================================
"""

from pathlib import Path
import sys
import pandas as pd

from intraday_execution_context import (
    set_processing_date
)

from intraday_path_config import (
    get_today_output
)

from intraday_intelligence_loader import IntradayIntelligenceLoader
from intraday_intelligence_query import IntradayIntelligenceQuery



# =========================================================
# Set processing date if provided
# =========================================================

if len(sys.argv) > 1:

    set_processing_date(
        sys.argv[1]
    )



OUTPUT_FOLDER = get_today_output()


INPUT_FILE = (
    OUTPUT_FOLDER
    /
    "intraday_probability_analysis.csv"
)


OUTPUT_FILE = (
    OUTPUT_FOLDER
    /
    "intraday_trade_candidates.csv"
)



class IntradayTradeValidationEngine:


    def __init__(self):
        try:
            self.loader = IntradayIntelligenceLoader()
            self.loader.load()
            self.query = IntradayIntelligenceQuery(self.loader)
            self.has_repo = True
        except Exception:
            self.has_repo = False


    def validate_signal(self, row):

        pattern_id = row.get("Pattern_ID", row.get("Pattern", ""))
        
        if self.has_repo and pattern_id:
            try:
                summary = self.query.historical_summary(pattern_id)
                occ = summary.get("Occurrences", 0)
                win_rate = summary.get("WinRate", 0)
                avg_pnl = summary.get("AveragePnL", 0)
                
                if occ >= 20:
                    if win_rate >= 60.0 and avg_pnl >= 0:
                        return "VALID BUY"
                    elif win_rate <= 35.0:
                        return "VALID SELL"
                    else:
                        return "WATCH"
            except Exception:
                pass

        probability = row.get(
            "Intraday Probability %",
            0
        )

        pattern = str(
            row.get("Pattern", "")
        )

        score = row.get(
            "NTIS Intraday Score",
            0
        )


        if (
            probability >= 75
            and score >= 35
            and "Short" not in pattern
            and "Unwinding" not in pattern
        ):
            return "VALID BUY"


        if (
            probability <= 35
            and score <= 30
        ):
            return "VALID SELL"


        return "WATCH"



    def risk_level(self, row):

        probability = row.get(
            "Intraday Probability %",
            0
        )

        if probability >= 80:

            return "LOW"

        elif probability >= 60:

            return "MEDIUM"

        return "HIGH"



    def calculate_trade_levels(
        self,
        row
    ):

        entry = row.get(
            "Price"
        )

        signal = row.get(
            "Validation Signal"
        )


        if pd.isna(entry):

            return pd.Series(
                [
                    None,
                    None,
                    None
                ]
            )


        if signal == "VALID BUY":

            stop_loss = (
                entry * 0.98
            )

            target = (
                entry * 1.04
            )


        elif signal == "VALID SELL":

            stop_loss = (
                entry * 1.02
            )

            target = (
                entry * 0.96
            )


        else:

            stop_loss = None
            target = None


        return pd.Series(
            [
                entry,
                stop_loss,
                target
            ]
        )



    def run(self):

        if not INPUT_FILE.exists():

            raise FileNotFoundError(
                f"Missing input file: {INPUT_FILE}"
            )


        df = pd.read_csv(
            INPUT_FILE
        )


        df["Validation Signal"] = df.apply(
            self.validate_signal,
            axis=1
        )


        df["Risk Level"] = df.apply(
            self.risk_level,
            axis=1
        )


        (
            df[
                [
                    "Entry Price",
                    "Stop Loss",
                    "Target"
                ]
            ]
        ) = df.apply(
            self.calculate_trade_levels,
            axis=1
        )


        df = df.sort_values(
            "Intraday Probability %",
            ascending=False
        )


        df.to_csv(
            OUTPUT_FILE,
            index=False
        )


        return OUTPUT_FILE



if __name__ == "__main__":

    result = (
        IntradayTradeValidationEngine()
        .run()
    )


    print("=" * 60)
    print(
        "INTRADAY TRADE VALIDATION COMPLETE"
    )
    print("Processing Folder:")
    print(OUTPUT_FOLDER)
    print(result)
    print("=" * 60)