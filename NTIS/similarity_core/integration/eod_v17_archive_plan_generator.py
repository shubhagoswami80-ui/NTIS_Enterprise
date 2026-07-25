
"""
NTIS V17 Archive Plan Generator

Phase 6C
Creates archive planning report only.

No files moved.
No files deleted.
No imports changed.
"""

from pathlib import Path


BASE = Path(__file__).parent
REPORT_DIR = BASE / "V17_Archive_Plan"


KEEP_FILES = {
    "eod_data_resolution_core_v17.py",
    "eod_replay_dashboard_core_v17.py",
    "eod_runtime_control_core_v17.py",
    "eod_service_management_core_v17.py",
    "eod_governance_audit_core_v17.py",
    "eod_production_control_core_v17.py",
    "eod_final_integration_core_v17.py",
}


def generate_plan():

    REPORT_DIR.mkdir(exist_ok=True)

    keep = []
    archive = []

    for file in BASE.glob("*_v17.py"):

        name = file.name.lower()

        if file.name in KEEP_FILES:
            keep.append(file.name)

        elif any(k in name for k in [
            "activation",
            "checkpoint",
            "validation",
            "shadow",
            "dry_run",
            "switch",
            "migration"
        ]):
            archive.append(file.name)

    (REPORT_DIR / "KEEP_PRODUCTION_CORE.txt").write_text(
        "\n".join(sorted(keep)),
        encoding="utf-8"
    )

    (REPORT_DIR / "ARCHIVE_MIGRATION_TOOLS.txt").write_text(
        "\n".join(sorted(archive)),
        encoding="utf-8"
    )

    print("V17 ARCHIVE PLAN READY")
    print("KEEP_PRODUCTION_CORE:", len(keep))
    print("ARCHIVE_MIGRATION_TOOLS:", len(archive))
    print("ACTION: REVIEW ONLY")


if __name__ == "__main__":
    generate_plan()
