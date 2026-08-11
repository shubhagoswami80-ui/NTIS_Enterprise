"""
NTIS Intraday Dashboard Health Panel

Purpose:
    Runtime health checks for dashboard visibility.

Rules:
    - No trading logic
    - No score calculation
    - No data modification
    - Dashboard compatibility only
"""

from pathlib import Path
import pandas as pd

from config_loader import OUTPUT_ROOT


REQUIRED_FILES = [
    "intraday_trade_candidates.csv",
    "intraday_probability_analysis.csv",
    "intraday_signal_evolution.csv",
]


def _check_file(path: Path) -> str:
    return "PASS" if path.exists() else "FAIL"


def _check_csv(path: Path) -> str:
    try:
        if not path.exists():
            return "FAIL"

        df = pd.read_csv(path)

        return "PASS" if not df.empty else "EMPTY"

    except Exception:
        return "FAIL"


def health_status(snapshot_path=None):

    result = {}

    # --------------------------------------------------
    # Output root
    # --------------------------------------------------

    result["Output Root"] = (
        "PASS"
        if OUTPUT_ROOT.exists()
        else "FAIL"
    )


    # --------------------------------------------------
    # Snapshot files
    # --------------------------------------------------

    if snapshot_path is None:

        result["Snapshot"] = "NOT PROVIDED"

        for file in REQUIRED_FILES:
            result[file] = "UNKNOWN"

        return result


    snapshot_path = Path(snapshot_path)


    result["Snapshot"] = (
        "PASS"
        if snapshot_path.exists()
        else "FAIL"
    )


    # --------------------------------------------------
    # Dataset validation
    # --------------------------------------------------

    for file in REQUIRED_FILES:

        result[file] = _check_csv(
            snapshot_path / file
        )


    return result