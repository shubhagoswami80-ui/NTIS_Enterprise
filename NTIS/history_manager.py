"""
=========================================================
NTIS History Manager
Version : 1.0

Purpose:
    Maintain NTIS historical records

Input:

    ntis_probability_analysis.csv
    ntis_outcome_report.csv


Output:

    Historical_Data
        |
        +-- Predictions
        |
        +-- Outcomes
        |
        +-- Accuracy


=========================================================
"""


from pathlib import Path
from datetime import datetime
import pandas as pd



# =====================================================
# BASE PATH
# =====================================================

BASE_DIR = Path(
    "E:/NSE_Daily_Analysis"
)



OUTPUT_DIR = BASE_DIR / "Output"



HISTORY_DIR = BASE_DIR / "Historical_Data"



PREDICTION_HISTORY = (
    HISTORY_DIR /
    "Predictions"
)


OUTCOME_HISTORY = (
    HISTORY_DIR /
    "Outcomes"
)


ACCURACY_HISTORY = (
    HISTORY_DIR /
    "Accuracy"
)



PREDICTION_FILE = (
    OUTPUT_DIR /
    "ntis_probability_analysis.csv"
)


OUTCOME_FILE = (
    OUTPUT_DIR /
    "ntis_outcome_report.csv"
)



# =====================================================
# HISTORY MANAGER
# =====================================================


class HistoryManager:



    def __init__(self):

        self.today = datetime.today()



        self.date = (
            self.today
            .strftime("%d%b%Y")
        )


        self.year = str(
            self.today.year
        )


        self.month = (
            self.today
            .strftime("%B")
        )



    # =================================================
    # Create Folder Structure
    # =================================================

    def create_folders(self):


        folders=[

            PREDICTION_HISTORY /
            self.year /
            self.month,


            OUTCOME_HISTORY /
            self.year /
            self.month,


            ACCURACY_HISTORY /
            self.year /
            self.month

        ]


        for folder in folders:

            folder.mkdir(

                parents=True,

                exist_ok=True

            )



    # =================================================
    # Archive Prediction
    # =================================================

    def archive_prediction(self):


        if not PREDICTION_FILE.exists():

            print(
                "Prediction file missing"
            )

            return



        df=pd.read_csv(

            PREDICTION_FILE

        )


        file=(

            PREDICTION_HISTORY /
            self.year /
            self.month /
            f"NTIS_Prediction_{self.date}.csv"

        )


        df.to_csv(

            file,

            index=False

        )


        print(
            "Prediction Archived:"
        )

        print(
            file
        )



    # =================================================
    # Archive Outcome
    # =================================================

    def archive_outcome(self):


        if not OUTCOME_FILE.exists():

            print(
                "Outcome file missing"
            )

            return



        df=pd.read_csv(

            OUTCOME_FILE

        )



        file=(

            OUTCOME_HISTORY /
            self.year /
            self.month /
            f"NTIS_Outcome_{self.date}.csv"

        )


        df.to_csv(

            file,

            index=False

        )


        print(
            "Outcome Archived:"
        )

        print(
            file
        )



    # =================================================
    # Accuracy Summary
    # =================================================

    def create_accuracy_report(self):


        if not OUTCOME_FILE.exists():

            return



        df=pd.read_csv(

            OUTCOME_FILE

        )


        if "Outcome" not in df.columns:

            return



        total=len(

            df[
                df["Outcome"]
                .isin(
                    [
                    "SUCCESS",
                    "FAILED"
                    ]
                )
            ]

        )


        success=len(

            df[
                df["Outcome"]
                ==
                "SUCCESS"
            ]

        )



        accuracy=0



        if total>0:

            accuracy=round(

                success /
                total *
                100,

                2

            )



        summary=pd.DataFrame(

            {

            "Date":[

                self.date

            ],

            "Total Trades":[

                total

            ],

            "Successful Trades":[

                success

            ],

            "Accuracy %":[

                accuracy

            ]

            }

        )



        file=(

            ACCURACY_HISTORY /
            self.year /
            self.month /
            "NTIS_Accuracy_Summary.csv"

        )



        if file.exists():

            old=pd.read_csv(file)

            summary=pd.concat(

                [
                old,
                summary
                ],

                ignore_index=True

            )



        summary.to_csv(

            file,

            index=False

        )


        print(
            "Accuracy Updated:"
        )

        print(
            file
        )



# =====================================================
# MAIN
# =====================================================


def main():


    print("="*60)

    print(
        "NTIS HISTORY MANAGER"
    )

    print("="*60)



    manager=HistoryManager()



    manager.create_folders()

    manager.archive_prediction()

    manager.archive_outcome()

    manager.create_accuracy_report()



    print(
        "\nHistory Update Completed"
    )



if __name__=="__main__":

    main()