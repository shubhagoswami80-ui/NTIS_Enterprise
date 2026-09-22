from __future__ import annotations

import json
import re
import time
import traceback
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
ENDPOINT_RE = re.compile(r"/getDataForTotalPECEOIDiff_Beta_v7_chart_v5\.php(?:\?|$)", re.I)


def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_json(body: str):
    try:
        obj = json.loads(body)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _validate_payload(body: str):
    """Return (valid, reason, row_count, object). Never invent data."""
    obj = _parse_json(body or "")
    if not obj:
        return False, "invalid_or_non_json_response", 0, None
    if "aaData" not in obj:
        return False, "missing_aaData", 0, obj
    data = obj.get("aaData")
    if not isinstance(data, list):
        return False, "aaData_not_list", 0, obj
    if not data:
        return False, "aaData_empty", 0, obj
    if not all(isinstance(row, list) for row in data):
        return False, "aaData_contains_non_list_row", 0, obj
    return True, "ok", len(data), obj


def _safe_post_data(post_data: str) -> str:
    pairs = parse_qsl(post_data or "", keep_blank_values=True)
    out = []
    for k, v in pairs:
        kl = k.lower()
        if kl in {"sessionid", "phpsessid", "cf_clearance", "password", "passwd", "token"} or "session" in kl:
            v = "<redacted>"
        out.append((k, v))
    return urlencode(out)


def _make_body(base_pairs, symbol):
    return urlencode([(k, symbol if k == "optSymbol" else v) for k, v in base_pairs])


def _safe_name(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", symbol)


def run_integrity_batch(context, output_root, expected_symbol_count=220, concurrency=6,
                        retries=2, status_callback=None):
    """Run authenticated in-context XHR batch with strict no-fabrication semantics."""
    root = Path(output_root)
    out = root / f"batch_integrity_{time.strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=False)

    def status(msg):
        if status_callback:
            try: status_callback(msg)
            except Exception: pass

    manifest = {
        "status": "starting",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "target_url": TARGET_URL,
        "expected_symbol_count": expected_symbol_count,
        "symbol_count": 0,
        "completed_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "unavailable_count": 0,
        "errors": [],
        "results": [],
        "data_policy": {
            "fabrication": "forbidden",
            "missing_data": "record_status_only",
            "invalid_payload": "do_not_write_as_data",
            "retry_failed": retries,
        },
    }
    _write(out / "00_STARTED.txt", "Integrity batch started\n")
    _write(out / "manifest.json", manifest)

    page = None
    try:
        if context is None:
            raise RuntimeError("Manager browser context is None")
        page = context.new_page()
        _write(out / "01_TAB_OPENED.txt", "Temporary PE/CE tab created\n")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("#optSymbol", timeout=30000)

        symbols = page.locator("#optSymbol option").evaluate_all(
            """els => els.map(e => ({value:e.value||'', text:(e.textContent||'').trim()})).filter(x=>x.value)"""
        )
        seen, unique = set(), []
        for s in symbols:
            if s["value"] not in seen:
                seen.add(s["value"]); unique.append(s)
        symbols = unique
        manifest["symbol_count"] = len(symbols)
        manifest["symbol_count_check"] = "pass" if len(symbols) == expected_symbol_count else "mismatch"
        manifest["symbols"] = symbols
        _write(out / "symbols.json", symbols)
        _write(out / "05_SYMBOLS_FOUND.txt", f"{len(symbols)} symbols found; expected {expected_symbol_count}\n")
        _write(out / "manifest.json", manifest)

        captured = []
        def on_response(resp):
            try:
                if resp.request.method == "POST" and ENDPOINT_RE.search(resp.url):
                    captured.append(resp)
            except Exception: pass
        page.on("response", on_response)

        deadline = time.monotonic() + 20
        while not captured and time.monotonic() < deadline:
            page.wait_for_timeout(250)
        if not captured:
            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
        if not captured:
            raise RuntimeError("Native PE/CE XHR template was not captured")

        resp = captured[-1]
        post = resp.request.post_data or ""
        base = parse_qsl(post, keep_blank_values=True)
        if not any(k == "optSymbol" for k, _ in base):
            raise RuntimeError("Captured XHR has no optSymbol")
        manifest["template_endpoint"] = resp.url
        manifest["template_status"] = resp.status
        manifest["template_post_data"] = _safe_post_data(post)
        _write(out / "06_XHR_TEMPLATE_CAPTURED.txt", f"{resp.url}\nHTTP {resp.status}\n")
        _write(out / "manifest.json", manifest)

        fetch_js = r"""
        async ({url, jobs, concurrency}) => {
          let next=0; const results=new Array(jobs.length);
          async function worker(){
            while(true){ const i=next++; if(i>=jobs.length)return; const j=jobs[i]; const t=performance.now();
              try{ const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With':'XMLHttpRequest'},body:j.body,credentials:'include',cache:'no-store'});
                const text=await r.text(); results[i]={status:r.status,ok:r.ok,elapsed_ms:performance.now()-t,body:text};
              }catch(e){results[i]={status:0,ok:false,elapsed_ms:performance.now()-t,error:String(e)};}
            }
          }
          await Promise.all(Array.from({length:Math.min(concurrency,jobs.length)},()=>worker())); return results;
        }
        """

        def run_jobs(job_list):
            return page.evaluate(fetch_js, {"url": resp.url,
                "jobs":[{"symbol":s["value"],"body":_make_body(base,s["value"])} for s in job_list],
                "concurrency":min(concurrency,max(1,len(job_list)))})

        started = time.perf_counter()
        pending = list(symbols)
        attempt = 0
        final = {}
        while pending and attempt <= retries:
            attempt += 1
            status(f"PE/CE integrity: attempt {attempt}, {len(pending)} symbol(s)")
            results = run_jobs(pending)
            next_pending=[]
            for sym, result in zip(pending, results):
                ok, reason, rows, obj = _validate_payload(result.get("body", "")) if result.get("ok") else (False, result.get("error", "http_error"), 0, None)
                rec = {
                    "symbol": sym["value"], "text": sym["text"], "attempt": attempt,
                    "http_status": result.get("status"), "ok": bool(result.get("ok")),
                    "payload_valid": ok, "reason": reason, "rows": rows,
                    "elapsed_ms": round(float(result.get("elapsed_ms",0)),1),
                }
                if ok:
                    final[sym["value"]] = rec
                    fname=f"{len(final):03d}_{_safe_name(sym['value'])}.json"
                    _write(out/fname, result.get("body",""))
                    rec["file"]=fname
                else:
                    final[sym["value"]]=rec
                    if attempt <= retries:
                        next_pending.append(sym)
            pending = next_pending

        results = []
        for s in symbols:
            rec = final.get(s["value"], {"symbol":s["value"],"text":s["text"],"ok":False,"reason":"no_result"})
            results.append(rec)

        manifest["results"] = results
        manifest["completed_count"] = len(results)
        manifest["success_count"] = sum(1 for r in results if r.get("file"))
        manifest["failed_count"] = len(results)-manifest["success_count"]
        manifest["unavailable_count"] = sum(1 for r in results if r.get("reason") in {"aaData_empty","invalid_or_non_json_response","http_error"} or not r.get("payload_valid"))
        manifest["elapsed_seconds"] = round(time.perf_counter()-started,2)
        manifest["symbols_per_second"] = round(len(results)/max(manifest["elapsed_seconds"],.001),3)
        manifest["status"] = "completed_with_gaps" if manifest["failed_count"] or manifest["symbol_count"] != expected_symbol_count else "completed"
        manifest["integrity_gate"] = "PASS" if manifest["status"] == "completed" else "HOLD"
        _write(out/"manifest.json",manifest)
        _write(out/"99_COMPLETED.txt",f"{manifest['completed_count']} discovered; {manifest['success_count']} valid data; {manifest['failed_count']} unavailable/invalid; integrity={manifest['integrity_gate']}\n")
        return manifest
    except Exception as exc:
        manifest.update(status="failed", fatal_error=repr(exc), traceback=traceback.format_exc(), integrity_gate="HOLD")
        _write(out/"manifest.json",manifest); _write(out/"ERROR.txt",traceback.format_exc())
        raise
    finally:
        if page is not None:
            try: page.close()
            except Exception: pass
