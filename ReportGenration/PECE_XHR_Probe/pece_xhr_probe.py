"""Isolated iCharts PE/CE XHR discovery probe.

Diagnostic-only phase. This module does not modify app.py or reports.json.
It reuses ReportGenration/browser_profile so an existing authenticated
session can be used. It records matching XHR/fetch metadata and response
bodies for endpoint/schema discovery.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Response, sync_playwright

ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "browser_profile"
OUTPUT_ROOT = ROOT / "pece_xhr_probe"

DEFAULT_KEYWORDS = (
    "pece", "totalpe", "total-ce", "total_pe",
    "totalce", "total_ce", "option", "oi", "volume",
    "chart", "getdata",
)

SENSITIVE_KEYS = {
    "cookie", "authorization", "proxy-authorization",
    "x-api-key", "api-key", "token", "access_token",
    "refresh_token", "password",
}


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        str(k): "<redacted>" if str(k).casefold() in SENSITIVE_KEYS else str(v)
        for k, v in headers.items()
    }


def matches(url: str, keywords: tuple[str, ...]) -> bool:
    lowered = url.casefold()
    return any(k.casefold() in lowered for k in keywords)


def is_json_response(response: Response) -> bool:
    try:
        return "json" in response.headers.get("content-type", "").casefold()
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--wait-seconds", type=float, default=15)
    parser.add_argument("--all-xhr", action="store_true")
    parser.add_argument("--keyword", action="append", dest="keywords")
    args = parser.parse_args()

    keywords = tuple(args.keywords or DEFAULT_KEYWORDS)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUTPUT_ROOT / stamp
    out.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def on_response(response: Response) -> None:
        request = response.request
        if request.resource_type not in {"xhr", "fetch"}:
            return
        if not args.all_xhr and not matches(response.url, keywords):
            return

        key = f"{request.method} {response.url}"
        if key in seen:
            return
        seen.add(key)

        record: dict[str, Any] = {
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "resource_type": request.resource_type,
            "method": request.method,
            "url": response.url,
            "status": response.status,
            "request_headers": sanitize_headers(dict(request.headers)),
            "response_headers": sanitize_headers(dict(response.headers)),
        }

        post_data = request.post_data
        if post_data:
            # Redact obvious credential/token fields in captured payloads.
            safe = str(post_data)
            for key_name in SENSITIVE_KEYS:
                safe = re.sub(
                    rf"({re.escape(key_name)}\s*[=:]\s*)[^&\s,}}]+",
                    r"\1<redacted>",
                    safe,
                    flags=re.IGNORECASE,
                )
            record["post_data"] = safe

        try:
            body = response.text()
            body_file = out / f"response_{len(records):04d}.txt"
            body_file.write_text(body, encoding="utf-8", errors="replace")
            record["body_file"] = body_file.name
            record["body_length"] = len(body)
            if is_json_response(response):
                try:
                    record["body_json"] = json.loads(body)
                except Exception:
                    record["body_json"] = None
        except Exception as exc:
            record["body_error"] = str(exc)

        records.append(record)
        write_manifest()

        print(f"Captured: {request.method} {response.status} {response.url}")

    def write_manifest() -> None:
        (out / "manifest.json").write_text(
            json.dumps(
                {
                    "tool": "pece_xhr_probe",
                    "target_url": args.url,
                    "captured_at": datetime.now().isoformat(timespec="seconds"),
                    "keywords": list(keywords),
                    "records": records,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(PROFILE),
            headless=False,
            accept_downloads=True,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.on("response", on_response)
            page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            print("Page loaded. Waiting for XHR/fetch traffic...")
            print("Perform the PE/CE page action manually if it requires a selection/submit.")
            time.sleep(max(0, args.wait_seconds))
        finally:
            context.close()

    write_manifest()
    print(f"Captured {len(records)} matching request(s).")
    print(f"Output: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
