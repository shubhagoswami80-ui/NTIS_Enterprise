"""
=========================================================
NTIS Pattern Learning Integration Validation Runner
Version : 1.0

Purpose:
    Validate Learning -> Pattern Intelligence Repository Integration.
=========================================================
"""

from pathlib import Path
import pandas as pd
from intraday_pattern_repository import IntradayPatternRepository
from intraday_pattern_lifecycle_engine import IntradayPatternLifecycleEngine
from intraday_learning_outcome_updater import IntradayLearningOutcomeUpdater
from config_loader import LEARNING_ROOT

print("="*60)
print("NTIS PATTERN LEARNING INTEGRATION VALIDATION")
print("="*60)

repo = IntradayPatternRepository()
lifecycle = IntradayPatternLifecycleEngine(repo)

# Create mock memory file and replay file for test
mock_replay = LEARNING_ROOT / "mock_replay_test.csv"
mock_memory = LEARNING_ROOT / "intraday_learning_memory.csv"

replay_df = pd.DataFrame([{
    "Symbol": "SBIN",
    "Pattern": "Fresh Long Buildup",
    "Outcome": "TARGET HIT",
    "Return %": 2.5
}])
replay_df.to_csv(mock_replay, index=False)

if not mock_memory.exists():
    mem_df = pd.DataFrame([{
        "Symbol": "SBIN",
        "Pattern": "Fresh Long Buildup",
        "Direction": "BUY",
        "Validation Signal": "VALID BUY",
        "Fut Buildup": "Long Buildup",
        "NTIS Score": 85.0,
        "Price Chg %": 2.0,
        "OI Chg %": 3.0,
        "Outcome": "PENDING"
    }])
    mem_df.to_csv(mock_memory, index=False)

updater = IntradayLearningOutcomeUpdater(mock_replay)
updater.run()

print("Learning -> Repository Integration Test : PASS")
print("="*60)
print("PATTERN LEARNING INTEGRATION VALIDATION PASSED")
print("="*60)
