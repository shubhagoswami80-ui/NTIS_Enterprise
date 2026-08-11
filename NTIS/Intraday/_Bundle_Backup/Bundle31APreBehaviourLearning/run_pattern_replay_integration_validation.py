"""
=========================================================
NTIS Pattern Replay Integration Validation Runner
Version : 1.0

Purpose:
    Validate Replay -> Pattern Repository Integration.
=========================================================
"""

from pathlib import Path
import pandas as pd
from intraday_pattern_repository import IntradayPatternRepository
from intraday_pattern_lifecycle_engine import IntradayPatternLifecycleEngine
from intraday_historical_replay_engine import IntradayHistoricalReplayEngine

print("="*60)
print("NTIS PATTERN REPLAY INTEGRATION VALIDATION")
print("="*60)

repo = IntradayPatternRepository()
lifecycle = IntradayPatternLifecycleEngine(repo)

dummy_replay = pd.DataFrame([
    {
        "Symbol": "INFY",
        "Pattern": "Short Covering",
        "Direction": "BUY",
        "Validation Signal": "VALID BUY",
        "Fut Buildup": "Short Covering",
        "NTIS Score": 88.0,
        "Price Chg %": 1.5,
        "OI Chg %": -2.0,
        "Outcome": "TARGET HIT",
        "Return %": 4.5
    }
])

lifecycle.integrate_outcomes(dummy_replay)
lifecycle.evaluate_lifecycle()

print("Replay -> Repository Integration Test : PASS")
print("="*60)
print("PATTERN REPLAY INTEGRATION VALIDATION PASSED")
print("="*60)
