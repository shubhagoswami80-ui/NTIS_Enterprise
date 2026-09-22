from __future__ import annotations
import json
import time
from datetime import datetime
from pathlib import Path

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"

def run_pece_manager_diagnostic(context, production_page, output_root: Path, wait_seconds: float = 20.0) -> dict:
    if context is None:
        raise RuntimeError("SAFETY STOP: existing Playwright context is None.")
    if production_page is None or production_page.is_closed():
        raise RuntimeError("SAFETY STOP: production page is not alive.")
    if production_page not in context.pages:
        raise RuntimeError("SAFETY STOP: production page is not in existing context.")
    before_url = production_page.url
    before_count = len(context.pages)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(output_root) / f"manager_capture_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    records, failures, errors = [], [], []

    def on_response(response):
        req = response.request
        if req.resource_type not in {"xhr", "fetch"}:
            return
        rec = {"captured_at": datetime.now().isoformat(timespec="seconds"),
               "method": req.method, "url": response.url, "status": response.status,
               "resource_type": req.resource_type,
               "content_type": response.headers.get("content-type", ""),
               "post_data": req.post_data,
               "request_headers": req.all_headers(),
               "response_headers": response.all_headers()}
        try:
            body = response.body()
            fn = f"response_{len(records):04d}.bin"
            (out/fn).write_bytes(body)
            rec["body_file"], rec["body_length"] = fn, len(body)
        except Exception as exc:
            rec["body_error"] = str(exc)
        records.append(rec)

    def on_failed(req):
        failures.append({"method": req.method, "url": req.url, "failure": req.failure or "unknown"})

    pece_page = context.new_page()
    pece_page.on("response", on_response)
    pece_page.on("requestfailed", on_failed)
    pece_page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        pece_page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        pece_page.wait_for_timeout(3000)
        if not pece_page.url.lower().startswith("https://www.icharts.in/"):
            raise RuntimeError("SAFETY STOP: unexpected PE/CE navigation URL.")
        if any(x in pece_page.url.casefold() for x in ("login","signin","auth")):
            raise RuntimeError("STOP: PE/CE tab requires login. No login attempted.")
        time.sleep(max(0.0, wait_seconds))
        if production_page.url != before_url:
            raise RuntimeError("SAFETY STOP: production Tab 1 URL changed.")
        if production_page.is_closed():
            raise RuntimeError("SAFETY STOP: production Tab 1 closed.")
        if len(context.pages) != before_count + 1:
            raise RuntimeError("SAFETY STOP: unexpected tab count.")
        manifest = {"target_url": TARGET_URL, "pece_page_url": pece_page.url,
                    "production_page_url_before": before_url,
                    "production_page_url_after": production_page.url,
                    "tab_count_before": before_count, "tab_count_during": len(context.pages),
                    "xhr_fetch_count": len(records), "request_failures": failures,
                    "page_errors": errors, "records": records,
                    "download_button_clicked": False}
        (out/"manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"output_folder": str(out), "manifest": manifest}
    finally:
        try: pece_page.close()
        except Exception: pass
