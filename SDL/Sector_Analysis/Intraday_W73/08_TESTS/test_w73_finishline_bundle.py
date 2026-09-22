from pathlib import Path
import sys

W73 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(W73 / "02_FEATURE_ENGINE"))
sys.path.insert(0, str(W73 / "03_LIVE_ADAPTER"))

from w73_raw_v8_bridge import derive_raw_features, V8_COLUMNS, V8Context, validate_vector
from w73_canonical_observation import canonicalize

def test_bridge_preserves_missing():
    r = derive_raw_features(
        {"Symbol": "TEST", "Price Chg %": None, "OI Chg %": None},
        V8Context("2026-09-18", __import__("datetime").datetime(2026,9,18,9,18,9), 15, "09:30"),
    )
    assert r.values["price_dir"] is None
    assert "INCOMPLETE_V8_VECTOR" in r.warnings

def test_vector_has_frozen_vocabulary_shape():
    assert len(V8_COLUMNS) == 25

def test_canonical_and_bridge_are_separate():
    raw = canonicalize({"Symbol":"TEST","Price Chg %":1.2,"OI Chg %":2.0})
    r = derive_raw_features(
        raw, V8Context("2026-09-18", __import__("datetime").datetime(2026,9,18,9,18,9), 15, "09:30")
    )
    assert r.status == "DERIVED_PROVISIONAL"
    assert r.values["price_state"] == "POSITIVE"

def test_missing_never_becomes_zero():
    r = derive_raw_features({}, V8Context("2026-09-18", __import__("datetime").datetime(2026,9,18,9,18,9), 15, "09:30"))
    assert all(v is None or v == 15 or v == "09:30" for v in r.values.values())

def test_vector_validation_is_fail_closed():
    assert len(validate_vector({"price_state":"POSITIVE"})) > 0
