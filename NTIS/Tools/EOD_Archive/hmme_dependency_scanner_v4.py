"""
=========================================================
HMME Consolidation Dependency Scanner v4.0

Purpose:
    Scan candidate files before archive/delete.

SAFE MODE:
    No move
    No delete

Checks:
    - import dependency
    - reference dependency
    - controller usage

=========================================================
"""

from pathlib import Path
import pandas as pd
import re


# =====================================================
# Paths
# =====================================================

BASE_DIR = Path("E:/NSE_Daily_Analysis/NTIS")

SIMILARITY_DIR = BASE_DIR / "similarity"

OUTPUT_DIR = BASE_DIR / "Output"


DELETE_FILE = (
    OUTPUT_DIR /
    "hmme_review_delete_candidate.csv"
)

REVIEW_FILE = (
    OUTPUT_DIR /
    "hmme_review_required.csv"
)


# =====================================================
# Scan all Python files
# =====================================================

def load_source_files():

    files = []

    for path in BASE_DIR.rglob("*.py"):

        if "similarity" in str(path):

            files.append(path)

    return files



# =====================================================
# Dependency Check
# =====================================================

def check_dependency(
        filename,
        source_files):


    module_name = filename.replace(
        ".py",
        ""
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


    imported = []

    referenced = []


    for file in source_files:

        if file.name == filename:
            continue


        try:

            content = file.read_text(
                encoding="utf-8",
                errors="ignore"
            )


            if import_pattern.search(content):

                imported.append(
                    str(file)
                )


            elif reference_pattern.search(content):

                referenced.append(
                    str(file)
                )


        except Exception:

            pass



    return imported, referenced



# =====================================================
# Classification
# =====================================================

def classify(
        filename,
        imported,
        referenced):


    if imported:

        return "KEEP"


    if referenced:

        return "REVIEW"


    return "SAFE_DELETE"



# =====================================================
# Main
# =====================================================

def process_file_list(
        input_file,
        source_files,
        results):


    if not input_file.exists():

        return


    df = pd.read_csv(
        input_file
    )


    for _, row in df.iterrows():

        filename = row["File"]


        imported, referenced = (
            check_dependency(
                filename,
                source_files
            )
        )


        results.append({

            "File":
            filename,

            "Imported_By":
            len(imported),

            "Referenced_By":
            len(referenced),

            "Classification":
            classify(
                filename,
                imported,
                referenced
            )

        })



def main():

    print("=" * 60)
    print("HMME DEPENDENCY SCANNER v4")
    print("=" * 60)


    source_files = load_source_files()


    results = []


    process_file_list(
        DELETE_FILE,
        source_files,
        results
    )


    process_file_list(
        REVIEW_FILE,
        source_files,
        results
    )


    output = pd.DataFrame(
        results
    )


    output.to_csv(
        OUTPUT_DIR /
        "hmme_dependency_analysis.csv",
        index=False
    )


    for name in [
        "KEEP",
        "REVIEW",
        "SAFE_DELETE"
    ]:

        output[
            output["Classification"] == name
        ].to_csv(
            OUTPUT_DIR /
            f"hmme_dependency_{name.lower()}.csv",
            index=False
        )


    print()

    print(
        output["Classification"]
        .value_counts()
    )


    print()

    print(
        "Dependency analysis completed"
    )



if __name__ == "__main__":

    main()