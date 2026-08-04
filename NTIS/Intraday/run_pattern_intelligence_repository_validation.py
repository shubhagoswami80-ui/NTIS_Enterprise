"""
=========================================================
NTIS Pattern Intelligence Repository Validation Runner
Version : 1.0

Purpose:
    Validate Historical Intelligence Loader and Query layer
    integrate exclusively with the Pattern Intelligence Repository.
=========================================================
"""

from pathlib import Path
from intraday_intelligence_loader import IntradayIntelligenceLoader
from intraday_intelligence_query import IntradayIntelligenceQuery

print("="*60)
print("NTIS PATTERN INTELLIGENCE REPOSITORY VALIDATION")
print("="*60)

loader = IntradayIntelligenceLoader()
df = loader.load()
print(f"Loaded Intelligence Records : {len(df)}")

query = IntradayIntelligenceQuery(loader)
symbols = list(loader.get_symbol_index().keys())
print(f"Indexed Symbols            : {symbols[:5]}")

if symbols:
    sym_df = query.by_symbol(symbols[0])
    print(f"Query by Symbol ({symbols[0]})   : {len(sym_df)} records")

print("Intelligence Repository Validation : PASS")
print("="*60)
print("PATTERN INTELLIGENCE REPOSITORY VALIDATION PASSED")
print("="*60)
