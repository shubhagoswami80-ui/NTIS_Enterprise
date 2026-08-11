"""
=========================================================
NTIS Intraday Historical Replay Engine
Version : 2.2

Purpose:
    Controller for historical intraday replay.

Rules:
    - Replay only actionable validated trades
    - Validate trade parameters before replay
    - Keep filtered records for audit visibility
    - No new configuration files
    - EOD remains read only

Input:
    intraday_trade_candidates.csv
    EOD OHLC report

Output:
    intraday_backtest_results.csv
=========================================================
"""

from pathlib import Path
import pandas as pd

from intraday_outcome_engine import calculate_outcomes


class IntradayHistoricalReplayEngine:


    def __init__(
        self,
        intraday_folder,
        eod_file
    ):

        self.intraday_folder = Path(
            intraday_folder
        )

        self.eod_file = Path(
            eod_file
        )


    def load_intraday_data(self):

        file = (
            self.intraday_folder
            /
            "intraday_trade_candidates.csv"
        )

        if not file.exists():

            raise FileNotFoundError(
                f"Missing intraday file: {file}"
            )

        return pd.read_csv(file)


    def load_eod_data(self):

        if not self.eod_file.exists():

            raise FileNotFoundError(
                f"Missing EOD file: {self.eod_file}"
            )

        return pd.read_excel(
            self.eod_file
        )


    def validate_replay_candidate(
        self,
        row
    ):

        valid_bias = [
            "VALID BUY",
            "VALID SELL"
        ]

        if row.get("Validation Signal") not in valid_bias:

            return False, "Non actionable signal"


        required_fields = [
            "Entry Price",
            "Stop Loss",
            "Target"
        ]


        for field in required_fields:

            if (
                field not in row
                or
                pd.isna(row[field])
            ):

                return (
                    False,
                    "Missing trade parameters"
                )


        return True, "Eligible"


    def prepare_candidates(
        self,
        df
    ):

        df = df.copy()

        eligibility = df.apply(
            self.validate_replay_candidate,
            axis=1
        )


        df["Replay Eligible"] = [
            x[0]
            for x in eligibility
        ]


        df["Filter Reason"] = [
            x[1]
            for x in eligibility
        ]


        return df


    def run(self):

        intraday_df = (
            self.load_intraday_data()
        )


        eod_df = (
            self.load_eod_data()
        )


        intraday_df = (
            self.prepare_candidates(
                intraday_df
            )
        )


        replay_df = intraday_df[
            intraday_df["Replay Eligible"]
        ].copy()


        filtered_df = intraday_df[
            ~intraday_df["Replay Eligible"]
        ].copy()


        if not replay_df.empty:

            replay_result = calculate_outcomes(
                replay_df,
                eod_df
            )

        else:

            replay_result = pd.DataFrame()


        if not filtered_df.empty:

            filtered_df["Outcome"] = (
                "FILTERED"
            )

            filtered_df["Outcome Reason"] = (
                filtered_df["Filter Reason"]
            )

            filtered_df["Exit Price"] = None
            filtered_df["Points"] = 0
            filtered_df["Return %"] = 0


        result = pd.concat(
            [
                replay_result,
                filtered_df
            ],
            ignore_index=True
        )


        output = (
            self.intraday_folder
            /
            "intraday_backtest_results.csv"
        )


        result.to_csv(
            output,
            index=False
        )


        return output