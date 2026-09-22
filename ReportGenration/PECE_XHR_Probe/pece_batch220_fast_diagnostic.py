from pathlib import Path
import json
import time
from datetime import datetime
from urllib.parse import parse_qsl, urlencode

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
SELECTOR = "#optSymbol"
ENDPOINT_MARKER = "getDataForTotalPECEOIDiff_Beta_v7_chart_v5.php"
RESPONSE_TIMEOUT_MS = 4000
INITIAL_WAIT_MS = 2500


def _safe_post_data(post_data):
    if not post_data:
        return None
    try:
        pairs = parse_qsl(post_data, keep_blank_values=True)
    except Exception:
        return "[REDACTED]"
    sensitive = {"sessionid", "phpsessid", "token", "password", "passwd", "username", "user_name", "userpassword", "cf_clearance"}
    return urlencode([(k, "[REDACTED]" if k.lower().strip() in sensitive else v) for k, v in pairs])


def _symbol(post_data):
    if not post_data:
        return None
    try:
        for key, value in parse_qsl(post_data, keep_blank_values=True):
            if key == "optSymbol":
                return value
    except Exception:
        pass
    return None


def _parse_payload(body):
    try:
        obj = json.loads(body.decode("utf-8-sig", errors="replace"))
        rows = obj.get("aaData")
        if isinstance(rows, list):
            return obj, rows
    except Exception:
        pass
    return None, None


def _write_excel(path, records):
    import pandas as pd
    rows_out = []
    max_cols = 0
    for rec in records:
        payload = rec.get("payload") or {}
        for row in payload.get("aaData") or []:
            row = row if isinstance(row, list) else [row]
            max_cols = max(max_cols, len(row))
            rows_out.append([rec["symbol"], rec.get("response_symbol"), rec.get("captured_at"), *row])
    columns = ["symbol", "response_symbol", "captured_at"] + [f"col_{i:02d}" for i in range(1, max_cols + 1)]
    padded = [r + [None] * (len(columns) - len(r)) for r in rows_out]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(padded, columns=columns).to_excel(writer, sheet_name="PECE_DATA", index=False)
        pd.DataFrame([
            {"symbol": r["symbol"], "response_symbol": r.get("response_symbol"), "status": r.get("status"),
             "rows": r.get("row_count", 0), "body_bytes": r.get("body_length", 0),
             "elapsed_seconds": r.get("elapsed_seconds"), "error": r.get("error", "")}
            for r in records
        ]).to_excel(writer, sheet_name="SUMMARY", index=False)


def acquire_batch220_fast(context, production_page, output_root):
    if context is None or production_page is None or production_page.is_closed():
        raise RuntimeError("Existing authenticated BrowserContext/page is not available. Open the normal session first.")

    root = Path(output_root)
    out = root / f"batch220_fast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=False)
    page = context.new_page()
    events = []
    errors = []
    results = []
    original = None
    started = time.perf_counter()

    def on_response(response):
        try:
            if ENDPOINT_MARKER not in response.url:
                return
            req = response.request
            sym = _symbol(req.post_data)
            if response.status != 200:
                return
            body = response.body()
            payload, rows = _parse_payload(body)
            events.append({
                "symbol": sym,
                "status": response.status,
                "body_length": len(body),
                "row_count": len(rows) if rows is not None else 0,
                "resource_type": req.resource_type,
            })
        except Exception as exc:
            errors.append(f"response_handler: {exc}")

    page.on("response", on_response)
    page.on("requestfailed", lambda r: errors.append(f"requestfailed: {r.method} {r.url} :: {r.failure}"))
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(INITIAL_WAIT_MS)
        sel = page.locator(SELECTOR)
        sel.wait_for(state="attached", timeout=30000)
        option_count = sel.locator("option").count()
        original = sel.input_value()
        symbols = []
        for i in range(option_count):
            value = sel.locator("option").nth(i).get_attribute("value")
            if value and value not in symbols:
                symbols.append(value)
        if len(symbols) < 220:
            raise RuntimeError(f"Expected at least 220 stock/index options, found {len(symbols)}")
        symbols = symbols[:220]

        for idx, sym in enumerate(symbols, 1):
            symbol_started = time.perf_counter()
            captured = None
            try:
                with page.expect_response(
                    lambda r: ENDPOINT_MARKER in r.url and r.request.method == "POST",
                    timeout=RESPONSE_TIMEOUT_MS,
                ) as waiter:
                    sel.select_option(sym)
                response = waiter.value
                body = response.body()
                payload, rows = _parse_payload(body)
                response_symbol = _symbol(response.request.post_data)
                if rows is None or not rows:
                    raise RuntimeError("endpoint response had no aaData rows")
                captured = {
                    "symbol": sym,
                    "response_symbol": response_symbol,
                    "status": "OK",
                    "body_length": len(body),
                    "row_count": len(rows),
                    "elapsed_seconds": round(time.perf_counter() - symbol_started, 3),
                    "captured_at": datetime.now().isoformat(timespec="seconds"),
                    "payload": payload,
                    "post_data": _safe_post_data(response.request.post_data),
                }
            except Exception as exc:
                captured = {
                    "symbol": sym,
                    "response_symbol": None,
                    "status": "TIMEOUT_OR_ERROR",
                    "body_length": 0,
                    "row_count": 0,
                    "elapsed_seconds": round(time.perf_counter() - symbol_started, 3),
                    "captured_at": datetime.now().isoformat(timespec="seconds"),
                    "payload": None,
                    "error": str(exc),
                }
                errors.append(f"{sym}: {exc}")
            results.append(captured)
            progress = {
                "completed": idx, "total": len(symbols),
                "ok": sum(r["status"] == "OK" for r in results),
                "failed": sum(r["status"] != "OK" for r in results),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "symbols_per_second": round(idx / (time.perf_counter() - started), 4),
                "last_symbol": sym,
            }
            (out / "progress.json").write_text(json.dumps(progress, indent=2), encoding="utf-8")
            if captured["status"] == "OK":
                (out / f"response_{idx:04d}.json").write_text(json.dumps(captured["payload"], ensure_ascii=False), encoding="utf-8")

        try:
            sel.select_option(original)
            page.wait_for_timeout(500)
        except Exception as exc:
            errors.append(f"restore: {exc}")

        elapsed = time.perf_counter() - started
        ok_records = [r for r in results if r["status"] == "OK"]
        excel = out / "PECE_220_Snapshot.xlsx"
        _write_excel(excel, ok_records)
        latest = root / "Latest_PECE_220.xlsx"
        latest.write_bytes(excel.read_bytes())
        manifest = {
            "mode": "fast_native_xhr_capture",
            "target_url": TARGET_URL,
            "selector": SELECTOR,
            "endpoint_marker": ENDPOINT_MARKER,
            "option_count": option_count,
            "requested_count": len(symbols),
            "successful_count": len(ok_records),
            "failed_count": len(results) - len(ok_records),
            "elapsed_seconds": round(elapsed, 3),
            "symbols_per_second": round(len(symbols) / elapsed, 4) if elapsed else None,
            "under_4_minutes": elapsed < 240,
            "projected_220_seconds": round(220 / (len(symbols) / elapsed), 3) if elapsed and symbols else None,
            "original_symbol": original,
            "results": [{k: v for k, v in r.items() if k != "payload" and k != "post_data"} for r in results],
            "errors": errors,
            "output_excel": excel.name,
            "latest_excel": latest.name,
            "production_page_after": {"url": production_page.url, "closed": production_page.is_closed()},
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return out
    finally:
        try:
            page.close()
        except Exception:
            pass
