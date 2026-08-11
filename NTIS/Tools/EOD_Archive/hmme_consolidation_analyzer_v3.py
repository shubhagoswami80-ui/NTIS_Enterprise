"""
=========================================================
HMME Consolidation Analyzer v3.0

Purpose:
    Analyze REVIEW files only.

Input:
    Output/hmme_review_list.csv

Output:
    Detailed classification reports.

SAFE MODE:
    No move
    No delete

=========================================================
"""

from pathlib import Path
import pandas as pd


BASE_DIR = Path("E:/NSE_Daily_Analysis/NTIS")

OUTPUT_DIR = BASE_DIR / "Output"

INPUT_FILE = OUTPUT_DIR / "hmme_review_list.csv"


# =====================================================
# Classification Keywords
# =====================================================

CORE_KEYWORDS = [
    "engine",
    "controller",
    "bridge",
    "pipeline",
    "runner",
    "manager",
    "adapter",
    "schema",
    "validator",
]


SUPPORT_KEYWORDS = [
    "config",
    "model",
    "loader",
    "builder",
    "utility",
    "helper",
    "cache",
]


MERGE_KEYWORDS = [
    "optimizer",
    "monitor",
    "tracker",
    "analyzer",
    "generator",
    "report",
    "service",
    "handler",
]


ARCHIVE_KEYWORDS = [
    "release",
    "experiment",
    "module",
    "test",
    "demo",
]


def classify(filename, size):

    name = filename.lower()


    # Very small placeholders
    if size < 40:
        return "DELETE_CANDIDATE"


    for word in CORE_KEYWORDS:
        if word in name:
            return "KEEP_CORE"


    for word in SUPPORT_KEYWORDS:
        if word in name:
            return "KEEP_SUPPORT"


    for word in MERGE_KEYWORDS:
        if word in name:
            return "MERGE"


    for word in ARCHIVE_KEYWORDS:
        if word in name:
            return "ARCHIVE"


    return "REVIEW_REQUIRED"



def main():

    print("=" * 60)
    print("HMME CONSOLIDATION ANALYZER v3")
    print("=" * 60)


    if not INPUT_FILE.exists():

        print(
            "Missing:",
            INPUT_FILE
        )
        return


    df = pd.read_csv(INPUT_FILE)


    results = []


    for _, row in df.iterrows():

        results.append({

            "File":
            row["File"],

            "Size":
            row["Size(Bytes)"],

            "Classification":
            classify(
                row["File"],
                row["Size(Bytes)"]
            )

        })


    output = pd.DataFrame(results)


    reports = {

        "KEEP_CORE":
        "hmme_review_keep_core.csv",

        "KEEP_SUPPORT":
        "hmme_review_keep_support.csv",

        "MERGE":
        "hmme_review_merge.csv",

        "ARCHIVE":
        "hmme_review_archive.csv",

        "DELETE_CANDIDATE":
        "hmme_review_delete_candidate.csv",

        "REVIEW_REQUIRED":
        "hmme_review_required.csv",
    }


    for category, filename in reports.items():

        output[
            output["Classification"] == category
        ].to_csv(
            OUTPUT_DIR / filename,
            index=False
        )


    summary = (
        "\nHMME REVIEW CLASSIFICATION\n"
        "==========================\n\n"
    )


    summary += (
        output["Classification"]
        .value_counts()
        .to_string()
    )


    (
        OUTPUT_DIR /
        "hmme_review_summary.txt"
    ).write_text(
        summary,
        encoding="utf-8"
    )


    print(summary)

    print("\nReports created.")



if __name__ == "__main__":
    main()