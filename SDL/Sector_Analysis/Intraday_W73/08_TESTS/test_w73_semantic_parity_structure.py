from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "02_FEATURE_ENGINE"))

from w73_v8_semantic_parity import V8_COLUMNS, inspect

def test_frozen_v8_shape():
    assert len(V8_COLUMNS) == 25

def test_local_authoritative_inputs_exist():
    assert (ROOT / "00_BASELINE" / "maturity_feature_matrix.csv").exists()
    assert (ROOT / "01_RESEARCH_SOURCE" / "maturity_conditional_pattern_discovery_v8.py").exists()

def test_structural_inspection_is_not_false_promotion():
    # The function's report must explicitly remain structural-only.
    report = inspect(
        ROOT / "00_BASELINE" / "maturity_feature_matrix.csv",
        ROOT / "01_RESEARCH_SOURCE" / "maturity_conditional_pattern_discovery_v8.py",
    )
    assert "COLUMN_PRESENCE_DOES_NOT_PROVE_EXACT_V8_SEMANTICS" in report.warnings
