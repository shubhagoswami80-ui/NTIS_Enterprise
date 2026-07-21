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
from pathlib import Path



# =====================================================
# Paths
# =====================================================

INPUT_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/ntis_ranked_stocks.csv"
)


OUTPUT_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/ntis_pattern_analysis.csv"
)



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