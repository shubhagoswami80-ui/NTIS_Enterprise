"""
PE/CE same-context diagnostic helper.

This module is intentionally standalone and contains NO Streamlit wiring.
It is designed to be copied temporarily into a diagnostic copy of
ReportGenration/app.py and invoked from that copy's existing Manager.

Contract:
    run_pece_xhr_diagnostic(context, production_page, target_url, output_root)

It creates one NEW page in the EXISTING Playwright BrowserContext.
It never creates a browser/context and never performs login.
The caller retains ownership of the production context and page.

Do not import this module from production app.py until the diagnostic has
been accepted.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def run_pece_xhr_diagnostic(
    context,
    production_page,
    target_url: str,
    output_root: Path,
    wait_seconds: float = 30.0,
) -> dict[str, Any]:
    if context is None:
        raise RuntimeError("Diagnostic safety stop: Playwright context is None.")
    if production_page is None or production_page.is_closed():
        raise RuntimeError("Diagnostic safety stop: production page is not alive.")
    if not target_url.startswith("https://www.icharts.in/"):
        raise ValueError("Diagnostic safety stop: target must be an iCharts HTTPS URL.")

    before_pages = list(context.pages)
    if production_page not in before_pages:
        raise RuntimeError(
            "Diagnostic safety stop: production page is not in the supplied context."
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(output_root) / f"same_context_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    page_errors: list[str] = []
    request_failures: list[str] = []

    def on_response(response):
        request = response.request
        if request.resource_type not in {"xhr", "fetch"}:
            return

        record: dict[str, Any] = {
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "method": request.method,
            "url": response.url,
            "status": response.status,
            "resource_type": request.resource_type,
            "content_type": response.headers.get("content-type", ""),
            "post_data_present": bool(request.post_data),
        }

        try:
            body = response.text()
            index = len(records)
            filename = f"response_{index:04d}.txt"
            (out / filename).write_text(
                body,
                encoding="utf-8",
                errors="replace",
            )
            record["body_file"] = filename
            record["body_length"] = len(body)

            if "json" in record["content_type"].casefold():
                try:
                    record["json"] = json.loads(body)
                except Exception:
                    record["json_parse_error"] = True
        except Exception as exc:
            record["body_error"] = str(exc)

        records.append(record)

    def on_request_failed(request):
        request_failures.append(
            f"{request.method} {request.url}: {request.failure or 'unknown'}"
        )

    pece_page = None
    result: dict[str, Any] = {}

    try:
        # The ONLY new browser object allowed is a Page in the existing context.
        pece_page = context.new_page()
        pece_page.on("response", on_response)
        pece_page.on("requestfailed", on_request_failed)
        pece_page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        production_url_before = production_page.url

        pece_page.goto(
            target_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )
        pece_page.wait_for_timeout(2000)

        if pece_page.url.lower().startswith("https://www.icharts.in/"):
            pass
        else:
            raise RuntimeError(
                f"Diagnostic safety stop: unexpected PE/CE navigation URL: {pece_page.url}"
            )

        # Authentication check is observational only. Never submit/login.
        login_required = any(
            token in pece_page.url.casefold()
            for token in ("login", "signin", "auth")
        )

        if login_required:
            result["login_required"] = True
            raise RuntimeError(
                "Diagnostic stopped: PE/CE tab requires login. "
                "No login was attempted."
            )

        # The operator performs the PE/CE action manually while this function
        # remains alive. This is intentionally not automated.
        time.sleep(max(0.0, wait_seconds))

        production_url_after = production_page.url

        if production_url_after != production_url_before:
            raise RuntimeError(
                "Diagnostic safety stop: production Tab 1 URL changed."
            )

        if pece_page.is_closed():
            raise RuntimeError("Diagnostic safety stop: PE/CE Tab 2 closed unexpectedly.")

        result.update(
            {
                "login_required": False,
                "production_page_url_before": production_url_before,
                "production_page_url_after": production_url_after,
                "pece_page_url": pece_page.url,
                "tab_count_after_open": len(context.pages),
                "xhr_count": len(records),
                "request_failures": request_failures,
                "page_errors": page_errors,
                "records": records,
            }
        )

    finally:
        # Close ONLY the diagnostic page. Never close the context.
        if pece_page is not None:
            try:
                pece_page.close()
            except Exception:
                pass

    result["tab_count_after_close"] = len(context.pages)
    result["production_page_still_alive"] = not production_page.is_closed()

    (out / "manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "output_folder": str(out),
        "result": result,
    }
