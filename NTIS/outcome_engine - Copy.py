"""
=========================================================
NTIS Outcome Engine
Version : 1.1

Purpose:
    Validate NTIS Predictions against
    actual market outcome

Input:

    ntis_probability_analysis.csv
    market_master.csv


Output:

    ntis_outcome_report.csv


Generated:

    Actual Return %
    Prediction Result
    Accuracy
    Outcome


=========================================================
"""


import pandas as pd
from pathlib import Path



# =====================================================
# PATHS
# =====================================================


PREDICTION_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/ntis_probability_analysis.csv"
)


PRICE_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/market_master.csv"
)


OUTPUT_FILE = Path(
    "E:/NSE_Daily_Analysis/Output/ntis_outcome_report.csv"
)



# =====================================================
# OUTCOME ENGINE CLASS
# =====================================================


class OutcomeEngine:


    def __init__(self, predictions, prices):

        self.df = predictions.copy()

        self.price = prices.copy()



    # =================================================
    # Merge Current Market Price
    # =================================================

    def merge_price(self):


        if "Symbol" not in self.price.columns:

            print(
                "Symbol column missing in price file"
            )

            return self.df



        if "Close" not in self.price.columns:

            print(
                "Close column missing in price file"
            )

            return self.df



        self.df = self.df.merge(

            self.price[

                [
                    "Symbol",
                    "Close"
                ]

            ],

            on="Symbol",

            how="left"

        )


        return self.df




    # =================================================
    # Calculate Outcome
    # =================================================

    def calculate_outcome(self):


        outcomes=[]

        returns=[]



        for _,row in self.df.iterrows():


            bias=row.get(

                "Trade Bias",
                "WAIT"

            )


            entry=row.get(

                "Entry Close",
                None

            )


            current=row.get(

                "Close",
                None

            )



            # -----------------------------------------
            # If Entry Price unavailable
            # -----------------------------------------

            if pd.isna(entry) or pd.isna(current):


                outcomes.append(
                    "PENDING"
                )


                returns.append(
                    0
                )


                continue




            change=(

                current-entry

            )/entry*100



            returns.append(

                round(change,2)

            )




            # -----------------------------------------
            # BUY Logic
            # -----------------------------------------


            if bias in [

                "BUY",
                "STRONG BUY"

            ]:


                if change > 0:


                    outcomes.append(
                        "SUCCESS"
                    )


                else:


                    outcomes.append(
                        "FAILED"
                    )





            # -----------------------------------------
            # SELL Logic
            # -----------------------------------------


            elif bias=="SELL":


                if change < 0:


                    outcomes.append(
                        "SUCCESS"
                    )


                else:


                    outcomes.append(
                        "FAILED"
                    )





            else:


                outcomes.append(
                    "NO TRADE"
                )



        self.df["Actual Return %"]=returns

        self.df["Outcome"]=outcomes



        return self.df




    # =================================================
    # Accuracy Calculation
    # =================================================


    def calculate_accuracy(self):


        valid=self.df[

            self.df["Outcome"].isin(

                [
                    "SUCCESS",
                    "FAILED"
                ]

            )

        ]



        total=len(valid)



        success=len(

            valid[

                valid["Outcome"]

                =="SUCCESS"

            ]

        )



        if total>0:


            accuracy=round(

                success/total*100,

                2

            )


        else:


            accuracy=0



        self.df["Model Accuracy %"]=accuracy



        return self.df




    # =================================================
    # Save Report
    # =================================================


    def save(self):


        OUTPUT_FILE.parent.mkdir(

            exist_ok=True

        )



        self.df.to_csv(

            OUTPUT_FILE,

            index=False

        )



        print()

        print(
            "Outcome Report Created:"
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
        "NTIS OUTCOME ENGINE"
    )

    print("="*60)




    if not PREDICTION_FILE.exists():


        print(

            "Prediction file missing"

        )

        return




    predictions=pd.read_csv(

        PREDICTION_FILE

    )




    if PRICE_FILE.exists():


        prices=pd.read_csv(

            PRICE_FILE

        )


    else:


        prices=pd.DataFrame()




    print()

    print(

        "Predictions Loaded:",

        len(predictions)

    )




    engine=OutcomeEngine(

        predictions,

        prices

    )




    engine.merge_price()


    engine.calculate_outcome()


    engine.calculate_accuracy()


    engine.save()




    print()

    print(
        "OUTCOME SUMMARY"
    )

    print("-"*60)




    display_columns=[

        "Symbol",
        "Trade Bias",
        "BUY Probability %",
        "Actual Return %",
        "Outcome",
        "Model Accuracy %"

    ]



    available=[

        c for c in display_columns

        if c in engine.df.columns

    ]



    print(

        engine.df[available]

        .head(20)

    )




    print()

    print(
        "Outcome Engine Completed"
    )





if __name__=="__main__":


    main()