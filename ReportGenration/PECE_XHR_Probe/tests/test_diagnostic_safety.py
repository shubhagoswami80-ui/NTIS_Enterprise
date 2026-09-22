from pathlib import Path
import ast

ROOT = Path(__file__).parents[1]
SRC = ROOT / "pece_same_context_diagnostic.py"

def test_syntax():
    ast.parse(SRC.read_text(encoding="utf-8"))

def test_no_browser_launch():
    s = SRC.read_text(encoding="utf-8")
    assert "launch_persistent_context" not in s
    assert ".launch(" not in s

def test_only_new_page_and_never_context_close():
    s = SRC.read_text(encoding="utf-8")
    assert "context.new_page()" in s
    assert "context.close()" not in s

def test_login_is_never_attempted():
    s = SRC.read_text(encoding="utf-8")
    assert "No login was attempted." in s

def test_production_page_guard():
    s = SRC.read_text(encoding="utf-8")
    assert "production_page_url_before" in s
    assert "production_page_url_after" in s
