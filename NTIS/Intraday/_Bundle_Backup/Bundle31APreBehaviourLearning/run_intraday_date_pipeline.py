
"""
NTIS Intraday Date Pipeline Runner
Subprocess date propagation fix
"""

import sys
import os
import subprocess

from intraday_execution_context import set_processing_date


MODULES = [
    "current_report_importer.py",
    "intraday_market_master_builder.py",
    "intraday_market_master_cleaner.py",
    "intraday_market_master_normalizer.py",
    "intraday_market_master_schema.py",
    "intraday_scoring_engine.py",
    "intraday_pattern_engine.py",
    "intraday_probability_engine.py",
    "intraday_trade_validation_engine.py",
    "intraday_daily_report_generator.py",
    "intraday_accuracy_tracker.py",
    "intraday_snapshot_evolution_engine.py"
]


def run_step(script):

    print("=" * 60)
    print("Running:", script)

    result = subprocess.run(
        [sys.executable, script],
        env=os.environ.copy()
    )

    if result.returncode != 0:
        raise SystemExit(f"FAILED: {script}")


def main():

    if len(sys.argv) < 2:
        print("Usage: python run_intraday_date_pipeline.py YYYY-MM-DD")
        raise SystemExit(1)

    process_date = sys.argv[1]

    os.environ["NTIS_PROCESSING_DATE"] = process_date

    set_processing_date(process_date)

    print("=" * 60)
    print("NTIS INTRADAY DATE PIPELINE")
    print("Processing Date:", process_date)
    print("=" * 60)

    for module in MODULES:
        run_step(module)


if __name__ == "__main__":
    main()
