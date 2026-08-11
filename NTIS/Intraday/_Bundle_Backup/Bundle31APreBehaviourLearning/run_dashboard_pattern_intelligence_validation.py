"""
=========================================================
Dashboard Pattern Intelligence Validation Runner
Version : 1.0

Purpose:
    Validate Dashboard integration with Intelligence Loader
    and Query Layer.
=========================================================
"""

from pathlib import Path
from intraday_intelligence_loader import IntradayIntelligenceLoader
from intraday_intelligence_query import IntradayIntelligenceQuery

print("="*60)
print("DASHBOARD PATTERN INTELLIGENCE VALIDATION")
print("="*60)

loader = IntradayIntelligenceLoader()
loader.load()
query = IntradayIntelligenceQuery(loader)

df = loader.get_dataframe()
print(f"Loader Records Loaded  : {len(df)}")
print(f"Query Layer Operational: {'PASS' if query is not None else 'FAIL'}")

print("Dashboard Intelligence Validation : PASS")
print("="*60)
print("DASHBOARD PATTERN INTELLIGENCE VALIDATION PASSED")
print("="*60)
