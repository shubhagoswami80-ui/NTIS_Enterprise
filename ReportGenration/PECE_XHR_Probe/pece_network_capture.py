from __future__ import annotations
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from playwright.sync_api import BrowserContext, Page

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"

def capture_pece_network(context: BrowserContext, production_page: Page,
                         output_root: Path, target_url: str = TARGET_URL,
                         wait_seconds: float = 20.0) -> dict[str, Any]:
    """Capture PE/CE XHR/fetch in a second tab of an already-owned context."""
    if context is None:
        raise RuntimeError("SAFETY STOP: context is None.")
    if production_page is None or production_page.is_closed():
        raise RuntimeError("SAFETY STOP: production page is not alive.")
    if not target_url.startswith("https://www.icharts.in/"):
        raise ValueError("SAFETY STOP: target URL is not an iCharts HTTPS URL.")
    if production_page not in context.pages:
        raise RuntimeError("SAFETY STOP: production page is not in supplied context.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(output_root) / f"network_capture_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    records, failures, errors = [], [], []

    def on_response(response):
        request = response.request
        if request.resource_type not in {"xhr", "fetch"}:
            return
        rec = {
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "method": request.method, "url": response.url,
            "status": response.status, "resource_type": request.resource_type,
            "content_type": response.headers.get("content-type", ""),
            "post_data": request.post_data,
        }
        try:
            body = response.text()
            fn = f"response_{len(records):04d}.txt"
            (out / fn).write_text(body, encoding="utf-8", errors="replace")
            rec["body_file"], rec["body_length"] = fn, len(body)
        except Exception as exc:
            rec["body_error"] = str(exc)
        records.append(rec)

    def on_failed(request):
        failures.append(f"{request.method} {request.url}: {request.failure or 'unknown'}")

    pece_page = context.new_page()
    pece_page.on("response", on_response)
    pece_page.on("requestfailed", on_failed)
    pece_page.on("pageerror", lambda exc: errors.append(str(exc)))
    before_url = production_page.url
    try:
        pece_page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        pece_page.wait_for_timeout(3000)
        if not pece_page.url.lower().startswith("https://www.icharts.in/"):
            raise RuntimeError(f"SAFETY STOP: unexpected navigation URL: {pece_page.url}")
        if any(x in pece_page.url.casefold() for x in ("login", "signin", "auth")):
            raise RuntimeError("STOP: PE/CE tab requires login. No login was attempted.")
        time.sleep(max(0.0, wait_seconds))
        if production_page.url != before_url:
            raise RuntimeError("SAFETY STOP: production Tab 1 URL changed.")
        manifest = {
            "target_url": target_url, "pece_page_url": pece_page.url,
            "production_page_url_before": before_url,
            "production_page_url_after": production_page.url,
            "xhr_fetch_count": len(records), "request_failures": failures,
            "page_errors": errors, "records": records,
            "download_button_clicked": False,
        }
        (out/"manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
        return {"output_folder": str(out), "manifest": manifest}
    finally:
        try: pece_page.close()
        except Exception: pass
