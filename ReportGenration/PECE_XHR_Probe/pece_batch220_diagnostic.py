from pathlib import Path
import json, time
from datetime import datetime
from urllib.parse import parse_qsl, urlencode

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
SELECTOR = "#optSymbol"
ENDPOINT_MARKER = "getDataForTotalPECEOIDiff_Beta_v7_chart_v5.php"
PER_SYMBOL_TIMEOUT = 8.0


def _safe_post_data(pd):
    if not pd:
        return None
    try:
        pairs = parse_qsl(pd, keep_blank_values=True)
    except Exception:
        return "[REDACTED]"
    sensitive = {"sessionid", "phpsessid", "token", "password", "passwd", "username", "user_name", "userpassword", "cf_clearance"}
    return urlencode([(k, "[REDACTED]" if k.lower().strip() in sensitive else v) for k, v in pairs])


def _symbol(pd):
    if not pd:
        return None
    try:
        for k, v in parse_qsl(pd, keep_blank_values=True):
            if k == "optSymbol":
                return v
    except Exception:
        return None
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
    normalized = []
    max_cols = 0
    for rec in records:
        obj = rec.get("payload") or {}
        rows = obj.get("aaData") or []
        for row in rows:
            if not isinstance(row, list):
                row = [row]
            max_cols = max(max_cols, len(row))
            normalized.append((rec["symbol"], rec.get("response_symbol"), rec.get("captured_at"), row))
    columns = [f"col_{i:02d}" for i in range(1, max_cols + 1)]
    out = []
    for symbol, response_symbol, captured_at, row in normalized:
        padded = list(row) + [None] * (max_cols - len(row))
        out.append([symbol, response_symbol, captured_at] + padded)
    df = pd.DataFrame(out, columns=["symbol", "response_symbol", "captured_at"] + columns)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="PECE_DATA", index=False)
        summary = pd.DataFrame([
            {"symbol": r["symbol"], "response_symbol": r.get("response_symbol"), "rows": r.get("row_count", 0), "body_bytes": r.get("body_length", 0), "status": r.get("status"), "elapsed_seconds": r.get("elapsed_seconds")}
            for r in records
        ])
        summary.to_excel(writer, sheet_name="SUMMARY", index=False)


def acquire_batch220(context, production_page, output_root):
    if context is None or production_page is None or production_page.is_closed():
        raise RuntimeError("Existing authenticated BrowserContext/page is not available. Open the normal session first.")

    root = Path(output_root)
    out = root / f"batch220_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=False)

    page = context.new_page()
    responses = []
    errors = []
    results = []
    started = time.perf_counter()
    original = None

    def on_response(response):
        try:
            if ENDPOINT_MARKER not in response.url:
                return
            req = response.request
            sym = _symbol(req.post_data)
            if not sym or response.status != 200:
                return
            body = response.body()
            payload, rows = _parse_payload(body)
            rec = {
                "url": response.url,
                "status": response.status,
                "method": req.method,
                "resource_type": req.resource_type,
                "response_symbol": sym,
                "body_length": len(body),
                "post_data": _safe_post_data(req.post_data),
                "payload": payload,
                "row_count": len(rows) if rows is not None else 0,
                "captured_at": datetime.now().isoformat(timespec="seconds"),
            }
            if rows is not None and len(rows) > 0:
                responses.append(rec)
        except Exception as exc:
            errors.append(f"response: {exc}")

    page.on("response", on_response)
    page.on("requestfailed", lambda r: errors.append(f"requestfailed: {r.method} {r.url} :: {r.failure}"))
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        sel = page.locator(SELECTOR)
        sel.wait_for(state="attached", timeout=30000)
        count = sel.locator("option").count()
        original = sel.input_value()
        symbols = []
        for i in range(count):
            value = sel.locator("option").nth(i).get_attribute("value")
            if value and value not in symbols:
                symbols.append(value)
        if len(symbols) < 220:
            raise RuntimeError(f"Expected at least 220 stock options, found {len(symbols)}")

        for idx, sym in enumerate(symbols, 1):
            before = len(responses)
            symbol_started = time.perf_counter()
            sel.select_option(sym)
            captured = None
            deadline = time.perf_counter() + PER_SYMBOL_TIMEOUT
            while time.perf_counter() < deadline:
                page.wait_for_timeout(100)
                for rec in responses[before:]:
                    if rec.get("response_symbol") == sym:
                        captured = rec
                        break
                if captured:
                    break
            elapsed = time.perf_counter() - symbol_started
            if captured:
                results.append({
                    "symbol": sym,
                    "status": "OK",
                    "response_symbol": captured["response_symbol"],
                    "body_length": captured["body_length"],
                    "row_count": captured["row_count"],
                    "elapsed_seconds": round(elapsed, 3),
                })
            else:
                results.append({"symbol": sym, "status": "TIMEOUT", "elapsed_seconds": round(elapsed, 3)})
                errors.append(f"timeout: {sym}")

            # Persist a compact progress file so a long run is inspectable even if interrupted.
            progress = {
                "completed": idx,
                "total": len(symbols),
                "ok": sum(1 for r in results if r["status"] == "OK"),
                "failed": sum(1 for r in results if r["status"] != "OK"),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "symbols_per_second": round(idx / (time.perf_counter() - started), 4),
                "last_symbol": sym,
            }
            (out / "progress.json").write_text(json.dumps(progress, indent=2), encoding="utf-8")

        try:
            sel.select_option(original)
            page.wait_for_timeout(500)
        except Exception as exc:
            errors.append(f"restore: {exc}")

        elapsed_total = time.perf_counter() - started
        successful = [r for r in results if r["status"] == "OK"]
        payload_records = []
        by_symbol = {r["response_symbol"]: r for r in responses}
        for r in successful:
            if r["symbol"] in by_symbol:
                payload_records.append(by_symbol[r["symbol"]])

        for i, rec in enumerate(payload_records, 1):
            (out / f"response_{i:04d}.json").write_text(json.dumps(rec["payload"], ensure_ascii=False), encoding="utf-8")

        excel = out / "PECE_220_Snapshot.xlsx"
        _write_excel(excel, payload_records)
        latest = root / "Latest_PECE_220.xlsx"
        latest.write_bytes(excel.read_bytes())

        manifest = {
            "target_url": TARGET_URL,
            "selector": SELECTOR,
            "endpoint_marker": ENDPOINT_MARKER,
            "option_count": count,
            "requested_count": len(symbols),
            "successful_count": len(successful),
            "failed_count": len(results) - len(successful),
            "started": datetime.now().isoformat(),
            "elapsed_seconds": round(elapsed_total, 3),
            "symbols_per_second": round(len(symbols) / elapsed_total, 4) if elapsed_total else None,
            "projected_220_seconds": round(220 / (len(symbols) / elapsed_total), 3) if elapsed_total and len(symbols) else None,
            "under_4_minutes": elapsed_total < 240 if len(symbols) == 220 else None,
            "original_symbol": original,
            "results": results,
            "errors": errors,
            "output_excel": excel.name,
            "latest_excel": str(latest),
            "production_page_after": {"url": production_page.url, "closed": production_page.is_closed()},
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return out
    finally:
        try:
            page.close()
        except Exception:
            pass
