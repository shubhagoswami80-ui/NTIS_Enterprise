from pathlib import Path
import ast

ROOT = Path(__file__).parents[1]
SRC = ROOT / "safe_diagnostic_browser.py"

def test_source_parses():
    ast.parse(SRC.read_text(encoding="utf-8"))

def test_never_references_production_browser_profile():
    text = SRC.read_text(encoding="utf-8").casefold()
    assert "reportgenration\\browser_profile" not in text
    assert "reportgenration/browser_profile" not in text

def test_uses_localhost_cdp_only():
    text = SRC.read_text(encoding="utf-8")
    assert "--remote-debugging-address=127.0.0.1" in text
    assert "http://127.0.0.1:" in text
