"""
NTIS Architecture Scanner

Purpose:
    Read-only NTIS project discovery tool.

Scans:
    - Python files
    - Data files
    - Folder structure
    - Imports
    - CSV/XLSX references
    - Output references
    - Duplicate files

Generates:

    NTIS\tools\Architecture_Report\

        NTIS_Project_Architecture.md
        file_inventory.csv
        python_import_graph.csv
        data_flow_mapping.csv
        output_file_mapping.csv
        duplicate_file_report.csv
        dependency_summary.json


Safety:
    - Does NOT modify NTIS files
    - Does NOT execute NTIS engines
    - Only reads project structure
"""

from __future__ import annotations

import ast
import csv
import json
import hashlib

from pathlib import Path
from datetime import datetime


# =====================================================
# PATH CONFIGURATION
# =====================================================

NTIS_ROOT = Path(
    "E:/NSE_Daily_Analysis/NTIS"
)


TOOLS_DIR = (
    NTIS_ROOT /
    "tools"
)


REPORT_DIR = (
    TOOLS_DIR /
    "Architecture_Report"
)


# =====================================================
# IGNORE RULES
# =====================================================

IGNORE_DIRS = {

    ".git",

    ".venv",

    "__pycache__",

    # Generated reports
    "Architecture_Report",

    # Separate project
    "intraday"

}


# =====================================================
# FILE TYPES
# =====================================================

DATA_EXTENSIONS = {

    ".csv",
    ".xlsx",
    ".xls"

}


# =====================================================
# HELPERS
# =====================================================

def ensure_report_dir():

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )



def is_ignored(path: Path):

    return any(
        part in IGNORE_DIRS
        for part in path.parts
    )



def write_csv(
    filename,
    headers,
    rows
):

    output = (
        REPORT_DIR /
        filename
    )


    with open(
        output,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow(headers)

        writer.writerows(rows)



def file_hash(path):

    try:

        md5 = hashlib.md5()

        with open(
            path,
            "rb"
        ) as file:

            md5.update(
                file.read()
            )

        return md5.hexdigest()


    except Exception:

        return ""



# =====================================================
# FILE INVENTORY
# =====================================================

def scan_files():

    inventory = []


    for path in NTIS_ROOT.rglob("*"):


        if not path.is_file():

            continue


        if is_ignored(path):

            continue


        inventory.append(

            {

                "file":
                    str(
                        path.relative_to(
                            NTIS_ROOT
                        )
                    ),

                "extension":
                    path.suffix,

                "size":
                    path.stat().st_size,

                "modified":
                    datetime.fromtimestamp(
                        path.stat().st_mtime
                    ).isoformat(),

                "hash":
                    file_hash(path)

            }

        )


    return inventory



# =====================================================
# PYTHON IMPORT SCANNER
# =====================================================

def scan_imports():

    results = []


    for file in NTIS_ROOT.rglob("*.py"):


        if is_ignored(file):

            continue


        try:

            tree = ast.parse(

                file.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

            )


            for node in ast.walk(tree):


                if isinstance(
                    node,
                    ast.Import
                ):


                    for item in node.names:


                        results.append(

                            [

                                str(
                                    file.relative_to(
                                        NTIS_ROOT
                                    )
                                ),

                                item.name,

                                "import"

                            ]

                        )



                elif isinstance(
                    node,
                    ast.ImportFrom
                ):


                    results.append(

                        [

                            str(
                                file.relative_to(
                                    NTIS_ROOT
                                )
                            ),

                            node.module or "",

                            "from_import"

                        ]

                    )


        except Exception:

            pass


    return results



# =====================================================
# DATA FLOW SCANNER
# =====================================================

def scan_data_references():

    results = []


    for file in NTIS_ROOT.rglob("*.py"):


        if is_ignored(file):

            continue


        try:

            content = file.read_text(

                encoding="utf-8",

                errors="ignore"

            )


            for ext in DATA_EXTENSIONS:


                for line in content.splitlines():


                    if ext in line:


                        results.append(

                            [

                                str(
                                    file.relative_to(
                                        NTIS_ROOT
                                    )
                                ),

                                line.strip(),

                                ext

                            ]

                        )


        except Exception:

            pass


    return results



# =====================================================
# OUTPUT DETECTION
# =====================================================

def scan_outputs():

    results = []


    for file in NTIS_ROOT.rglob("*.py"):


        if is_ignored(file):

            continue


        try:

            content = file.read_text(

                encoding="utf-8",

                errors="ignore"

            )


            for line in content.splitlines():


                if (

                    "OUTPUT_FILE"
                    in line

                    or

                    "to_csv"
                    in line

                ):


                    results.append(

                        [

                            str(
                                file.relative_to(
                                    NTIS_ROOT
                                )
                            ),

                            line.strip()

                        ]

                    )


        except Exception:

            pass


    return results



# =====================================================
# DUPLICATE DETECTION
# =====================================================

def scan_duplicates(files):

    hashes = {}

    duplicates = []


    for item in files:


        digest = item["hash"]


        if not digest:

            continue



        if digest in hashes:


            duplicates.append(

                [

                    hashes[digest],

                    item["file"]

                ]

            )


        else:

            hashes[digest] = item["file"]


    return duplicates



# =====================================================
# ARCHITECTURE REPORT
# =====================================================

def create_markdown(files):

    lines = []


    lines.append(

        "# NTIS Project Architecture Report"

    )


    lines.append("")

    lines.append(

        f"Generated: {datetime.now()}"

    )


    lines.append("")

    lines.append(

        "## Folder Structure Summary"

    )


    folders = sorted(

        {

            str(
                Path(
                    item["file"]
                ).parent
            )

            for item in files

        }

    )


    for folder in folders:

        lines.append(

            f"- {folder}"

        )


    lines.append("")

    lines.append(

        f"Total Files Scanned: {len(files)}"

    )


    output = (

        REPORT_DIR /

        "NTIS_Project_Architecture.md"

    )


    output.write_text(

        "\n".join(lines),

        encoding="utf-8"

    )



# =====================================================
# MAIN
# =====================================================

def main():

    print(
        "NTIS Architecture Scanner Started"
    )


    ensure_report_dir()


    files = scan_files()


    imports = scan_imports()


    data_refs = scan_data_references()


    outputs = scan_outputs()


    duplicates = scan_duplicates(
        files
    )


    write_csv(

        "file_inventory.csv",

        [

            "file",
            "extension",
            "size",
            "modified",
            "hash"

        ],

        [

            list(item.values())

            for item in files

        ]

    )


    write_csv(

        "python_import_graph.csv",

        [

            "source",
            "target",
            "type"

        ],

        imports

    )


    write_csv(

        "data_flow_mapping.csv",

        [

            "source",
            "reference",
            "type"

        ],

        data_refs

    )


    write_csv(

        "output_file_mapping.csv",

        [

            "source",
            "reference"

        ],

        outputs

    )


    write_csv(

        "duplicate_file_report.csv",

        [

            "original",
            "duplicate"

        ],

        duplicates

    )


    summary = {

        "generated":

            str(datetime.now()),

        "files_scanned":

            len(files),

        "imports":

            len(imports),

        "data_references":

            len(data_refs),

        "output_references":

            len(outputs),

        "duplicates":

            len(duplicates)

    }


    (

        REPORT_DIR /

        "dependency_summary.json"

    ).write_text(

        json.dumps(

            summary,

            indent=4

        ),

        encoding="utf-8"

    )


    create_markdown(
        files
    )


    print()

    print(
        "Completed"
    )

    print(
        REPORT_DIR
    )



if __name__ == "__main__":

    main()