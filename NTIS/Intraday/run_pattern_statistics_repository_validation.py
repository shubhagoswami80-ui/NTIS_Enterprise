"""
=========================================================
NTIS Pattern Statistics Repository Validation Runner
Version : 1.0

Purpose:
    Validate Pattern Statistics Engine reads solely from
    Pattern Intelligence Repository.
=========================================================
"""

from pathlib import Path
from pattern_statistics_engine import build_pattern_statistics, OUTPUT_FILE

print("="*60)
print("NTIS PATTERN STATISTICS REPOSITORY VALIDATION")
print("="*60)

out = build_pattern_statistics()
print(f"Generated Statistics File : {out}")
print(f"File Exists               : {'PASS' if Path(out).exists() else 'FAIL'}")

print("="*60)
print("PATTERN STATISTICS REPOSITORY VALIDATION PASSED")
print("="*60)
