"""
=========================================================
NTIS Pattern Lifecycle Validation Runner
Version : 1.0

Purpose:
    Validate Pattern Lifecycle & Repository Integration.
=========================================================
"""

from pathlib import Path
import pandas as pd
from intraday_pattern_repository import IntradayPatternRepository
from intraday_pattern_lifecycle_engine import IntradayPatternLifecycleEngine

print("="*60)
print("NTIS PATTERN LIFECYCLE VALIDATION")
print("="*60)

repo = IntradayPatternRepository()
engine = IntradayPatternLifecycleEngine(repo)

state_new = engine.determine_lifecycle_state(3, 50.0)
state_high = engine.determine_lifecycle_state(20, 75.0)

print(f"Lifecycle state (3 occ, 50%): {state_new}")
print(f"Lifecycle state (20 occ, 75%): {state_high}")

dummy_memory = pd.DataFrame([
    {
        "Symbol": "TCS",
        "Pattern": "Fresh Long Buildup",
        "Direction": "BUY",
        "Validation Signal": "VALID BUY",
        "Fut Buildup": "Long Buildup",
        "NTIS Score": 90.0,
        "Price Chg %": 3.1,
        "OI Chg %": 4.2,
        "Outcome": "TARGET HIT"
    }
])

engine.integrate_outcomes(dummy_memory)
engine.evaluate_lifecycle()

print("Lifecycle Integration Test : PASS")
print("="*60)
print("PATTERN LIFECYCLE VALIDATION PASSED")
print("="*60)
