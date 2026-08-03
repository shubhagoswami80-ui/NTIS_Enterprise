"""
=========================================================
NTIS Enterprise Application
Version : 3.0
Purpose :
    Enterprise bootstrap for complete NTIS-EOD pipeline.

Frozen Runtime Contract

Importer
    ↓
Scoring Engine
    ↓
Pattern Engine
    ↓
Probability Engine
    ↓
Similarity Intelligence
    ↓
Trade Validation
    ↓
Outcome Engine
    ↓
History Manager

No business logic exists here.
This file only orchestrates execution.
=========================================================
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from importlib import import_module


# ==========================================================
# PATHS
# ==========================================================

BASE_DIR = Path("E:/NSE_Daily_Analysis")

LOG_DIR = BASE_DIR / "Logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "ntis_enterprise.log"


# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

LOGGER = logging.getLogger("NTIS")


# ==========================================================
# PIPELINE
# ==========================================================

PIPELINE = [

    (
        "Importer",
        "importer"
    ),

    (
        "Scoring Engine",
        "scoring_engine"
    ),

    (
        "Pattern Engine",
        "pattern_engine"
    ),

    (
        "Probability Engine",
        "probability_engine"
    ),

    (
        "Historical Intelligence",
        "similarity_core_clean.integration.production_runtime"
    ),

    (
        "Trade Validation",
        "trade_validation_engine"
    ),

    (
        "Outcome Engine",
        "outcome_engine"
    ),

    (
        "History Manager",
        "history_manager"
    )

]


# ==========================================================
# EXECUTE MODULE
# ==========================================================

def execute_module(name: str, module_name: str):

    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    LOGGER.info("Starting : %s", name)

    start = time.perf_counter()

    module = import_module(module_name)

    if not hasattr(module, "main"):

        raise AttributeError(
            f"{module_name} does not expose main()"
        )

    module.main()

    elapsed = round(
        time.perf_counter() - start,
        2
    )

    LOGGER.info(
        "%s completed in %.2f sec",
        name,
        elapsed
    )

    print(f"Completed in {elapsed} sec")


# ==========================================================
# MAIN
# ==========================================================

def main():

    total_start = time.perf_counter()

    print("=" * 80)
    print("NTIS ENTERPRISE")
    print("=" * 80)

    LOGGER.info("NTIS Pipeline Started")

    try:

        for name, module in PIPELINE:

            execute_module(
                name,
                module
            )

    except Exception as exc:

        LOGGER.exception(exc)

        print()
        print("=" * 80)
        print("PIPELINE FAILED")
        print("=" * 80)
        print(exc)

        sys.exit(1)

    total = round(
        time.perf_counter() - total_start,
        2
    )

    LOGGER.info(
        "Pipeline Completed Successfully"
    )

    LOGGER.info(
        "Execution Time : %.2f sec",
        total
    )

    print()
    print("=" * 80)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print(f"Execution Time : {total} sec")


# ==========================================================
# START
# ==========================================================

if __name__ == "__main__":

    main()