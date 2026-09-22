from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

def test_two_v1_variants_are_preserved():
    p = ROOT / "00_BASELINE" / "strategy_baseline_v1_tied_max.json"
    assert p.exists()
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["tied_max_count"] == 2
    assert round(float(d["max_holdout_rate_pct"]), 3) == 72.093
    assert len(d["candidates"]) == 2

def test_candidate_ids_are_preserved():
    p = ROOT / "00_BASELINE" / "strategy_baseline_v1_tied_max.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    ids = [x["candidate_id"] for x in d["candidates"]]
    assert any("orb_agree=NO" in x for x in ids)
    assert any("orb_price_agree=NO" in x for x in ids)

def test_missing_never_matches():
    import sys
    sys.path.insert(0, str(ROOT))
    from strategy_v1 import W73StrategyV1
    s = W73StrategyV1(ROOT)
    row = pd.Series(dict(s.variants[0].conditions))
    # Force one required field missing.
    first_feature = next(iter(s.variants[0].conditions))
    row[first_feature] = None
    assert s.classify(row) is None
