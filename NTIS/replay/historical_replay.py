"""
=========================================================
NTIS Historical Replay Runner
Version : 1.0
Purpose :
    Execute the complete Historical Replay workflow
=========================================================
"""

from pathlib import Path

from replay_engine import ReplayEngine
from replay_validator import ReplayValidator
from replay_report import ReplayReport


class HistoricalReplay:

    def __init__(self):

        self.engine = ReplayEngine()
        self.validator = ReplayValidator()
        self.report = ReplayReport()

    def run(
        self,
        historical_file,
        strategy,
        output_folder,
    ):

        output_folder = Path(output_folder)
        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        replay_results = self.engine.run(
            historical_file=historical_file,
            strategy=strategy,
            output_file=output_folder / "replay_results.csv",
        )

        summary = self.validator.validate(
            replay_results
        )

        statistics = self.validator.calculate_statistics(
            replay_results
        )

        self.report.save_summary(
            summary,
            output_folder / "replay_summary.csv",
        )

        self.report.save_results(
            statistics,
            output_folder / "replay_statistics.csv",
        )

        self.report.print_summary(
            summary
        )

        return replay_results, summary, statistics


if __name__ == "__main__":

    print("=" * 55)
    print("NTIS HISTORICAL REPLAY ENGINE")
    print("=" * 55)
    print("Import this module into the NTIS pipeline.")