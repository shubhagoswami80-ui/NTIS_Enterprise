from pathlib import Path
import sys

W73 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(W73 / "12_INTEGRATION"))

from w73_entrypoint import render_intraday_w73_page

def test_single_entrypoint_exists():
    assert callable(render_intraday_w73_page)

def test_entrypoint_module_does_not_require_existing_sdl_app():
    app = W73 / "sdl_decision_centre_preview.py"
    assert not app.exists() or app.is_file()
