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


REQUIRED_INTELLIGENCE_FIELDS = [
    "Business_Pattern_ID",
    "Pattern_Fingerprint",
    "Occurrences",
    "Success_%",
    "Average_PnL",
    "Confidence_Score",
    "Historical_Probability",
    "Historical_Confidence",
    "Evidence_Level",
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


def _check_intelligence_schema(path: Path) -> str:
    try:
        if not path.exists():
            return "MISSING"
        df = pd.read_csv(path, nrows=5)
        missing = [f for f in REQUIRED_INTELLIGENCE_FIELDS if f not in df.columns]
        return "PASS" if not missing else "LEGACY_OR_PARTIAL"
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
    # Pipeline status check
    # --------------------------------------------------

    from intraday_config import INPUT_FOLDER
    has_reports = INPUT_FOLDER.exists() and list(INPUT_FOLDER.glob("*.xlsx"))
    if not has_reports:
        result["Pipeline Status"] = "NO_INTRADAY_DATA"
        result["Severity"] = "INFO"
        result["Message"] = "No intraday reports available for the selected processing date."
    else:
        result["Pipeline Status"] = "NORMAL"
        result["Severity"] = "INFO"
        result["Message"] = "Intraday reports available."

    from config_loader import LEARNING_ROOT
    repo_file = LEARNING_ROOT / "intraday_pattern_repository.csv"
    result["Historical Intelligence"] = "EXISTS" if repo_file.exists() else "NOT FOUND"


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

    prob_file = snapshot_path / "intraday_probability_analysis.csv"
    if prob_file.exists():
        result["Intelligence Schema"] = _check_intelligence_schema(prob_file)


    return result