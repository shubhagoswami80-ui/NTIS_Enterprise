
"""
NTIS V17 Final Archive Executor

Phase 6D.2

Moves only approved migration artifacts.
Uses ARCHIVE_CANDIDATES.txt as source list.

Safety:
- No deletion
- No active module movement
- No config changes
"""

from pathlib import Path
import shutil
from datetime import datetime


BASE = Path(__file__).parent
ARCHIVE_LIST = BASE / "V17_ACTIVE_MODULE_REVIEW" / "ARCHIVE_CANDIDATES.txt"

ARCHIVE_TARGET = BASE.parent.parent / "Archive" / "V17_Migration_Tools"


def execute_archive_move(dry_run=True):

    if not ARCHIVE_LIST.exists():
        raise FileNotFoundError(
            "ARCHIVE_CANDIDATES.txt not found"
        )

    ARCHIVE_TARGET.mkdir(parents=True, exist_ok=True)

    files = [
        x.strip()
        for x in ARCHIVE_LIST.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]

    log = []

    for filename in files:

        source = BASE / filename
        target = ARCHIVE_TARGET / filename

        if source.exists():

            if dry_run:
                action = "DRY RUN"
            else:
                shutil.move(str(source), str(target))
                action = "MOVED"

            log.append(f"{action}: {filename}")
            print(action, filename)

    report = BASE / f"V17_ARCHIVE_MOVE_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report.write_text("\n".join(log), encoding="utf-8")

    print("=" * 60)
    print("V17 FINAL ARCHIVE EXECUTOR")
    print("=" * 60)
    print("SELECTED FILES:", len(files))
    print("MODE:", "DRY RUN" if dry_run else "EXECUTE")
    print("REPORT:", report.name)

    return log


if __name__ == "__main__":
    execute_archive_move(dry_run=True)
