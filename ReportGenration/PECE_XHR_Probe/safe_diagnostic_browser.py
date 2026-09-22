"""Safe diagnostic Chromium launcher for PE/CE XHR capture.

This launcher NEVER opens the production browser_profile.
It creates a disposable Chromium profile under the Phase-3 workspace and
starts Chromium with CDP enabled. It is intentionally separate from the
live ReportGenration application.

Use this only for endpoint discovery. It is not production code.
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMP_PROFILE = ROOT / "temporary_chromium_profile"
CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Chromium\Application\chrome.exe"),
]

def free_port(start: int = 9222, end: int = 9322) -> int:
    for port in range(start, end + 1):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free localhost CDP port found.")

def find_browser(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            raise FileNotFoundError(f"Browser executable not found: {p}")
        return p
    for p in CHROME_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Chrome/Chromium executable not found. "
        "Use --browser with the full executable path."
    )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", help="Full path to Chrome/Chromium executable.")
    ap.add_argument("--url", default="https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument(
        "--keep-profile",
        action="store_true",
        help="Keep the disposable profile after exit for repeated diagnostics.",
    )
    args = ap.parse_args()

    # Strong safety check: this tool must never point at the production profile.
    if "browser_profile" in str(TEMP_PROFILE).casefold():
        raise RuntimeError("Safety check failed: temporary profile path is unsafe.")

    if TEMP_PROFILE.exists() and not args.keep_profile:
        shutil.rmtree(TEMP_PROFILE)

    TEMP_PROFILE.mkdir(parents=True, exist_ok=True)
    browser = find_browser(args.browser)
    port = args.port or free_port()

    cmd = [
        str(browser),
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={TEMP_PROFILE}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        args.url,
    ]

    print("SAFE DIAGNOSTIC BROWSER")
    print(f"Executable : {browser}")
    print(f"Temporary profile : {TEMP_PROFILE}")
    print(f"CDP endpoint : http://127.0.0.1:{port}")
    print()
    print("This browser is NOT the production browser.")
    print("Login here, if iCharts requires it. Your production profile is not used.")
    print()
    print("After the page is logged in and ready, run in another PowerShell window:")
    print()
    print(
        f'python pece_xhr_probe.py --url "{args.url}" '
        f'--cdp-url "http://127.0.0.1:{port}"'
    )
    print()
    print("Keep this browser open while capturing.")
    print("Close this diagnostic browser after the capture is complete.")

    proc = subprocess.Popen(cmd)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
