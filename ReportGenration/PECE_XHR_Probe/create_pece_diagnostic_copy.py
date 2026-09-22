from __future__ import annotations

import subprocess
from pathlib import Path

EXPECTED_APP_SHA = "62c17d570bb019f5d24147ef10de20ba69090ae7"
TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"

ROOT = Path(__file__).resolve().parent
LIVE_APP = ROOT.parent / "app.py"
HELPER = ROOT / "pece_same_context_diagnostic.py"
DIAGNOSTIC_APP = ROOT / "app_pece_diagnostic.py"


def git_blob_sha(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)],
        cwd=str(ROOT.parent),
        text=True,
    ).strip()


def main() -> None:
    if not LIVE_APP.exists():
        raise SystemExit("SAFETY STOP: app.py not found.")
    if not HELPER.exists():
        raise SystemExit("SAFETY STOP: helper not found.")

    try:
        actual = git_blob_sha(LIVE_APP)
    except Exception as exc:
        raise SystemExit(
            "SAFETY STOP: could not verify app.py with Git. "
            "No diagnostic copy created."
        ) from exc

    if actual != EXPECTED_APP_SHA:
        raise SystemExit(
            "SAFETY STOP: local app.py does not match verified master.\n"
            f"Expected: {EXPECTED_APP_SHA}\n"
            f"Actual:   {actual}\n"
            "No production file was modified."
        )

    source = LIVE_APP.read_text(encoding="utf-8")

    import_marker = 'from playwright.sync_api import sync_playwright\n'
    if import_marker not in source:
        raise SystemExit("SAFETY STOP: Playwright import marker not found.")
    if 'from pece_same_context_diagnostic import' in source:
        raise SystemExit("SAFETY STOP: diagnostic import already exists.")

    source = source.replace(
        import_marker,
        import_marker + 'from pece_same_context_diagnostic import run_pece_xhr_diagnostic\n',
        1,
    )

    worker_marker = '                        if command == "open":\n'
    worker_block = (
        '                        if command == "pece_diagnostic":\n'
        '                            if running:\n'
        '                                self.log("PE/CE diagnostic refused: daily run is active.")\n'
        '                                continue\n'
        '\n'
        '                            if context is None or page is None or page.is_closed():\n'
        '                                self.log("PE/CE diagnostic refused: production browser/page is not alive.")\n'
        '                                continue\n'
        '\n'
        '                            try:\n'
        '                                probe_root = ROOT / "PECE_XHR_Probe"\n'
        '                                diagnostic = run_pece_xhr_diagnostic(\n'
        '                                    context, page, TARGET_URL, probe_root,\n'
        '                                    wait_seconds=45.0,\n'
        '                                )\n'
        '                                result = diagnostic["result"]\n'
        '                                self.log(\n'
        '                                    "PE/CE diagnostic completed: "\n'
        '                                    f"{result.get(\'xhr_count\', 0)} XHR/fetch responses; "\n'
        '                                    f"production tab alive={result.get(\'production_page_still_alive\')}; "\n'
        '                                    f"output={diagnostic[\'output_folder\']}"\n'
        '                                )\n'
        '                            except Exception as error:\n'
        '                                self.log(f"PE/CE diagnostic stopped: {error}")\n'
        '\n'
        '                        elif command == "open":\n'
    )
    if worker_marker not in source:
        raise SystemExit("SAFETY STOP: worker marker not found.")
    source = source.replace(worker_marker, worker_block, 1)

    ui_marker = 'st.divider()\n\ncol1, col2, col3, col4 = st.columns(4)\n'
    ui_block = (
        'st.divider()\n\n'
        'st.subheader("PE/CE XHR Diagnostic")\n'
        'st.caption(\n'
        '    "Temporary same-context test. Daily run must be stopped. "\n'
        '    "Opens one second tab in the existing authenticated Chromium context."\n'
        ')\n\n'
        'if st.button(\n'
        '    "OPEN PE/CE XHR TEST TAB",\n'
        '    use_container_width=True,\n'
        '    disabled=status["running"],\n'
        '):\n'
        '    manager.cmd("pece_diagnostic")\n'
        '    time.sleep(0.4)\n'
        '    st.rerun()\n\n'
        'col1, col2, col3, col4 = st.columns(4)\n'
    )
    if ui_marker not in source:
        raise SystemExit("SAFETY STOP: UI marker not found.")
    source = source.replace(ui_marker, ui_block, 1)

    if DIAGNOSTIC_APP.exists():
        raise SystemExit("SAFETY STOP: diagnostic copy already exists. Refusing overwrite.")

    DIAGNOSTIC_APP.write_text(source, encoding="utf-8")
    print(f"CREATED: {DIAGNOSTIC_APP}")
    print(f"VERIFIED SOURCE BLOB SHA: {actual}")
    print("LIVE app.py was NOT modified.")


if __name__ == "__main__":
    main()
