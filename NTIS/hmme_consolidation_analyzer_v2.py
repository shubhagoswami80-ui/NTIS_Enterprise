"""
=========================================================
HMME Consolidation Analyzer v2.0
SAFE MODE

Purpose:
    Classify similarity folder files into:
    KEEP
    ARCHIVE
    REVIEW

No files moved.
No files deleted.

=========================================================
"""

from pathlib import Path
import pandas as pd
import fnmatch
from datetime import datetime


# =====================================================
# Paths
# =====================================================

BASE_DIR = Path("E:/NSE_Daily_Analysis/NTIS")

SIMILARITY_DIR = BASE_DIR / "similarity"

OUTPUT_DIR = BASE_DIR / "Output"

OUTPUT_DIR.mkdir(exist_ok=True)


# =====================================================
# Protected / Critical Files
# =====================================================

KEEP_FILES = {

    # Core engines
    "hmme_engine.py",
    "historical_similarity_engine.py",
    "candidate_selector.py",
    "calibration_engine.py",

    # Feature
    "feature_engineering.py",
    "feature_normalizer.py",
    "feature_models.py",
    "feature_config.py",
    "feature_cache_manager.py",

    # Similarity core
    "similarity_loader.py",
    "similarity_models.py",
    "similarity_calculator.py",
    "similarity_probability.py",
    "similarity_ranker.py",
    "similarity_report.py",

    # Memory
    "memory_index.py",
    "memory_repository.py",
    "memory_models.py",

    # Controllers
    "hmme_controller.py",
    "hmme_final_master_controller.py",
    "hmme_autonomous_master_controller.py",
    "production_master_controller.py",

    # Protected
    "hmme_decision_schema.py",
    "hmme_execution_summary.py",
    "performance_tracker.py",
    "future_Cache_manager.py",
    "hmme_validation_report.py",

    # Config
    "hmme18_config.py",
    "hmme41_paths.py",
}


# =====================================================
# Archive Patterns
# =====================================================

ARCHIVE_PATTERNS = [

    # Generated expansion modules
    "hmme_*_module_*.py",

    # Release documentation
    "HMME*_Release_Notes.txt",

    # Tests
    "*_test.py",

]


# =====================================================
# Merge Candidates
# =====================================================

MERGE_PATTERNS = [

    "confidence_*.py",
    "decision_*.py",
    "execution_*.py",
    "production_*.py",
    "runtime_*.py",
    "model_*.py",
    "risk_*.py",
    "report_*.py",
]


# =====================================================
# Classification
# =====================================================

def classify(filename):

    if filename in KEEP_FILES:
        return "KEEP"


    for pattern in ARCHIVE_PATTERNS:
        if fnmatch.fnmatch(filename, pattern):
            return "ARCHIVE"


    for pattern in MERGE_PATTERNS:
        if fnmatch.fnmatch(filename, pattern):
            return "REVIEW"


    return "REVIEW"



# =====================================================
# Main
# =====================================================

def main():

    print("=" * 60)
    print("HMME CONSOLIDATION ANALYZER v2")
    print("=" * 60)


    records = []


    for file in SIMILARITY_DIR.iterdir():

        if file.is_file():

            category = classify(file.name)


            records.append({

                "File": file.name,

                "Size(Bytes)": file.stat().st_size,

                "Modified":

                datetime.fromtimestamp(
                    file.stat().st_mtime
                ).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

                "Category": category

            })


    df = pd.DataFrame(records)


    for category in [
        "KEEP",
        "ARCHIVE",
        "REVIEW"
    ]:

        output = (
            OUTPUT_DIR /
            f"hmme_{category.lower()}_list.csv"
        )


        df[
            df["Category"] == category
        ].to_csv(
            output,
            index=False
        )


    summary = (

        "HMME CONSOLIDATION SUMMARY\n"
        "==========================\n\n"
        f"KEEP    : {len(df[df.Category=='KEEP'])}\n"
        f"ARCHIVE : {len(df[df.Category=='ARCHIVE'])}\n"
        f"REVIEW  : {len(df[df.Category=='REVIEW'])}\n"

    )


    (
        OUTPUT_DIR /
        "hmme_consolidation_summary.txt"
    ).write_text(
        summary,
        encoding="utf-8"
    )


    print(summary)

    print("Reports created in Output folder")



if __name__ == "__main__":
    main()