from __future__ import annotations

import json
import re
import time
import traceback
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
ENDPOINT_RE = re.compile(
    r"/getDataForTotalPECEOIDiff_Beta_v7_chart_v5\.php(?:\?|$)", re.I
)

def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def _safe_post_data(post_data: str) -> str:
    pairs = parse_qsl(post_data or "", keep_blank_values=True)
    redacted = []
    for k, v in pairs:
        kl = k.lower()
        if kl in {"sessionid", "phpsessid", "cf_clearance", "password", "passwd", "token"} or "session" in kl:
            v = "<redacted>"
        redacted.append((k, v))
    return urlencode(redacted)

def _parse_json(body: str):
    try:
        obj = json.loads(body)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None

def _row_count(body: str) -> int:
    obj = _parse_json(body)
    return len(obj.get("aaData") or []) if obj else 0

def run_full_220(context, output_root, status_callback=None, concurrency=6):
    root = Path(output_root)
    out = root / f"batch220_final_{time.strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=False)

    def status(msg):
        if status_callback:
            try:
                status_callback(msg)
            except Exception:
                pass

    # These files are intentionally written BEFORE any browser operation.
    _write(out / "00_STARTED.txt",
           f"PE/CE 220 diagnostic started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    manifest = {
        "status": "starting",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "target_url": TARGET_URL,
        "completed_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "errors": [],
        "results": [],
    }
    _write(out / "manifest.json", manifest)

    page = None
    try:
        if context is None:
            raise RuntimeError("Manager browser context is None")

        status("PE/CE: opening one temporary tab...")
        _write(out / "01_TAB_OPEN_START.txt", "Creating temporary PE/CE tab\n")
        page = context.new_page()
        _write(out / "02_TAB_OPENED.txt", f"Temporary tab created at {time.time()}\n")

        captured = []

        def on_response(resp):
            try:
                if (
                    resp.request.method == "POST"
                    and ENDPOINT_RE.search(resp.url)
                ):
                    captured.append(resp)
            except Exception:
                pass

        page.on("response", on_response)

        status("PE/CE: opening target URL and capturing native request...")
        _write(out / "03_NAVIGATION_START.txt", TARGET_URL + "\n")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        _write(out / "04_NAVIGATION_DONE.txt", page.url + "\n")

        page.wait_for_selector("#optSymbol", timeout=30000)
        symbols = page.locator("#optSymbol option").evaluate_all(
            """els => els.map(e => ({
                value: e.value || "",
                text: (e.textContent || "").trim()
            })).filter(x => x.value)"""
        )

        seen = set()
        unique = []
        for item in symbols:
            if item["value"] not in seen:
                seen.add(item["value"])
                unique.append(item)
        symbols = unique

        manifest["symbol_count"] = len(symbols)
        manifest["symbols"] = symbols
        _write(out / "symbols.json", symbols)
        _write(out / "manifest.json", manifest)
        _write(out / "05_SYMBOLS_FOUND.txt", f"{len(symbols)} symbols found\n")

        if len(symbols) < 200:
            raise RuntimeError(f"Expected about 220 stocks, found {len(symbols)}")

        # Allow the page's own script to issue its normal request.
        deadline = time.monotonic() + 20
        while not captured and time.monotonic() < deadline:
            page.wait_for_timeout(250)

        if not captured:
            # A reload gives the page one clean opportunity to issue its own request.
            status("PE/CE: native request not seen yet; performing one controlled reload...")
            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

        if not captured:
            raise RuntimeError("Native PE/CE XHR template was not captured")

        resp = captured[-1]
        endpoint = resp.url
        post = resp.request.post_data or ""
        if not post:
            raise RuntimeError("Captured PE/CE XHR contains no POST data")

        manifest["template_endpoint"] = endpoint
        manifest["template_post_data"] = _safe_post_data(post)
        manifest["template_status"] = resp.status
        manifest["template_body_length"] = len(resp.body())
        _write(out / "06_XHR_TEMPLATE_CAPTURED.txt",
               f"endpoint={endpoint}\nstatus={resp.status}\nbody_length={len(resp.body())}\n")
        _write(out / "manifest.json", manifest)

        base = parse_qsl(post, keep_blank_values=True)
        if not any(k == "optSymbol" for k, _ in base):
            raise RuntimeError("Captured request does not contain optSymbol")

        def make_body(symbol):
            return urlencode(
                [(k, symbol if k == "optSymbol" else v) for k, v in base]
            )

        bodies = [make_body(x["value"]) for x in symbols]

        # Fetch runs in the authenticated page itself. This keeps the browser
        # session/cookies and same-origin policy identical to the native request.
        fetch_js = r"""
        async ({url, bodies, concurrency}) => {
            let next = 0;
            const results = new Array(bodies.length);

            async function worker() {
                while (true) {
                    const i = next++;
                    if (i >= bodies.length) return;
                    const started = performance.now();
                    try {
                        const response = await fetch(url, {
                            method: "POST",
                            headers: {
                                "Content-Type":
                                  "application/x-www-form-urlencoded; charset=UTF-8",
                                "X-Requested-With": "XMLHttpRequest"
                            },
                            body: bodies[i],
                            credentials: "include",
                            cache: "no-store"
                        });
                        const text = await response.text();
                        results[i] = {
                            status: response.status,
                            ok: response.ok,
                            elapsed_ms: performance.now() - started,
                            body: text
                        };
                    } catch (e) {
                        results[i] = {
                            status: 0,
                            ok: false,
                            elapsed_ms: performance.now() - started,
                            error: String(e)
                        };
                    }
                }
            }

            const workers = [];
            for (let i = 0; i < Math.min(concurrency, bodies.length); i++) {
                workers.push(worker());
            }
            await Promise.all(workers);
            return results;
        }
        """

        started = time.perf_counter()
        results = []
        chunk_size = 20

        status(f"PE/CE: starting {len(symbols)} stocks with controlled XHR concurrency={concurrency}...")
        for pos in range(0, len(symbols), chunk_size):
            chunk = symbols[pos:pos + chunk_size]
            chunk_results = page.evaluate(
                fetch_js,
                {
                    "url": endpoint,
                    "bodies": [bodies[pos + i] for i in range(len(chunk))],
                    "concurrency": min(concurrency, len(chunk)),
                },
            )

            for item, result in zip(chunk, chunk_results):
                rec = {
                    "sequence": len(results) + 1,
                    "symbol": item["value"],
                    "text": item["text"],
                    "http_status": result.get("status"),
                    "ok": bool(result.get("ok")),
                    "elapsed_ms": round(float(result.get("elapsed_ms", 0)), 1),
                    "rows": _row_count(result.get("body", "")),
                }

                if rec["ok"] and rec["rows"] > 0:
                    filename = f"{rec['sequence']:03d}_{re.sub(r'[^A-Za-z0-9_.-]', '_', item['value'])}.json"
                    _write(out / filename, result.get("body", ""))
                    rec["file"] = filename
                else:
                    rec["error"] = result.get("error", "HTTP/non-data response")
                    manifest["errors"].append(rec.copy())

                results.append(rec)
                elapsed = time.perf_counter() - started
                manifest.update(
                    status="running",
                    completed_count=len(results),
                    success_count=sum(1 for x in results if x.get("file")),
                    failed_count=sum(1 for x in results if not x.get("file")),
                    elapsed_seconds=round(elapsed, 2),
                    symbols_per_second=round(len(results) / max(elapsed, 0.001), 3),
                    results=results,
                )
                _write(out / "progress.json", manifest)
                _write(out / "manifest.json", manifest)
                _write(out / "LATEST_PROGRESS.txt",
                       f"{len(results)}/{len(symbols)} completed; "
                       f"{manifest['success_count']} success; "
                       f"{manifest['failed_count']} failed; "
                       f"{manifest['elapsed_seconds']} sec\n")
                status(
                    f"PE/CE: {len(results)}/{len(symbols)} | "
                    f"success {manifest['success_count']} | "
                    f"failed {manifest['failed_count']} | "
                    f"{manifest['elapsed_seconds']} sec"
                )

        # Build a usable consolidated workbook.
        import pandas as pd

        status_df = pd.DataFrame(results)
        rows = []
        for rec in results:
            if not rec.get("file"):
                continue
            obj = _parse_json((out / rec["file"]).read_text(encoding="utf-8"))
            for row in (obj or {}).get("aaData") or []:
                rows.append({
                    "Symbol": rec["symbol"],
                    "Time": row[0] if row else "",
                    "RawRow": json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                })

        data_df = pd.DataFrame(rows)
        xlsx = out / "PECE_220_Snapshot.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            status_df.to_excel(writer, index=False, sheet_name="Stock_Status")
            data_df.to_excel(writer, index=False, sheet_name="PECE_Data")
            pd.DataFrame([{
                "Metric": "Stocks discovered", "Value": len(symbols)
            }, {
                "Metric": "Stocks completed", "Value": len(results)
            }, {
                "Metric": "Successful", "Value": manifest["success_count"]
            }, {
                "Metric": "Failed", "Value": manifest["failed_count"]
            }, {
                "Metric": "Elapsed seconds", "Value": manifest["elapsed_seconds"]
            }, {
                "Metric": "Stocks/second", "Value": manifest["symbols_per_second"]
            }]).to_excel(writer, index=False, sheet_name="Summary")

        latest = root / "Latest_PECE_220.xlsx"
        import shutil
        shutil.copy2(xlsx, latest)

        elapsed = time.perf_counter() - started
        rate = len(results) / max(elapsed, 0.001)
        manifest.update(
            status="completed",
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            elapsed_seconds=round(elapsed, 2),
            symbols_per_second=round(rate, 3),
            projected_220_seconds=round(220 / max(rate, 0.001), 2),
            excel=str(xlsx.name),
            latest=str(latest.name),
        )
        _write(out / "manifest.json", manifest)
        _write(out / "99_COMPLETED.txt",
               f"Completed {len(results)} stocks in {elapsed:.2f} seconds\n")
        status(
            f"PE/CE COMPLETE: {len(results)}/{len(symbols)} | "
            f"{manifest['success_count']} success | "
            f"{manifest['failed_count']} failed | "
            f"{elapsed:.2f} sec"
        )
        return manifest

    except Exception as exc:
        manifest.update(
            status="failed",
            fatal_error=repr(exc),
            traceback=traceback.format_exc(),
        )
        _write(out / "manifest.json", manifest)
        _write(out / "ERROR.txt", traceback.format_exc())
        status(f"PE/CE FAILED: {exc}")
        raise
    finally:
        # Only the temporary PE/CE tab is closed. The Manager's production
        # page and BrowserContext are never closed here.
        if page is not None:
            try:
                _write(out / "98_TAB_CLOSE_START.txt", "Closing temporary PE/CE tab\n")
                page.close()
                _write(out / "98_TAB_CLOSED.txt", "Temporary PE/CE tab closed\n")
            except Exception as close_error:
                try:
                    _write(out / "98_TAB_CLOSE_ERROR.txt", repr(close_error))
                except Exception:
                    pass
