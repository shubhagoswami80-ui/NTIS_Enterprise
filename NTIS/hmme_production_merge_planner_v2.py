"""
=========================================================
HMME Production Merge Planner v2.0

Purpose:
    Analyze active similarity modules and create
    consolidation plan.

SAFE MODE:
    No move
    No delete
    No code modification

=========================================================
"""

from pathlib import Path
import pandas as pd
import difflib


# =====================================================
# Paths
# =====================================================

BASE_DIR = Path(
    "E:/NSE_Daily_Analysis/NTIS"
)

SIMILARITY_DIR = (
    BASE_DIR /
    "similarity"
)

OUTPUT_DIR = (
    BASE_DIR /
    "Output"
)

OUTPUT_DIR.mkdir(
    exist_ok=True
)


# =====================================================
# Master keywords
# =====================================================

MASTER_KEYWORDS = [

    "engine",
    "controller",
    "master",
    "manager",
    "pipeline",
    "workflow"

]


# =====================================================
# Functional keywords
# =====================================================

FUNCTION_MAP = {

    "CORE":
    [
        "engine",
        "similarity",
        "calculator",
        "matcher",
        "feature"
    ],

    "MEMORY":
    [
        "memory",
        "cache",
        "repository",
        "store"
    ],

    "LEARNING":
    [
        "learning",
        "adaptive",
        "outcome",
        "training"
    ],

    "DECISION":
    [
        "decision",
        "strategy",
        "validation"
    ],

    "EXECUTION":
    [
        "execution",
        "trade",
        "order"
    ],

    "REPORT":
    [
        "report",
        "dashboard",
        "summary"
    ],

    "CONTROL":
    [
        "controller",
        "workflow",
        "pipeline",
        "runner"
    ]

}



# =====================================================
# Detect function
# =====================================================

def detect_function(filename):

    name = filename.lower()


    for group, words in FUNCTION_MAP.items():

        for word in words:

            if word in name:
                return group


    return "UNCLASSIFIED"



# =====================================================
# Master candidate
# =====================================================

def detect_role(filename):

    name = filename.lower()


    for word in MASTER_KEYWORDS:

        if word in name:

            return "MASTER_CANDIDATE"


    return "MODULE"



# =====================================================
# Similarity detection
# =====================================================

def find_similar(filename, files):

    matches = []


    base = filename.replace(
        ".py",
        ""
    )


    for other in files:

        if other == filename:
            continue


        ratio = difflib.SequenceMatcher(
            None,
            base,
            other.replace(".py","")
        ).ratio()


        if ratio >= 0.65:

            matches.append(
                other
            )


    return ",".join(matches)



# =====================================================
# Main
# =====================================================

def main():

    print("="*60)
    print(
        "HMME PRODUCTION MERGE PLANNER v2"
    )
    print("="*60)


    files = [

        f.name

        for f in SIMILARITY_DIR.glob("*.py")

    ]


    records = []


    for file in files:

        records.append({

            "File":
            file,

            "Function_Group":
            detect_function(file),

            "Role":
            detect_role(file),

            "Similar_Files":
            find_similar(
                file,
                files
            )

        })


    df = pd.DataFrame(
        records
    )


    df.to_csv(

        OUTPUT_DIR /
        "hmme_merge_plan.csv",

        index=False

    )


    candidates = df[
        df["Role"] ==
        "MASTER_CANDIDATE"
    ]


    candidates.to_csv(

        OUTPUT_DIR /
        "hmme_production_candidates.csv",

        index=False

    )


    unclassified = df[
        df["Function_Group"]
        ==
        "UNCLASSIFIED"
    ]


    unclassified.to_csv(

        OUTPUT_DIR /
        "hmme_unclassified_analysis.csv",

        index=False

    )


    summary = (

        "HMME PRODUCTION ARCHITECTURE PLAN\n"
        "================================\n\n"

        f"Total Files : {len(df)}\n\n"

        +
        df["Function_Group"]
        .value_counts()
        .to_string()

    )


    (
        OUTPUT_DIR /
        "hmme_final_architecture_plan.txt"
    ).write_text(

        summary,

        encoding="utf-8"

    )


    print(summary)

    print(
        "\nMerge planning completed."
    )


if __name__ == "__main__":

    main()