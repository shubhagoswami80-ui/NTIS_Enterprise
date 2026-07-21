"""
=========================================================
NTIS Probability Engine
Version : 2.0 Enterprise

Purpose:
    Convert NTIS Score + Pattern + Confirmation
    into Trading Probability

Part : 1 / 4
=========================================================
"""

import logging
import pandas as pd
from pathlib import Path
from datetime import datetime



# =====================================================
# PATHS
# =====================================================

INPUT_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/ntis_pattern_analysis.csv"
)

OUTPUT_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/ntis_probability_analysis.csv"
)

LOG_FILE = Path(
    "E:/NSE_Daily_Analysis/Logs/probability_engine.log"
)

LOG_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)



# =====================================================
# ENGINE
# =====================================================

class ProbabilityEngine:


    def __init__(self, df):

        self.df = df.copy()

        self.clean_numeric()

        logging.info(
            "Probability Engine Started"
        )


    # =================================================
    # NUMERIC CLEANUP
    # =================================================

    def clean_numeric(self):

        numeric_columns = [

            "NTIS Score",

            "Price Chg %",

            "OI Chg %",

            "Volume Chg (%)",

            "PCR Chg %",

            "Close"

        ]


        for col in numeric_columns:

            if col in self.df.columns:

                self.df[col] = (

                    self.df[col]

                    .astype(str)

                    .str.replace(",", "", regex=False)

                    .str.replace("%", "", regex=False)

                    .replace("nan", "0")

                )

                self.df[col] = pd.to_numeric(

                    self.df[col],

                    errors="coerce"

                ).fillna(0)


    # =================================================
    # SCORE WEIGHT
    # =================================================

    def score_probability(self, score):

        if score >= 90:

            return 25

        elif score >= 80:

            return 22

        elif score >= 70:

            return 18

        elif score >= 60:

            return 15

        elif score >= 50:

            return 10

        elif score >= 40:

            return 5

        return 0



    # =================================================
    # PATTERN WEIGHT
    # =================================================

    def pattern_probability(self, pattern):

        pattern = str(pattern).strip()


        bullish = {

            "Momentum Long Buildup": 20,

            "Fresh Long Buildup": 18,

            "Short Covering": 15,

            "Support Bounce": 10

        }


        bearish = {

            "Fresh Short Buildup": -20,

            "Long Unwinding": -15,

            "Resistance Rejection": -10

        }


        if pattern in bullish:

            return bullish[pattern]

        if pattern in bearish:

            return bearish[pattern]

        return 0



    # =================================================
    # CONFIRMATION SCORE
    # =================================================

    def confirmation_probability(self, row):

        score = 0

        volume = row.get(
            "Volume Chg (%)",
            0
        )

        pcr = row.get(
            "PCR Chg %",
            0
        )

        price = row.get(
            "Price Chg %",
            0
        )

        oi = row.get(
            "OI Chg %",
            0
        )

        # Volume confirmation

        if volume >= 200:

            score += 8

        elif volume >= 100:

            score += 5

        elif volume >= 50:

            score += 3

        # PCR hook

        if pcr >= 15:

            score += 3

        elif pcr <= -15:

            score -= 5

        # Price + OI confirmation

        if price >= 0.5 and oi >= 1:

            score += 3

        elif price <= -0.5 and oi >= 1:

            score -= 3
            
                    # =================================================
        # Future Hooks
        # =================================================

        # IV / HV Hook
        # (Will be activated in v2.1)

        iv = row.get(
            "IV Chg %",
            0
        )

        try:
            iv = float(iv)
        except:
            iv = 0

        if iv > 10:
            score += 2
        elif iv < -10:
            score -= 2


        # ATM Straddle Hook
        # (Reserved)

        atm = row.get(
            "ATM Straddle %",
            0
        )

        try:
            atm = float(atm)
        except:
            atm = 0

        if atm > 0:
            score += 1


        return score


    # =================================================
    # CALCULATE PROBABILITY
    # =================================================

    def calculate(self):

        buy_probability = []
        sell_probability = []
        entry_close = []

        for _, row in self.df.iterrows():

            probability = 50

            probability += self.score_probability(

                row.get(
                    "NTIS Score",
                    0
                )

            )

            probability += self.pattern_probability(

                row.get(
                    "Pattern",
                    ""
                )

            )

            probability += self.confirmation_probability(

                row

            )

            # Clamp probability

            probability = max(

                10,

                min(

                    probability,

                    90

                )

            )

            buy_probability.append(

                round(probability, 2)

            )

            sell_probability.append(

                round(

                    100 - probability,

                    2

                )

            )

            # Store Entry Price

            entry_close.append(

                row.get(

                    "CMP",

                    0

                )

            )


        self.df["BUY Probability %"] = buy_probability

        self.df["SELL Probability %"] = sell_probability

        self.df["Entry Close"] = entry_close

        logging.info(

            "Probability Calculation Completed"

        )

        return self.df



    # =================================================
    # CONFIDENCE
    # =================================================

    def add_confidence(self):

        def confidence(prob):

            if prob >= 90:

                return "VERY HIGH"

            elif prob >= 80:

                return "HIGH"

            elif prob >= 65:

                return "MEDIUM"

            elif prob >= 50:

                return "LOW"

            return "VERY LOW"

        self.df["Confidence"] = (

            self.df[
                "BUY Probability %"
            ]

            .apply(

                confidence

            )

        )

        logging.info(

            "Confidence Assigned"

        )

        return self.df
        
            # =================================================
    # TRADE BIAS
    # =================================================

    def add_bias(self):

        def bias(prob):

            if prob >= 90:

                return "STRONG BUY"

            elif prob >= 75:

                return "BUY"

            elif prob >= 60:

                return "ACCUMULATE"

            elif prob >= 40:

                return "WAIT"

            elif prob >= 25:

                return "SELL"

            return "STRONG SELL"


        self.df["Trade Bias"] = (

            self.df[
                "BUY Probability %"
            ]

            .apply(
                bias
            )

        )

        logging.info(

            "Trade Bias Assigned"

        )

        return self.df


    # =================================================
    # FINAL RANKING
    # =================================================

    def ranking(self):

        self.df = (

            self.df

            .sort_values(

                by=[

                    "BUY Probability %",

                    "NTIS Score"

                ],

                ascending=[

                    False,

                    False

                ]

            )

            .reset_index(

                drop=True

            )

        )


        # Remove existing Rank column

        if "Rank" in self.df.columns:

            self.df.drop(

                columns=["Rank"],

                inplace=True

            )


        self.df.insert(

            0,

            "Rank",

            range(

                1,

                len(self.df) + 1

            )

        )

        logging.info(

            "Ranking Completed"

        )

        return self.df

    # =================================================
    # SAVE
    # =================================================

    def save(self):

        OUTPUT_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        # =============================================
        # MASTER PROBABILITY REPORT
        # =============================================

        self.df.to_csv(

            OUTPUT_FILE,

            index=False

        )


        # =============================================
        # LONG OPPORTUNITY REPORT
        # =============================================

        long_df = (

            self.df

            .sort_values(

                by=[

                    "BUY Probability %",

                    "NTIS Score"

                ],

                ascending=[

                    False,

                    False

                ]

            )

            .reset_index(

                drop=True

            )

        )

        if "Rank" in long_df.columns:

            long_df.drop(
                columns=["Rank"],
                inplace=True
            )

        long_df.insert(

            0,

            "Rank",

            range(

                1,

                len(long_df) + 1

            )

        )


        long_df.to_csv(

            OUTPUT_FILE.parent / "ntis_long_probability.csv",

            index=False

        )


        # =============================================
        # SHORT OPPORTUNITY REPORT
        # =============================================

        short_df = (

            self.df

            .sort_values(

                by=[

                    "SELL Probability %",

                    "NTIS Score"

                ],

                ascending=[

                    False,

                    False

                ]

            )

            .reset_index(

                drop=True

            )

        )

        if "Rank" in short_df.columns:

            short_df.drop(

                columns=["Rank"],

                inplace=True

            )

        short_df.insert(

            0,

            "Rank",

            range(

                1,

                len(short_df) + 1

            )

        )


        short_df.to_csv(

            OUTPUT_FILE.parent / "ntis_short_probability.csv",

            index=False

        )


        logging.info(

            "Probability Reports Saved"

        )


        print()

        print(
            "Probability Reports Created"
        )

        print(
            OUTPUT_FILE
        )

        print(
            OUTPUT_FILE.parent / "ntis_long_probability.csv"
        )

        print(
            OUTPUT_FILE.parent / "ntis_short_probability.csv"
        )

        return self.df


    # =================================================
    # SUMMARY
    # =================================================

    def summary(self):

        print()

        print("=" * 80)

        print("TOP 20 NTIS PROBABILITY STOCKS")

        print("=" * 80)

        display_columns = [

            "Rank",

            "Symbol",

            "NTIS Score",

            "Pattern",

            "BUY Probability %",

            "SELL Probability %",

            "Confidence",

            "Trade Bias",

            "Entry Close"

        ]

        available = [

            c

            for c in display_columns

            if c in self.df.columns

        ]

        print(

            self.df[available]

            .head(20)

        )

        print()

        logging.info(

            "Summary Printed"

        )
        
        # =====================================================
# MAIN
# =====================================================

def main():

    print("=" * 60)
    print("NTIS PROBABILITY ENGINE v2.0 ENTERPRISE")
    print("=" * 60)

    if not INPUT_FILE.exists():

        print()
        print("Pattern Analysis file not found")
        print(INPUT_FILE)

        logging.error(
            "Input file missing : %s",
            INPUT_FILE
        )

        return

    try:

        df = pd.read_csv(

            INPUT_FILE

        )
        print(df.columns.tolist())
    except Exception as e:

        print()
        print("Unable to read input file")

        logging.exception(e)

        return


    print()
    print(f"Stocks Loaded : {len(df)}")


    engine = ProbabilityEngine(

        df

    )


    # ================================================
    # Execute Engine
    # ================================================

    engine.calculate()

    engine.add_confidence()

    engine.add_bias()

    engine.ranking()

    engine.save()

    engine.summary()


    # ================================================
    # Statistics
    # ================================================

    print("=" * 60)

    print("ENGINE STATISTICS")

    print("=" * 60)

    print(
        "Total Stocks :",
        len(engine.df)
    )

    print(
        "Strong BUY :",
        len(
            engine.df[
                engine.df["Trade Bias"] == "STRONG BUY"
            ]
        )
    )

    print(
        "BUY :",
        len(
            engine.df[
                engine.df["Trade Bias"] == "BUY"
            ]
        )
    )

    print(
        "ACCUMULATE :",
        len(
            engine.df[
                engine.df["Trade Bias"] == "ACCUMULATE"
            ]
        )
    )

    print(
        "WAIT :",
        len(
            engine.df[
                engine.df["Trade Bias"] == "WAIT"
            ]
        )
    )

    print(
        "SELL :",
        len(
            engine.df[
                engine.df["Trade Bias"] == "SELL"
            ]
        )
    )

    print(
        "STRONG SELL :",
        len(
            engine.df[
                engine.df["Trade Bias"] == "STRONG SELL"
            ]
        )
    )


    average_probability = round(

        engine.df[
            "BUY Probability %"
        ].mean(),

        2

    )

    print()

    print(
        "Average BUY Probability :",
        average_probability,
        "%"
    )

    print()

    print(
        "Output File :"
    )

    print(
        OUTPUT_FILE
    )

    logging.info(

        "Probability Engine Completed Successfully"

    )

    print()

    print(
        "Probability Engine Completed Successfully"
    )


# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    start_time = datetime.now()

    main()

    end_time = datetime.now()

    print()

    print(
        "Execution Time :",
        end_time - start_time
    )

    logging.info(

        "Execution Time : %s",

        end_time - start_time

    )


# =====================================================
# END OF FILE
# Probability Engine v2.0 Enterprise
# =====================================================