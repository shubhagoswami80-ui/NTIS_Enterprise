"""
=========================================================
NTIS Intraday Learning Outcome Updater
Version : 1.1

Purpose:
    Update learning memory with replay outcomes.

Input:
    intraday_backtest_results.csv
    intraday_learning_memory.csv

Output:
    Updated intraday_learning_memory.csv

Fix:
    - Handles existing CSV datatype issues
    - Preserves learning memory schema
=========================================================
"""

from pathlib import Path
import pandas as pd

from config_loader import LEARNING_ROOT
from intraday_pattern_repository import IntradayPatternRepository
from intraday_pattern_lifecycle_engine import IntradayPatternLifecycleEngine


MEMORY_FILE = (
    LEARNING_ROOT /
    "intraday_learning_memory.csv"
)



class IntradayLearningOutcomeUpdater:


    def __init__(
        self,
        replay_file
    ):

        self.replay_file = Path(
            replay_file
        )



    def run(self):

        if not self.replay_file.exists():

            raise FileNotFoundError(
                f"Replay file not found: {self.replay_file}"
            )


        if not MEMORY_FILE.exists():

            raise FileNotFoundError(
                f"Learning memory not found: {MEMORY_FILE}"
            )


        replay = pd.read_csv(
            self.replay_file
        )


        memory = pd.read_csv(
            MEMORY_FILE,
            dtype=str
        )


        if replay.empty or memory.empty:

            return MEMORY_FILE



        # Ensure required columns exist

        for col in [
            "Future_Move_%",
            "Target_Hit",
            "Stop_Loss_Hit"
        ]:

            if col not in memory.columns:

                memory[col] = ""



        for index, row in memory.iterrows():


            matches = replay[

                (replay["Symbol"].astype(str) == str(row["Symbol"])) &

                (replay["Pattern"].astype(str) == str(row["Pattern"]))

            ]


            if matches.empty:

                continue



            trade = matches.iloc[0]


            outcome = str(
                trade.get(
                    "Outcome",
                    "PENDING"
                )
            )


            memory.at[
                index,
                "Outcome"
            ] = outcome



            memory.at[
                index,
                "Future_Move_%"
            ] = str(
                trade.get(
                    "Return %",
                    0
                )
            )



            memory.at[
                index,
                "Target_Hit"
            ] = (
                "YES"
                if outcome == "TARGET HIT"
                else
                "NO"
            )



            memory.at[
                index,
                "Stop_Loss_Hit"
            ] = (
                "YES"
                if outcome == "STOP LOSS HIT"
                else
                "NO"
            )



        memory.to_csv(
            MEMORY_FILE,
            index=False
        )

        # Synchronize updated learning outcomes with Pattern Intelligence Repository
        try:
            repo = IntradayPatternRepository()
            lifecycle = IntradayPatternLifecycleEngine(repo)
            lifecycle.integrate_outcomes(memory)
            lifecycle.evaluate_lifecycle()
        except Exception:
            pass

        return MEMORY_FILE



if __name__ == "__main__":


    print(
        "Use:"
    )

    print(
        "IntradayLearningOutcomeUpdater(replay_file).run()"
    )