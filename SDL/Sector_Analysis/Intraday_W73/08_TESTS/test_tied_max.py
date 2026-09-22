from pathlib import Path
import json
P=Path(__file__).resolve().parents[1]/"00_BASELINE"/"strategy_baseline_v1_tied_max.json"
def test_tied_max():
    assert P.exists()
    d=json.loads(P.read_text(encoding="utf-8"))
    assert round(float(d["max_holdout_rate_pct"]),3)==72.093
    assert int(d["tied_max_count"])==2
    assert len(d["candidates"])==2
