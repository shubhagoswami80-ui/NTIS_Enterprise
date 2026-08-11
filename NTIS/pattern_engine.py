"""
=========================================================
NTIS Pattern Engine
Version : 1.0

Purpose:
    Identify market patterns from NTIS ranked stocks

Input:
    ntis_ranked_stocks.csv

Output:
    ntis_pattern_analysis.csv


Patterns:

    1. Fresh Long Buildup
    2. Short Buildup
    3. Short Covering
    4. Long Unwinding
    5. Momentum Breakout
    6. Support Bounce
    7. Resistance Rejection

=========================================================
"""


import pandas as pd
from datetime import datetime
from pathlib import Path

from config import DAILY_REPORTS, OUTPUT, REPORT_FOLDERS
from utils import extract_report_date, format_date, get_latest_file


# =====================================================
# Paths
# =====================================================

INPUT_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/ntis_ranked_stocks.csv"
)


OUTPUT_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/ntis_pattern_analysis.csv"
)


def resolve_importer_trading_date():

    date_file = OUTPUT / "current_trading_date.txt"

    if not date_file.exists():

        return None

    try:

        return datetime.strptime(
            date_file.read_text(encoding="utf-8").strip(),
            "%Y-%m-%d"
        ).date()

    except Exception:

        return None


def resolve_trading_date():

    dates = []

    for folder_name in REPORT_FOLDERS.values():

        source_folder = DAILY_REPORTS / folder_name

        if not source_folder.exists():

            continue


        latest_file = get_latest_file(source_folder)

        if latest_file is None:

            continue


        report_date = extract_report_date(latest_file.name)

        if report_date is not None:

            dates.append(report_date)


    if not dates:

        return None


    unique_dates = sorted({date.date() for date in dates})

    if len(unique_dates) == 1:

        return unique_dates[0]


    latest_date = max(unique_dates)

    print(
        "Warning: multiple report dates found in EOD folders. Using latest date :",
        format_date(latest_date)
    )

    return latest_date


# =====================================================
# Numeric Cleaning
# =====================================================

def clean_numeric(df):

    columns = [

        "Price Chg %",
        "OI Chg %",
        "Volume Chg (%)"

    ]


    for col in columns:

        if col in df.columns:

            df[col] = (

                df[col]
                .astype(str)
                .str.replace(
                    ",",
                    "",
                    regex=False
                )

            )


            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )


    return df



# =====================================================
# Pattern Engine
# =====================================================

class PatternEngine:


    def __init__(self,df):

        self.df = clean_numeric(
            df.copy()
        )

        self.pattern_date = resolve_importer_trading_date()

        if self.pattern_date is None:

            self.pattern_date = resolve_trading_date()

        if self.pattern_date is not None:

            self.df["Date"] = format_date(self.pattern_date)



    # -------------------------------------------------
    # Detect Pattern
    # -------------------------------------------------

    def detect_pattern(self,row):


        price = row.get(
            "Price Chg %",
            0
        )


        oi = row.get(
            "OI Chg %",
            0
        )


        volume = row.get(
            "Volume Chg (%)",
            0
        )


        support = row.get(
            "Near Support"
        )


        resistance = row.get(
            "Near Resistance"
        )



        # ---------------------------------------------
        # Long Buildup
        # ---------------------------------------------

        if price >0 and oi >0:

            if volume >=100:

                return (
                    "Momentum Long Buildup",
                    "Price rising + OI rising + Volume expansion"
                )


            return (
                "Fresh Long Buildup",
                "Price rising with increasing OI"
            )



        # ---------------------------------------------
        # Short Buildup
        # ---------------------------------------------

        elif price <0 and oi >0:

            return (
                "Fresh Short Buildup",
                "Price falling + OI increasing"
            )



        # ---------------------------------------------
        # Short Covering
        # ---------------------------------------------

        elif price >0 and oi <0:

            return (
                "Short Covering",
                "Price rising + Shorts exiting"
            )



        # ---------------------------------------------
        # Long Unwinding
        # ---------------------------------------------

        elif price <0 and oi <0:

            return (
                "Long Unwinding",
                "Price falling + Long positions exiting"
            )



        # ---------------------------------------------
        # Support Bounce
        # ---------------------------------------------

        if support=="YES":

            return (
                "Support Bounce",
                "Stock trading near OI support"
            )



        # ---------------------------------------------
        # Resistance Rejection
        # ---------------------------------------------

        if resistance=="YES":

            return (
                "Resistance Rejection",
                "Stock near resistance zone"
            )



        return (
            "No Clear Pattern",
            "Mixed market signals"
        )



    # -------------------------------------------------
    # Apply Pattern
    # -------------------------------------------------

    def apply_patterns(self):


        result = (

            self.df.apply(
                self.detect_pattern,
                axis=1
            )

        )


        self.df["Pattern"] = (

            result
            .apply(
                lambda x:x[0]
            )

        )


        self.df["Pattern Reason"] = (

            result
            .apply(
                lambda x:x[1]
            )

        )


        return self.df



    # -------------------------------------------------
    # Save
    # -------------------------------------------------

    def save(self):


        OUTPUT_FILE.parent.mkdir(
            exist_ok=True
        )


        self.df.to_csv(
            OUTPUT_FILE,
            index=False
        )


        print(
            "\nPattern Analysis Created:"
        )


        print(
            OUTPUT_FILE
        )



# =====================================================
# Main
# =====================================================

def main():


    print("="*60)

    print(
        "NTIS PATTERN ENGINE"
    )

    print("="*60)



    if not INPUT_FILE.exists():

        print(
            "Ranking file missing"
        )

        return



    df = pd.read_csv(
        INPUT_FILE
    )


    print(
        f"Stocks Loaded : {len(df)}"
    )



    engine = PatternEngine(
        df
    )


    engine.apply_patterns()

    engine.save()



    print("\nTOP PATTERNS")

    print("-"*60)


    print(

        engine.df[

            [
                "Rank",
                "Symbol",
                "NTIS Score",
                "Signal",
                "Pattern",
                "Pattern Reason"

            ]

        ]

        .head(20)

    )



if __name__=="__main__":

    main()