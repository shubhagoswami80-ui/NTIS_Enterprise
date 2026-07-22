"""
=========================================================
HMME Active Dependency Mapper v1.0

Purpose:
    Analyze remaining active similarity modules.

Input:
    similarity/*.py

Output:
    Output/
        hmme_active_dependency_map.csv
        hmme_module_groups.csv
        hmme_core_reduction_summary.txt

SAFE MODE:
    No move
    No delete
    No modification

=========================================================
"""

from pathlib import Path
import pandas as pd
import re


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
# Group Rules
# =====================================================

GROUP_RULES = {

    "CORE_ENGINE": [
        "engine",
        "core",
        "similarity",
        "calculator"
    ],

    "CONTROLLER": [
        "controller",
        "runner",
        "pipeline",
        "workflow"
    ],

    "MEMORY": [
        "memory",
        "cache",
        "repository"
    ],

    "LEARNING": [
        "learning",
        "adaptive",
        "training",
        "outcome"
    ],

    "DECISION": [
        "decision",
        "strategy",
        "validation"
    ],

    "EXECUTION": [
        "execution",
        "trade",
        "order"
    ],

    "REPORTING": [
        "report",
        "dashboard",
        "summary"
    ],

    "UTILITY": [
        "config",
        "utils",
        "helper",
        "schema"
    ]

}


# =====================================================
# Scan Files
# =====================================================

def load_files():

    return list(
        SIMILARITY_DIR.glob("*.py")
    )



# =====================================================
# Dependency Scan
# =====================================================

def scan_dependencies(files):

    results = []


    for file in files:

        imported_by = []
        referenced_by = []


        module_name = (
            file.stem
        )


        import_pattern = re.compile(
            rf"(import\s+{module_name}|"
            rf"from\s+{module_name}\s+import)",
            re.IGNORECASE
        )


        reference_pattern = re.compile(
            rf"\b{module_name}\b",
            re.IGNORECASE
        )


        for other in files:

            if other == file:
                continue


            try:

                text = other.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )


                if import_pattern.search(text):

                    imported_by.append(
                        other.name
                    )


                elif reference_pattern.search(text):

                    referenced_by.append(
                        other.name
                    )


            except Exception:

                pass


        results.append({

            "File":
            file.name,

            "Size":
            file.stat().st_size,

            "Imported_By":
            len(imported_by),

            "Referenced_By":
            len(referenced_by),

        })


    return results



# =====================================================
# Grouping
# =====================================================

def assign_group(filename):

    name = filename.lower()


    for group, keywords in GROUP_RULES.items():

        for keyword in keywords:

            if keyword in name:

                return group


    return "UNCLASSIFIED"



# =====================================================
# Main
# =====================================================

def main():

    print("="*60)
    print(
        "HMME ACTIVE DEPENDENCY MAPPER"
    )
    print("="*60)


    files = load_files()


    dependency_data = scan_dependencies(
        files
    )


    df = pd.DataFrame(
        dependency_data
    )


    df["Group"] = (
        df["File"]
        .apply(assign_group)
    )


    df.to_csv(
        OUTPUT_DIR /
        "hmme_active_dependency_map.csv",
        index=False
    )


    df[
        [
            "File",
            "Group"
        ]
    ].to_csv(
        OUTPUT_DIR /
        "hmme_module_groups.csv",
        index=False
    )


    summary = (

        "HMME ACTIVE REDUCTION SUMMARY\n"
        "============================\n\n"
        f"Active Files : {len(df)}\n\n"
        +
        df["Group"]
        .value_counts()
        .to_string()

    )


    (
        OUTPUT_DIR /
        "hmme_core_reduction_summary.txt"
    ).write_text(
        summary,
        encoding="utf-8"
    )


    print(summary)

    print(
        "\nReports created."
    )



if __name__ == "__main__":

    main()