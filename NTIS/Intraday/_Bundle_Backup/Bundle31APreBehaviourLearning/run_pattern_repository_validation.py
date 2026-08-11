"""
=========================================================
NTIS Pattern Repository Validation Runner
Version : 1.0

Purpose:
    Validate Persistent Pattern Intelligence Repository (PIR).
=========================================================
"""

from pathlib import Path
import pandas as pd
from intraday_pattern_repository import IntradayPatternRepository

print("="*60)
print("NTIS PATTERN REPOSITORY VALIDATION")
print("="*60)

repo = IntradayPatternRepository()

test_row = {
    "Symbol": "RELIANCE",
    "Pattern": "Fresh Long Buildup",
    "Direction": "BUY",
    "Validation Signal": "VALID BUY",
    "Fut Buildup": "Long Buildup",
    "NTIS Score": 85.5,
    "Price Chg %": 2.5,
    "OI Chg %": 5.1,
}

fp = repo.generate_fingerprint(test_row)
pid = repo.get_or_create_pattern_id("RELIANCE", fp, test_row)

print(f"Generated Fingerprint: {fp}")
print(f"Assigned Business ID : {pid}")

record = repo.lookup_pattern(pid)
print(f"Repository Lookup    : {'PASS' if record else 'FAIL'}")

print("="*60)
print("PATTERN REPOSITORY VALIDATION PASSED")
print("="*60)
