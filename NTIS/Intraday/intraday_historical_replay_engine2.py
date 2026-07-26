"""
NTIS Intraday Historical Replay Engine v2.0

Controller for replaying historical intraday signals.
"""

from pathlib import Path
import pandas as pd

from intraday_outcome_engine import calculate_outcomes


class IntradayHistoricalReplayEngine:

    def __init__(self, intraday_folder, eod_file):

        self.intraday_folder = Path(intraday_folder)
        self.eod_file = Path(eod_file)


    def run(self):

        input_file = (
            self.intraday_folder /
            "intraday_trade_candidates.csv"
        )

        if not input_file.exists():
            raise FileNotFoundError(
                f"Missing intraday file: {input_file}"
            )

        if not self.eod_file.exists():
            raise FileNotFoundError(
                f"Missing EOD file: {self.eod_file}"
            )

        intraday_df = pd.read_csv(
            input_file
        )

        eod_df = pd.read_excel(
            self.eod_file
        )

        result = calculate_outcomes(
            intraday_df,
            eod_df
        )

        output = (
            self.intraday_folder /
            "intraday_backtest_results.csv"
        )

        result.to_csv(
            output,
            index=False
        )

        return output


if __name__ == "__main__":

    print(
        "Use IntradayHistoricalReplayEngine(date folder, EOD file)"
    )
