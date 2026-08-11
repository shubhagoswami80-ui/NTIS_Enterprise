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

TRADING_DATE_FILE = OUTPUT_DIR / "current_trading_date.txt"



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


FOOTPRINT_HISTORY = (
    HISTORY_DIR /
    "Footprints"
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

        trading_date = None

        if TRADING_DATE_FILE.exists():
            try:
                trading_date = datetime.strptime(
                    TRADING_DATE_FILE.read_text(encoding="utf-8").strip(),
                    "%Y-%m-%d"
                ).date()
            except Exception:
                trading_date = None

        if trading_date is not None:
            self.today = trading_date

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
            self.month,

            FOOTPRINT_HISTORY
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
    # Historical Footprints
    # =================================================

    def build_historical_footprints(self):
        """
        Rebuild the derived date-wise Historical Footprint ledger from
        the existing archived Prediction and Outcome records.
        """

        prediction_files = sorted(
            PREDICTION_HISTORY.rglob("NTIS_Prediction_*.csv")
        )

        if not prediction_files:
            print("Historical Footprints: no prediction archives found")
            return

        footprints = []

        for prediction_file in prediction_files:
            try:
                prediction_df = pd.read_csv(prediction_file)
            except Exception:
                continue

            if "Symbol" not in prediction_df.columns:
                continue

            date_token = prediction_file.stem.replace(
                "NTIS_Prediction_", ""
            )

            outcome_file = (
                OUTCOME_HISTORY /
                prediction_file.parent.parent.name /
                prediction_file.parent.name /
                f"NTIS_Outcome_{date_token}.csv"
            )

            if outcome_file.exists():
                try:
                    outcome_df = pd.read_csv(outcome_file)
                except Exception:
                    outcome_df = None
            else:
                outcome_df = None

            if outcome_df is not None and "Symbol" in outcome_df.columns:
                outcome_columns = [
                    column for column in [
                        "Actual Return %",
                        "Outcome",
                        "Model Accuracy %"
                    ]
                    if column in outcome_df.columns
                ]

                outcome_subset = outcome_df[
                    ["Symbol"] + outcome_columns
                ].drop_duplicates(
                    subset=["Symbol"],
                    keep="last"
                )

                merged = prediction_df.merge(
                    outcome_subset,
                    on="Symbol",
                    how="left",
                    suffixes=("", "_OUTCOME")
                )
            else:
                merged = prediction_df.copy()
                merged["Actual Return %"] = pd.NA
                merged["Outcome"] = "PENDING"
                merged["Model Accuracy %"] = pd.NA

            merged.insert(0, "Trading Date", date_token)
            merged["Prediction Source"] = prediction_file.name
            merged["Outcome Source"] = (
                outcome_file.name
                if outcome_file.exists()
                else pd.NA
            )

            footprints.append(merged)

        if not footprints:
            print("Historical Footprints: no valid records found")
            return

        footprint_df = pd.concat(
            footprints,
            ignore_index=True
        )

        footprint_file = (
            FOOTPRINT_HISTORY /
            "NTIS_Historical_Footprints.csv"
        )

        footprint_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        footprint_df.to_csv(
            footprint_file,
            index=False
        )

        print("Historical Footprints Updated:")
        print(footprint_file)
        print("Historical Footprint Rows:", len(footprint_df))


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

    manager.build_historical_footprints()

    manager.create_accuracy_report()



    print(
        "\nHistory Update Completed"
    )



if __name__=="__main__":

    main()