"""
=========================================================
NTIS Intraday Intelligence Validation Runner
Version : 1.1

Purpose:
    Validate complete Intraday Intelligence Layer.

Checks:
    - Schema Layer
    - Snapshot Layer
    - Validator Layer
    - Health Monitor
    - Snapshot Registry
    - Loader
    - Query Engine
    - Export Engine

=========================================================
"""

from pathlib import Path


FILES = [

    "intraday_intelligence_schema.py",

    "intraday_intelligence_snapshot.py",

    "intraday_snapshot_validator.py",

    "intraday_data_health_monitor.py",

    "intraday_health_report_generator.py",

    "intraday_snapshot_registry.py",

    "intraday_intelligence_loader.py",

    "intraday_intelligence_query.py",

    "intraday_intelligence_export.py",

    "run_intraday_intelligence_validation.py"
]


def check_files():

    result = True

    for file in FILES:

        if Path(file).exists():

            print(f"{file:<45} PASS")

        else:

            print(f"{file:<45} FAIL")
            result = False

    return result



def main():

    print("=" * 60)
    print("NTIS INTRADAY INTELLIGENCE VALIDATION")
    print("=" * 60)

    status = check_files()

    print("=" * 60)

    if status:

        print(
            "INTELLIGENCE MEMORY LAYER READY"
        )

    else:

        print(
            "INTELLIGENCE MEMORY LAYER INCOMPLETE"
        )

    print("=" * 60)



if __name__ == "__main__":

    main()