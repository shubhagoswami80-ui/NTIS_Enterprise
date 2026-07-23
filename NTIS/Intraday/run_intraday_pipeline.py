"""
NTIS Intraday Pipeline Runner v1.5.6

Purpose:
Single command execution point.

Flow:
1. Run importer + registry check
2. If NEW/MODIFIED files exist, run full NTIS pipeline
3. If no changes, exit safely
"""

import subprocess
import sys


def run_step(script):
    print("=" * 70)
    print("Running:", script)

    result = subprocess.run(
        [sys.executable, script]
    )

    if result.returncode != 0:
        print("FAILED:", script)
        sys.exit(result.returncode)


def main():

    print("=" * 70)
    print("NTIS INTRADAY PIPELINE START")
    print("=" * 70)

    # Registry / importer check
    run_step("current_report_importer.py")

    # Continue existing NTIS processing chain
    modules = [
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
        "intraday_historical_replay_engine.py",
        "intraday_probability_calibration.py",
        "intraday_snapshot_evolution_engine.py"
    ]

    for module in modules:
        run_step(module)

    print("=" * 70)
    print("NTIS INTRADAY PIPELINE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
