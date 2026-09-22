from __future__ import annotations
import subprocess
from pathlib import Path

EXPECTED_APP_SHA = "62c17d570bb019f5d24147ef10de20ba69090ae7"
ROOT = Path(__file__).resolve().parent
LIVE_APP = ROOT.parent / "app.py"
HELPER = ROOT / "pece_manager_diagnostic.py"
OUT = ROOT / "app_pece_manager_diagnostic.py"

def blob_sha(path):
    return subprocess.check_output(["git","hash-object",str(path)], cwd=str(LIVE_APP.parent), text=True).strip()

def main():
    if not LIVE_APP.exists(): raise SystemExit("SAFETY STOP: app.py not found.")
    if not HELPER.exists(): raise SystemExit("SAFETY STOP: helper not found.")
    actual = blob_sha(LIVE_APP)
    if actual != EXPECTED_APP_SHA:
        raise SystemExit(f"SAFETY STOP: app.py SHA mismatch. Expected {EXPECTED_APP_SHA}; actual {actual}.")
    if OUT.exists(): raise SystemExit("SAFETY STOP: diagnostic copy already exists.")
    source = LIVE_APP.read_text(encoding="utf-8")
    marker = "from playwright.sync_api import sync_playwright\n"
    if marker not in source: raise SystemExit("SAFETY STOP: Playwright import marker not found.")
    source = source.replace(marker, marker + "from pece_manager_diagnostic import run_pece_manager_diagnostic\n", 1)

    worker_marker = '                        if command == "open":\n'
    block = (
        '                        if command == "pece_manager_diagnostic":\n'
        '                            if running:\n'
        '                                self.log("PE/CE diagnostic refused: daily run is active.")\n'
        '                                continue\n'
        '                            if context is None or page is None or page.is_closed():\n'
        '                                self.log("PE/CE diagnostic refused: production browser/page is not alive.")\n'
        '                                continue\n'
        '                            try:\n'
        '                                diagnostic = run_pece_manager_diagnostic(context, page, ROOT / "PECE_XHR_Probe", wait_seconds=20.0)\n'
        '                                result = diagnostic["manifest"]\n'
        '                                self.log("PE/CE manager diagnostic completed: " + str(result.get("xhr_fetch_count", 0)) + " XHR/fetch responses; output=" + diagnostic["output_folder"])\n'
        '                            except Exception as error:\n'
        '                                self.log("PE/CE manager diagnostic stopped: " + str(error))\n'
        '\n'
        '                        elif command == "open":\n'
    )
    if worker_marker not in source: raise SystemExit("SAFETY STOP: worker marker not found.")
    source = source.replace(worker_marker, block, 1)

    ui_marker = "st.divider()\n\ncol1, col2, col3, col4 = st.columns(4)\n"
    ui = (
        "st.divider()\n\n"
        'st.subheader("PE/CE XHR Discovery — Temporary")\n'
        'st.caption("Uses the existing authenticated Playwright context. Opens one PE/CE tab, observes XHR/fetch only, and never clicks Download.")\n\n'
        'if st.button("OPEN PE/CE XHR DISCOVERY TAB", use_container_width=True, disabled=status["running"]):\n'
        '    manager.cmd("pece_manager_diagnostic")\n'
        '    time.sleep(0.4)\n'
        '    st.rerun()\n\n'
        "col1, col2, col3, col4 = st.columns(4)\n"
    )
    if ui_marker not in source: raise SystemExit("SAFETY STOP: UI marker not found.")
    source = source.replace(ui_marker, ui, 1)
    OUT.write_text(source, encoding="utf-8")
    print("CREATED:", OUT)
    print("VERIFIED SOURCE BLOB SHA:", actual)
    print("LIVE app.py was NOT modified.")

if __name__ == "__main__":
    main()
