"""
=========================================================
NTIS Intraday Historical Replay Engine
Version : 2.3

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
from intraday_pattern_repository import IntradayPatternRepository
from intraday_pattern_lifecycle_engine import IntradayPatternLifecycleEngine


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

    # ----------------------------------------------------------

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

    # ----------------------------------------------------------

    def load_eod_data(self):

        if not self.eod_file.exists():

            raise FileNotFoundError(
                f"Missing EOD file: {self.eod_file}"
            )

        return pd.read_excel(
            self.eod_file
        )

    # ----------------------------------------------------------

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

    # ----------------------------------------------------------

    def prepare_candidates(
        self,
        df
    ):

        df = df.copy()

        if df.empty:

            df["Replay Eligible"] = pd.Series(
                dtype=bool
            )

            df["Filter Reason"] = pd.Series(
                dtype=str
            )

            return df

        eligibility = df.apply(
            self.validate_replay_candidate,
            axis=1
        )

        df["Replay Eligible"] = [
            item[0]
            for item in eligibility
        ]

        df["Filter Reason"] = [
            item[1]
            for item in eligibility
        ]

        return df

    # ----------------------------------------------------------

    @staticmethod
    def _filtered_results(filtered_df):

        if filtered_df.empty:
            return filtered_df

        filtered_df = filtered_df.copy()

        filtered_df["Outcome"] = "FILTERED"

        filtered_df["Outcome Reason"] = (
            filtered_df["Filter Reason"]
        )

        filtered_df["Exit Price"] = None
        filtered_df["Points"] = 0
        filtered_df["Return %"] = 0

        return filtered_df

    # ----------------------------------------------------------

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

        eligible_mask = intraday_df[
            "Replay Eligible"
        ].fillna(False).astype(bool)

        replay_df = intraday_df[
            eligible_mask
        ].copy()

        filtered_df = intraday_df[
            ~eligible_mask
        ].copy()

        if not replay_df.empty:

            replay_result = calculate_outcomes(
                replay_df,
                eod_df
            )

        else:

            replay_result = pd.DataFrame(
                columns=intraday_df.columns
            )

        filtered_result = self._filtered_results(
            filtered_df
        )

        result = pd.concat(
            [
                replay_result,
                filtered_result
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

        # Integrate replay results into Pattern Intelligence Repository
        try:
            repo = IntradayPatternRepository()
            lifecycle = IntradayPatternLifecycleEngine(repo)
            replay_date = self.intraday_folder.name
            lifecycle.integrate_outcomes(result, trade_date=replay_date)
            lifecycle.evaluate_lifecycle()
        except Exception:
            pass

        return output
