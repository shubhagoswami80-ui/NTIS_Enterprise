
from __future__ import annotations

from pathlib import Path
import re
import py_compile
import tempfile

ROOT = Path(__file__).resolve().parent
PREVIEW = ROOT / "sdl_decision_centre_preview.py"
START = ROOT / "start_sdl_dashboard.ps1"


def replace_top_nav(text: str) -> str:
    pattern = re.compile(
        r"def top_nav\(page, live_ts\):.*?(?=\ntoday = pd\.Timestamp\.now\(\)\.date\(\)\.isoformat\(\))",
        re.S,
    )
    replacement = '''def top_nav(page, live_ts):
    # Approved visual header. Replay remains in the compact bottom
    # Navigation expander so the top header stays visually clean.
    live_text = time_text(live_ts)
    date_text = (
        time_text(live_ts, True).split(", ", 1)[0]
        if pd.notna(pd.to_datetime(live_ts, errors="coerce"))
        else "—"
    )
    st.markdown(
        f'<div class="appnav"><div class="brand"><div class="brandmark">◈</div>'
        f'<div class="brandname">NTIS SDL</div><div class="brandsep"></div>'
        f'<div class="brandsub">INTRADAY DECISION CENTRE</div></div>'
        f'<div class="navlinks"><div class="navitem {"active" if page == "Decision Board" else ""}">▣　DECISION BOARD</div>'
        f'<div class="navitem {"active" if page == "Historical Evidence" else ""}">▤　HISTORICAL EVIDENCE</div>'
        f'<div class="navitem {"active" if page == "Settings" else ""}">⚙　SETTINGS</div></div>'
        f'<div class="navright"><span class="livepill">LIVE ●</span>'
        f'<div class="clockbox"><b>{live_text}</b><br>{date_text}</div>'
        f'<span class="refreshbtn">⟳ Refresh</span><span class="autopill">● Auto Refresh　10s⌄</span></div></div>',
        unsafe_allow_html=True,
    )
'''
    new_text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("Could not locate top_nav() block.")
    return new_text


def patch_preview(text: str) -> str:
    text = replace_top_nav(text)

    # Keep Replay out of the top header; it remains in the bottom Navigation expander.
    text = text.replace(
        '["Decision Board","Replay","Historical Evidence","Settings"]',
        '["Decision Board","Historical Evidence","Settings"]',
    )

    # Ensure timestamp display has a reliable source-file fallback.
    old = '''def ts(path):
    try:
        return parse_observation_timestamp(path)
    except Exception:
        try:
            return pd.Timestamp.fromtimestamp(Path(path).stat().st_mtime)
        except Exception:
            return pd.NaT
'''
    new = '''def ts(path):
    try:
        parsed = parse_observation_timestamp(path)
        if pd.notna(pd.to_datetime(parsed, errors="coerce")):
            return parsed
    except Exception:
        pass
    try:
        return pd.Timestamp.fromtimestamp(Path(path).stat().st_mtime)
    except Exception:
        return pd.NaT
'''
    if old not in text:
        raise RuntimeError("Could not locate ts() block.")
    text = text.replace(old, new, 1)
    return text


def patch_start(text: str) -> str:
    # Production dashboard runs the approved presentation layer.
    old = '& $PythonPath -m streamlit run app.py --server.port $Port'
    new = '& $PythonPath -m streamlit run sdl_decision_centre_preview.py --server.port $Port'
    if old not in text:
        raise RuntimeError("Could not locate production Streamlit entry command.")
    return text.replace(old, new, 1)


def main() -> None:
    if not PREVIEW.exists():
        raise FileNotFoundError(PREVIEW)
    if not START.exists():
        raise FileNotFoundError(START)

    preview_text = PREVIEW.read_text(encoding="utf-8")
    start_text = START.read_text(encoding="utf-8")

    patched_preview = patch_preview(preview_text)
    patched_start = patch_start(start_text)

    # Compile before touching the working files.
    with tempfile.TemporaryDirectory() as td:
        candidate = Path(td) / "sdl_decision_centre_preview.py"
        candidate.write_text(patched_preview, encoding="utf-8")
        py_compile.compile(str(candidate), doraise=True)

    PREVIEW.write_text(patched_preview, encoding="utf-8")
    START.write_text(patched_start, encoding="utf-8")

    print("SDL approved dashboard deployment applied.")
    print(f"Changed: {PREVIEW}")
    print(f"Changed: {START}")
    print("Decision/prediction/replay engine modules were not modified.")


if __name__ == "__main__":
    main()
