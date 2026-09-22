from __future__ import annotations

import json
import re
import time
import traceback
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
ENDPOINT_RE = re.compile(r"/getDataForTotalPECEOIDiff_Beta_v7_chart_v5\.php(?:\?|$)", re.I)

INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "NIFTYFPI", "SENSEX", "BANKEX"}

def _load_allowed_symbols():
    candidates = [
        Path(__file__).with_name("pece_symbols_master_verified.json"),
        Path(__file__).with_name("pece_symbols_master.json"),
        Path("E:/NSE_Daily_Analysis/Output/market_master.csv"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            if path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                items = data.get("symbols", data) if isinstance(data, dict) else data
                out = set()
                for item in items:
                    value = item.get("value") if isinstance(item, dict) else item
                    if value:
                        out.add(str(value).strip().upper())
                if out:
                    return out - INDEX_SYMBOLS, str(path)
            else:
                import csv
                with path.open(encoding="utf-8-sig", newline="") as fh:
                    out = {str(row.get("Symbol", "")).strip().upper() for row in csv.DictReader(fh)}
                out.discard("")
                if out:
                    return out - INDEX_SYMBOLS, str(path)
        except Exception:
            continue
    return None, None


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse(body: str):
    try:
        obj = json.loads(body or "")
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def validate_payload(body: str):
    obj = _parse(body)
    if not obj:
        return False, "invalid_or_non_json_response", 0, None
    data = obj.get("aaData")
    if not isinstance(data, list):
        return False, "missing_or_invalid_aaData", 0, obj
    if not data:
        return False, "aaData_empty", 0, obj
    if not all(isinstance(row, list) for row in data):
        return False, "aaData_contains_non_list_row", 0, obj
    width = len(data[0])
    if width == 0 or any(len(row) != width for row in data):
        return False, "aaData_inconsistent_row_width", 0, obj
    return True, "ok", len(data), obj


def _safe_post_data(post_data: str) -> str:
    out = []
    for k, v in parse_qsl(post_data or "", keep_blank_values=True):
        kl = k.lower()
        if kl in {"sessionid", "phpsessid", "cf_clearance", "password", "passwd", "token"} or "session" in kl:
            v = "<redacted>"
        out.append((k, v))
    return urlencode(out)


def _make_body(base_pairs, symbol):
    return urlencode([(k, symbol if k == "optSymbol" else v) for k, v in base_pairs])


def _safe_name(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", symbol)


def _flatten_rows(results, snapshot_id):
    rows = []
    for result in results:
        if not result.get("valid"):
            continue
        symbol = result["symbol"]
        obj = result["object"]
        for row_no, row in enumerate(obj["aaData"], 1):
            record = {
                "Snapshot": snapshot_id,
                "Symbol": symbol,
                "Response_Row": row_no,
            }
            for i, value in enumerate(row, 1):
                record[f"Field_{i:02d}"] = value
            rows.append(record)
    return rows


def _write_excel(path: Path, rows, status_rows, manifest):
    import pandas as pd
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="Data")
        pd.DataFrame(status_rows).to_excel(writer, index=False, sheet_name="Status")
        pd.DataFrame([manifest]).to_excel(writer, index=False, sheet_name="Run")


def run_pece_xhr_batch(context, output_root, job, status_callback=None):
    """Production PE/CE batch acquisition. Missing/invalid data is status only; never fabricated."""
    root = Path(output_root)
    destination = Path(str(job.get("destination") or root)).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    cycle_id = time.strftime("%Y%m%d_%H%M%S")
    # Downloader-owned PE/CE data is partitioned by trading date.
    # The timestamped filename is the sole "latest" mechanism; no mutable
    # No mutable latest copy is maintained.
    dt = time.localtime()
    year_dir = destination / time.strftime("%Y", dt)
    month_dir = year_dir / time.strftime("%B", dt).lower()
    day_dir = month_dir / time.strftime("%Y-%m-%d", dt)
    cycle = day_dir
    cycle.mkdir(parents=True, exist_ok=True)

    expected = int(job.get("expected_symbol_count", 220))
    concurrency = max(1, min(12, int(job.get("concurrency", 8))))
    retries = max(0, min(5, int(job.get("retries", 2))))
    timeout_ms = max(3000, min(30000, int(float(job.get("request_timeout_seconds", 15)) * 1000)))

    manifest = {
        "status": "starting",
        "integrity_gate": "HOLD",
        "cycle_id": cycle_id,
        "target_url": str(job.get("url") or TARGET_URL),
        "expected_symbol_count": expected,
        "symbol_count": 0,
        "completed_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "data_policy": {
            "fabrication": "forbidden",
            "missing_data": "status_only",
            "carry_forward": "forbidden",
            "cross_symbol_substitution": "forbidden",
            "retry_failed": retries,
        },
        "results": [],
    }
    manifest_path = cycle / f"PECE_{cycle_id}.json"
    _write_json(manifest_path, manifest)
    (cycle / "00_STARTED.txt").write_text("PE/CE XHR cycle started\n", encoding="utf-8")

    page = None
    try:
        if context is None:
            raise RuntimeError("Existing authenticated BrowserContext is required")
        page = context.new_page()
        page.goto(manifest["target_url"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("#optSymbol", timeout=30000)

        symbols = page.locator("#optSymbol option").evaluate_all(
            "els => els.map(e => ({value:e.value||'', text:(e.textContent||'').trim()})).filter(x=>x.value)"
        )
        unique, seen = [], set()
        for s in symbols:
            if s["value"] not in seen:
                seen.add(s["value"]); unique.append(s)
        symbols = unique
        allowed, allowed_source = _load_allowed_symbols()
        if allowed:
            before = len(symbols)
            symbols = [s for s in symbols if str(s.get("value", "")).strip().upper() in allowed]
            manifest["symbol_universe_filter"] = {
                "applied": True, "source": allowed_source,
                "discovered_count": before, "eligible_count": len(symbols),
                "excluded_count": before - len(symbols),
            }
            expected = len(symbols)
            manifest["expected_symbol_count"] = expected
        manifest["symbol_count"] = len(symbols)
        manifest["symbol_count_check"] = "pass" if len(symbols) == expected else "mismatch"
        manifest["symbols"] = symbols
        _write_json(cycle / "symbols.json", symbols)
        (cycle / "01_SYMBOLS_FOUND.txt").write_text(
            f"{len(symbols)} symbols discovered; expected {expected}\n", encoding="utf-8"
        )

        captured = []
        def on_response(resp):
            try:
                if resp.request.method == "POST" and ENDPOINT_RE.search(resp.url):
                    captured.append(resp)
            except Exception:
                pass
        page.on("response", on_response)

        deadline = time.monotonic() + 20
        while not captured and time.monotonic() < deadline:
            page.wait_for_timeout(250)
        if not captured:
            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
        if not captured:
            raise RuntimeError("Native PE/CE XHR template was not captured")

        template = captured[-1]
        post = template.request.post_data or ""
        base_pairs = parse_qsl(post, keep_blank_values=True)
        if not any(k == "optSymbol" for k, _ in base_pairs):
            raise RuntimeError("Captured XHR has no optSymbol")
        manifest["template_endpoint"] = template.url
        manifest["template_status"] = template.status
        manifest["template_post_data"] = _safe_post_data(post)
        (cycle / "02_XHR_TEMPLATE_CAPTURED.txt").write_text(
            f"{template.url}\nHTTP {template.status}\n", encoding="utf-8"
        )

        fetch_js = r"""
        async ({url, jobs, concurrency, timeoutMs}) => {
          let next=0; const results=new Array(jobs.length);
          async function worker(){
            while(true){ const i=next++; if(i>=jobs.length)return; const j=jobs[i]; const t=performance.now();
              const ctl=new AbortController(); const timer=setTimeout(()=>ctl.abort(), timeoutMs);
              try{
                const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With':'XMLHttpRequest'},body:j.body,credentials:'include',cache:'no-store',signal:ctl.signal});
                const text=await r.text(); results[i]={status:r.status,ok:r.ok,elapsed_ms:performance.now()-t,body:text};
              }catch(e){results[i]={status:0,ok:false,elapsed_ms:performance.now()-t,error:String(e)};}
              finally{clearTimeout(timer);}
            }
          }
          await Promise.all(Array.from({length:Math.min(concurrency,jobs.length)},()=>worker())); return results;
        }
        """

        def execute(batch):
            return page.evaluate(fetch_js, {
                "url": template.url,
                "jobs": [{"symbol": s["value"], "body": _make_body(base_pairs, s["value"])} for s in batch],
                "concurrency": concurrency,
                "timeoutMs": timeout_ms,
            })

        started = time.perf_counter()
        pending = list(symbols)
        final = {}
        attempt = 0
        while pending and attempt <= retries:
            attempt += 1
            if status_callback:
                status_callback(f"{job.get('name','PE/CE')}: attempt {attempt}; {len(pending)} pending")
            raw = execute(pending)
            next_pending = []
            for sym, result in zip(pending, raw):
                valid, reason, rows, obj = validate_payload(result.get("body", "")) if result.get("ok") else (False, result.get("error", "http_error"), 0, None)
                rec = {
                    "symbol": sym["value"], "text": sym["text"], "attempt": attempt,
                    "http_status": result.get("status"), "elapsed_ms": round(float(result.get("elapsed_ms", 0)), 1),
                    "payload_valid": valid, "reason": reason, "rows": rows,
                    "valid": valid,
                }
                if valid:
                    final[sym["value"]] = rec | {"object": obj}
                else:
                    final[sym["value"]] = rec
                    if attempt <= retries:
                        next_pending.append(sym)
            pending = next_pending

        ordered = []
        for s in symbols:
            r = final.get(s["value"], {"symbol": s["value"], "text": s["text"], "valid": False, "reason": "no_result"})
            if r.get("valid"):
                # Per-symbol payloads are intentionally not persisted in production.
                # The consolidated timestamped Excel is the retained acquisition artifact.
                r = dict(r)
            else:
                r = dict(r)
            r.pop("object", None)
            ordered.append(r)

        manifest["results"] = ordered
        manifest["completed_count"] = len(ordered)
        manifest["success_count"] = sum(1 for r in ordered if r.get("valid"))
        manifest["failed_count"] = len(ordered) - manifest["success_count"]
        manifest["elapsed_seconds"] = round(time.perf_counter() - started, 2)
        manifest["symbols_per_second"] = round(len(ordered) / max(manifest["elapsed_seconds"], 0.001), 3)
        manifest["status"] = "completed" if manifest["symbol_count"] == expected and manifest["failed_count"] == 0 else "completed_with_gaps"
        manifest["integrity_gate"] = "PASS" if manifest["status"] == "completed" else "HOLD"

        status_rows = []
        raw_results = []
        for s in symbols:
            r = final.get(s["value"], {"symbol": s["value"], "valid": False, "reason": "no_result"})
            status_rows.append({k: v for k, v in r.items() if k != "object"})
            if r.get("valid"):
                raw_results.append(r)
        rows = _flatten_rows(raw_results, cycle_id)
        xlsx = cycle / f"PECE_{cycle_id}.xlsx"
        _write_excel(xlsx, rows, status_rows, manifest)
        manifest["snapshot_file"] = str(xlsx)
        manifest.pop("latest_file", None)
        _write_json(manifest_path, manifest)
        (cycle / "99_COMPLETED.txt").write_text(
            f"discovered={manifest['symbol_count']} valid={manifest['success_count']} failed={manifest['failed_count']} integrity={manifest['integrity_gate']}\n",
            encoding="utf-8",
        )
        return manifest
    except Exception as exc:
        manifest.update(status="failed", integrity_gate="HOLD", fatal_error=repr(exc), traceback=traceback.format_exc())
        _write_json(cycle / f"PECE_{cycle_id}.json", manifest)
        (cycle / "ERROR.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        if page is not None:
            try: page.close()
            except Exception: pass
