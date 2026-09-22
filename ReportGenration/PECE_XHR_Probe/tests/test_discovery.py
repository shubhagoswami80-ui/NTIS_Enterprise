from pathlib import Path
import ast
import json

ROOT = Path(__file__).resolve().parents[1]


def test_discovery_compiles():
    ast.parse((ROOT / "pece_control_discovery.py").read_text(encoding="utf-8"))


def test_discovery_does_not_implement_session_storage():
    text = (ROOT / "pece_control_discovery.py").read_text(encoding="utf-8").lower()
    forbidden_code_patterns = [
        "context.cookies(", "storage_state(", "page.context.cookies(",
        "set_cookie(", "add_cookies(", "password =",
        "phpsessid =", "sessionid =",
    ]
    assert not any(x in text for x in forbidden_code_patterns)


def test_discovery_is_read_only_by_contract():
    text = (ROOT / "pece_control_discovery.py").read_text(encoding="utf-8")
    assert "context.new_page()" in text
    assert "page.close()" in text
    assert "page.goto(" in text
    assert "page.evaluate(" in text


def test_historical_mode_remains_reserved():
    schema = json.loads((ROOT / "xhr_report_schema.json").read_text(encoding="utf-8"))
    assert schema["report_types"]["historical_xhr_batch"]["status"] == "reserved_not_implemented"


if __name__ == "__main__":
    for f in (
        test_discovery_compiles,
        test_discovery_does_not_implement_session_storage,
        test_discovery_is_read_only_by_contract,
        test_historical_mode_remains_reserved,
    ):
        f()
    print("PASS: PE/CE v1.2.1 discovery safety tests")
