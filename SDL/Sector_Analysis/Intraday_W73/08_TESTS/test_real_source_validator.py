from pathlib import Path

def test_real_source_validator_is_present():
    p = Path(__file__).resolve().parents[1] / "10_DOCS" / "validate_real_source_v1.py"
    assert p.exists()
