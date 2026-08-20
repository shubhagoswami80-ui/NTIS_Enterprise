
from pathlib import Path
import ast

TARGET = Path(__file__).resolve().parent / "intraday_dashboard.py"
BACKUP = TARGET.with_name("intraday_dashboard_pre_phase22a_cleanup.py")

REMOVE = {
    "_ntis_text",
    "_run_next_snapshot",
    "_exact_pattern_history",
    "_predictive_label",
}

source = TARGET.read_text(encoding="utf-8")
tree = ast.parse(source)

ranges = []
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in REMOVE:
        end = getattr(node, "end_lineno", None)
        if end:
            ranges.append((node.lineno, end))

if not ranges:
    print("No obsolete duplicate helper functions found. Nothing changed.")
    raise SystemExit(0)

BACKUP.write_text(source, encoding="utf-8")

lines = source.splitlines(keepends=True)
for start, end in sorted(ranges, reverse=True):
    del lines[start - 1:end]

TARGET.write_text("".join(lines), encoding="utf-8")

print("Removed obsolete duplicate helper functions:")
for name in sorted(REMOVE):
    print(f"  - {name}")
print(f"Backup: {BACKUP.name}")
print("Next: python -m py_compile intraday_dashboard.py")
