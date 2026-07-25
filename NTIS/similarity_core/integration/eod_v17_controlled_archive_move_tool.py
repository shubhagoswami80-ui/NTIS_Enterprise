
"""
NTIS V17 Controlled Archive Move Tool

Phase 6D

Purpose:
Move only approved migration artifacts to archive.

Safety:
- No deletion
- No core movement
- No import modification
"""

from pathlib import Path
import shutil


BASE = Path(__file__).parent
ARCHIVE = BASE.parent / "Archive" / "V17_Migration_Tools"


KEYWORDS = [
    "activation",
    "checkpoint",
    "validation",
    "shadow",
    "dry_run",
    "switch",
    "migration",
]


def move_migration_tools(dry_run=True):

    ARCHIVE.mkdir(parents=True, exist_ok=True)

    moved = []

    for file in BASE.glob("*_v17.py"):

        name = file.name.lower()

        if any(k in name for k in KEYWORDS):

            target = ARCHIVE / file.name

            print(
                "[DRY RUN] " if dry_run else "[MOVE] ",
                file.name
            )

            if not dry_run:
                shutil.move(str(file), str(target))

            moved.append(file.name)

    print("=" * 60)
    print("V17 CONTROLLED ARCHIVE MOVE")
    print("=" * 60)
    print("FILES SELECTED:", len(moved))
    print("MODE:", "DRY RUN" if dry_run else "EXECUTE")

    return moved


if __name__ == "__main__":
    move_migration_tools(dry_run=True)
