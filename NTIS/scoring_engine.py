"""
=========================================================
NTIS Scoring Engine
Version : 1.2

Purpose:
    Convert Market Master Data into
    Stock Ranking & Trading Signals

Enhancement:
    - Numeric normalization
    - Correct bearish scoring
    - Added long unwinding detection
    - Added bearish signal classification

Score Model:

    Price Momentum        25
    OI Confirmation       25
    Volume Momentum       15
    Support Resistance    20
    IV Analysis           15

    Total                 100

=========================================================
"""


import pandas as pd
from pathlib import Path



# =====================================================
# Paths
# =====================================================

INPUT_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/market_master.csv"
)


OUTPUT_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/ntis_ranked_stocks.csv"
)



# =====================================================
# Numeric Cleaning
# =====================================================

def clean_numeric_columns(df):

    numeric_columns = [

        "Price Chg %",
        "OI Chg %",
        "Volume Chg (%)",
        "IVR",
        "IVP",
        "CMP"

    ]


    for col in numeric_columns:

        if col in df.columns:

            df[col] = (

                df[col]
                .astype(str)
                .str.replace(
                    ",",
                    "",
                    regex=False
                )
                .replace(
                    [
                        "nan",
                        "None",
                        "",
                        "NA"
                    ],
                    None
                )

            )


            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )


    return df



# =====================================================
# NTIS SCORE ENGINE
# =====================================================

class NTISScoreEngine:


    def __init__(self,df):

        self.df = clean_numeric_columns(
            df.copy()
        )



    # =================================================
    # Price Momentum
    # =================================================

    def price_score(self,row):

        score = 0


        price = row.get(
            "Price Chg %",
            0
        )


        if pd.isna(price):

            return score



        if price >= 2:

            score +=25


        elif price >0:

            score +=15


        elif price >= -1:

            score +=5


        elif price < -2:

            score -=10


        return score



    # =================================================
    # OI Confirmation
    # =================================================

    def oi_score(self,row):

        score = 0


        price = row.get(
            "Price Chg %",
            0
        )


        oi = row.get(
            "OI Chg %",
            0
        )


        if pd.isna(price) or pd.isna(oi):

            return score



        # Long Buildup
        if price >0 and oi >0:

            score +=25



        # Short Covering
        elif price >0 and oi <0:

            score +=15



        # Short Buildup
        elif price <0 and oi >0:

            score -=20



        # Long Unwinding
        elif price <0 and oi <0:

            score -=10



        return score



    # =================================================
    # Volume Momentum
    # =================================================

    def volume_score(self,row):

        score = 0


        volume = row.get(
            "Volume Chg (%)",
            0
        )


        if pd.isna(volume):

            return score



        if volume >=200:

            score +=15


        elif volume >=100:

            score +=10


        elif volume >0:

            score +=5



        return score



    # =================================================
    # Support Resistance
    # =================================================

    def sr_score(self,row):

        score = 0


        if row.get(
            "Near Support"
        )=="YES":

            score +=20



        elif row.get(
            "Near Resistance"
        )=="YES":

            score -=10



        return score



    # =================================================
    # IV Analysis
    # =================================================

    def iv_score(self,row):

        score = 0


        ivr = row.get(
            "IVR"
        )


        if pd.isna(ivr):

            return score



        if ivr <30:

            score +=15



        elif ivr <50:

            score +=10



        elif ivr >70:

            score -=5



        return score



    # =================================================
    # Calculate NTIS Score
    # =================================================

    def calculate_score(self):


        print(
            "\nCalculating NTIS Score..."
        )


        self.df["Price Score"] = (
            self.df.apply(
                self.price_score,
                axis=1
            )
        )


        self.df["OI Score"] = (
            self.df.apply(
                self.oi_score,
                axis=1
            )
        )


        self.df["Volume Score"] = (
            self.df.apply(
                self.volume_score,
                axis=1
            )
        )


        self.df["Support Resistance Score"] = (
            self.df.apply(
                self.sr_score,
                axis=1
            )
        )


        self.df["IV Score"] = (
            self.df.apply(
                self.iv_score,
                axis=1
            )
        )



        self.df["NTIS Score"] = (

            self.df["Price Score"]

            +

            self.df["OI Score"]

            +

            self.df["Volume Score"]

            +

            self.df["Support Resistance Score"]

            +

            self.df["IV Score"]

        )


        return self.df



    # =================================================
    # Signal Classification
    # =================================================

    def add_signal(self):


        def signal(score):


            if score >=80:

                return "STRONG BULLISH"


            elif score >=60:

                return "BULLISH"


            elif score >=40:

                return "NEUTRAL"


            elif score >=20:

                return "BEARISH WATCH"


            else:

                return "STRONG BEARISH"



        self.df["Signal"] = (

            self.df["NTIS Score"]
            .apply(signal)

        )


        return self.df



    # =================================================
    # Ranking
    # =================================================

    def rank(self):


        self.df = (

            self.df
            .sort_values(
                "NTIS Score",
                ascending=False
            )

        )


        self.df["Rank"] = range(
            1,
            len(self.df)+1
        )


        return self.df



    # =================================================
    # Save
    # =================================================

    def save(self):


        OUTPUT_FILE.parent.mkdir(
            exist_ok=True
        )


        self.df.to_csv(
            OUTPUT_FILE,
            index=False
        )


        print(
            "\nRanking File Created:"
        )

        print(
            OUTPUT_FILE
        )



# =====================================================
# MAIN
# =====================================================

def main():


    print("="*60)

    print(
        "NTIS SCORE ENGINE VERSION 1.2"
    )

    print("="*60)



    if not INPUT_FILE.exists():

        print(
            "Market master file missing"
        )

        return



    df = pd.read_csv(
        INPUT_FILE
    )


    print(
        f"Stocks Loaded : {len(df)}"
    )



    engine = NTISScoreEngine(
        df
    )


    engine.calculate_score()

    engine.add_signal()

    engine.rank()

    engine.save()



    print(
        "\nTOP 20 STOCKS"
    )

    print("-"*60)



    print(

        engine.df[
            [
                "Rank",
                "Symbol",
                "CMP",
                "NTIS Score",
                "Signal"
            ]
        ]
        .head(20)

    )



if __name__=="__main__":

    main()