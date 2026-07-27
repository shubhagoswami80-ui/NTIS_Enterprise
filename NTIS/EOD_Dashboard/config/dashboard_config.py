"""
NTIS EOD Dashboard Configuration

Read only configuration layer.
"""

from pathlib import Path


NTIS_ROOT = Path(__file__).resolve().parents[2]

EOD_OUTPUT_DIR = NTIS_ROOT.parent / "Output"

REQUIRED_EOD_FILES = {
    "market_master": "market_master.csv",
    "ranking": "ntis_ranked_stocks.csv",
    "probability": "ntis_probability_analysis.csv",
    "long_probability": "ntis_long_probability.csv",
    "short_probability": "ntis_short_probability.csv",
    "patterns": "ntis_pattern_analysis.csv",
    "trade_candidates": "ntis_trade_candidates.csv",
    "outcome": "ntis_outcome_report.csv",
}


def show_config():

    print("=" * 60)
    print("NTIS EOD DASHBOARD CONFIG")
    print("=" * 60)
    print("Output:", EOD_OUTPUT_DIR)
