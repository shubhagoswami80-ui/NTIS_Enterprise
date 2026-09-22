from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "00_BASELINE" / "strategy_baseline_v1.json"

def test_w73_baseline_exists_and_is_frozen():
    assert BASE.exists(), "Run reproduce_w73_baseline.py first."
    d = json.loads(BASE.read_text(encoding="utf-8"))
    assert d["schema_version"] == "W73_STRATEGY_BASELINE_V1"
    assert d["max_holdout_rate"] >= 0
    assert d["holdout_n"] >= 30
    assert d["holdout_dates"] >= 3
    assert d["holdout_symbols"] >= 10
    assert d["source_sha256"]
    assert d["status"] == "FROZEN_CANDIDATE_EXTRACTION_ONLY"

def test_expected_historical_ceiling():
    d = json.loads(BASE.read_text(encoding="utf-8"))
    # The established research ceiling is 72.093%. This test is deliberately
    # exact to prevent the source data from silently changing underneath W73.
    assert round(float(d["max_holdout_rate_pct"]), 3) == 72.093
    assert int(d["holdout_n"]) == 129
    assert int(d["holdout_dates"]) == 5
    assert int(d["holdout_symbols"]) == 45
