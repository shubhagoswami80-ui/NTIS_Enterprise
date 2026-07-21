"""
=========================================================
NTIS Replay Engine
Version : 1.0
Purpose :
    Execute Historical Replay
=========================================================
"""

from pathlib import Path

import pandas as pd

from replay_loader import ReplayLoader


class ReplayEngine:

    def __init__(self):

        self.loader = ReplayLoader()

    def run(
        self,
        historical_file,
        strategy,
        output_file=None
    ):

        df = self.loader.load_csv(historical_file)

        results = []

        for _, row in df.iterrows():

            result = strategy.evaluate(row)

            if result is not None:
                results.append(result)

        replay_df = pd.DataFrame(results)

        if output_file:

            output_file = Path(output_file)

            output_file.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            replay_df.to_csv(
                output_file,
                index=False
            )

        return replay_df