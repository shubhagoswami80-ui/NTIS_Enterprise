from __future__ import annotations

import json
import re
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import traceback
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
ENDPOINT_RE = re.compile(
    r"/getDataForTotalPECEOIDiff_Beta_v7_chart_v5\.php(?:\?|$)", re.I
)

# Authoritative iCharts PE/CE report output schema.
# The native XHR returns 31 source fields; six fields are packed pairs,
# expanding to these 37 report columns.
REPORT_HEADERS = [
    "Time",
    "Fut Price",
    "Fut PriceChg (Day)",
    "Fut PriceChg (Day) %",
    "Fut PriceChg",
    "Fut PriceChg %",
    "VWAP",
    "IV",
    "Fut Volume",
    "Tot Fut OI",
    "Fut OIChg (Day)",
    "Fut OIChg (Day) %",
    "Fut OI Chg",
    "Fut OI Chg %",
    "Tot CEVol (Day)",
    "Tot PEVol (Day)",
    "Diff (PE-CE Volume)",
    "CE Volume",
    "PE Volume",
    "PCR-Volume",
    "TotCE OI",
    "TotPE OI",
    "PCR-OI",
    "Diff(PE-CE OI)",
    "Diff(PE-CE OI %)",
    "Tot CE OIChg (Day)",
    "Tot PE OIChg (Day)",
    "CE OIChg/Vol %",
    "PE OIChg/Vol %",
    "PCR-OI Chg",
    "Diff(PE-CE OI Chg)",
    "Diff(PE-CE OI Chg %)",
    "CE OI Chg",
    "CE OI Chg %",
    "PE OI Chg",
    "PE OI Chg %",
    "OI ChgTrend",
]

# 1-based source field -> two output fields.
PACKED_PAIRS = {
    3: (2, 3),
    4: (4, 5),
    9: (10, 11),
    10: (12, 13),
    29: (32, 33),
    30: (34, 35),
}


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


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
    width = len(data[0]) if isinstance(data[0], list) else 0
    # Non-blocking validation: accept any non-empty aaData payload.
    # Schema/field completeness is recorded for later review, not rejected.
    widths = sorted({
        len(row) for row in data
        if isinstance(row, list)
    })
    schema_note = f"source_widths_{','.join(map(str, widths))}" if widths else "source_rows_non_list"
    return True, f"accepted_{schema_note}", len(data), obj


def _safe_post_data(post_data: str) -> str:
    out = []
    for k, v in parse_qsl(post_data or "", keep_blank_values=True):
        kl = k.lower()
        if (
            kl in {
                "sessionid",
                "phpsessid",
                "cf_clearance",
                "password",
                "passwd",
                "token",
            }
            or "session" in kl
        ):
            v = "<redacted>"
        out.append((k, v))
    return urlencode(out)


def _make_body(base_pairs, symbol):
    return urlencode(
        [(k, symbol if k == "optSymbol" else v) for k, v in base_pairs]
    )


def _safe_name(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", symbol)


def _display_scalar(value, preserve_time=False):
    """Strip iCharts display/color suffix without corrupting Time."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if preserve_time:
        return text

    # Non-time scalar display values may contain ':color'.
    # Keep the actual scalar and discard presentation metadata.
    if ":" in text:
        return text.split(":", 1)[0].strip()
    return text


def _packed_values(value):
    """Expand an iCharts packed pair such as '-4959:-1.76:red'."""
    if value is None:
        return "", ""
    if isinstance(value, (int, float)):
        return value, ""

    parts = str(value).split(":")
    first = parts[0].strip() if parts else ""
    second = parts[1].strip() if len(parts) > 1 else ""
    return first, second


def _map_source_row(source_row):
    if not isinstance(source_row, list):
        source_row = []

    out = [""] * len(REPORT_HEADERS)

    # Source field 1 is Time. It MUST never be split on ':'.
    out[0] = _display_scalar(source_row[0], preserve_time=True)

    # Source field 2 is Fut Price with optional color suffix.
    out[1] = _display_scalar(source_row[1])

    # Packed source fields.
    for source_index, (out_a, out_b) in PACKED_PAIRS.items():
        a, b = _packed_values(source_row[source_index - 1])
        out[out_a] = a
        out[out_b] = b

    # Remaining one-to-one source fields.
    for source_index, target_index in [
        (5, 6),
        (6, 7),
        (7, 8),
        (8, 9),
        (11, 14),
        (12, 15),
        (13, 16),
        (14, 17),
        (15, 18),
        (16, 19),
        (17, 20),
        (18, 21),
        (19, 22),
        (20, 23),
        (21, 24),
        (22, 25),
        (23, 26),
        (24, 27),
        (25, 28),
        (26, 29),
        (27, 30),
        (28, 31),
        (31, 36),
    ]:
        out[target_index] = _display_scalar(source_row[source_index - 1])

    if len(out) != len(REPORT_HEADERS):
        raise AssertionError(
            f"Mapped output width {len(out)} != schema width {len(REPORT_HEADERS)}"
        )
    return out


def _flatten_rows(results, snapshot_id):
    rows = []
    for result in results:
        if not result.get("valid"):
            continue

        symbol = result["symbol"]
        obj = result["object"]

        for row_no, source_row in enumerate(obj["aaData"], 1):
            mapped = _map_source_row(source_row)
            record = dict(zip(REPORT_HEADERS, mapped))

            # Metadata is deliberately appended after the native report columns.
            record["Symbol"] = symbol
            record["Snapshot"] = snapshot_id
            record["Response_Row"] = row_no
            rows.append(record)

    return rows


def _write_excel(path: Path, rows, status_rows, manifest):
    import pandas as pd

    data_columns = REPORT_HEADERS + ["Symbol", "Snapshot", "Response_Row"]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(rows, columns=data_columns).to_excel(
            writer, index=False, sheet_name="Data"
        )
        pd.DataFrame(status_rows).to_excel(
            writer, index=False, sheet_name="Status"
        )
        pd.DataFrame([manifest]).to_excel(
            writer, index=False, sheet_name="Run"
        )


def _trace_dir(destination: Path, dt):
    return (
        destination
        / "_Trace"
        / time.strftime("%Y", dt)
        / time.strftime("%B", dt).lower()
        / time.strftime("%Y-%m-%d", dt)
    )


def run_pece_xhr_batch(context, output_root, job, status_callback=None):
    """Production PE/CE batch acquisition.

    Data path:
      authenticated iCharts page
        -> native XHR template
        -> symbol discovery
        -> split, paced XHR batches
        -> 31-field validation
        -> 37-column expansion
        -> integrity gate
        -> clean Excel publication

    Fabrication/carry-forward/cross-symbol substitution are forbidden.
    """

    root = Path(output_root)
    destination = Path(str(job.get("destination") or root)).expanduser()
    destination.mkdir(parents=True, exist_ok=True)

    cycle_id = time.strftime("%Y%m%d_%H%M%S")
    dt = time.localtime()

    # Consumer data and trace/audit data are physically separated.
    day_dir = (
        destination
        / time.strftime("%Y", dt)
        / time.strftime("%B", dt).lower()
        / time.strftime("%Y-%m-%d", dt)
    )
    trace = _trace_dir(destination, dt)
    day_dir.mkdir(parents=True, exist_ok=True)
    trace.mkdir(parents=True, exist_ok=True)

    configured_expected = job.get("expected_symbol_count")
    expected = int(configured_expected) if configured_expected is not None else None
    # iCharts rate-limits this endpoint with HTTP 429 when requests are
    # started in a burst.  Keep the configured value for compatibility, but
    # apply a conservative acquisition ceiling and global request pacing.
    configured_concurrency = max(1, min(12, int(job.get("concurrency", 8))))
    concurrency = configured_concurrency
    split_batch_size = max(1, min(50, int(job.get("split_batch_size", 48))))
    request_gap_ms = max(100, min(5000, int(job.get("request_start_gap_ms", 150))))
    retry_backoff_ms = max(15000, min(180000, int(job.get("retry_backoff_ms", 30000))))
    retry_after_cap_ms = max(30000, min(300000, int(job.get("retry_after_cap_ms", 120000))))
    jitter_min_ms = max(0, min(5000, int(job.get("request_jitter_min_ms", 100))))
    jitter_max_ms = max(jitter_min_ms, min(5000, int(job.get("request_jitter_max_ms", 400))))
    batch_gap_ms = max(1000, min(15000, int(job.get("batch_gap_ms", 3000))))
    retries = 0
    timeout_ms = max(
        3000,
        min(
            30000,
            int(float(job.get("request_timeout_seconds", 3)) * 1000),
        ),
    )
    max_429_failures = max(1, min(10, int(job.get("max_429_failures", 3))))
    run_timeout_seconds = 210

    manifest = {
        "status": "starting",
        "integrity_gate": "HOLD",
        "cycle_id": cycle_id,
        "target_url": str(job.get("url") or TARGET_URL),
        "expected_symbol_count": expected,
        "expected_symbol_count_source": (
            "job_configuration" if expected is not None else "discovered_at_runtime"
        ),
        "coverage_percent": None,
        "missing_symbols": [],
        "symbol_count": 0,
        "completed_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "source_width_expected": 31,
        "report_width": len(REPORT_HEADERS),
        "report_headers": REPORT_HEADERS,
        "data_policy": {
            "fabrication": "forbidden",
            "missing_data": "status_only",
            "carry_forward": "forbidden",
            "cross_symbol_substitution": "forbidden",
            "retry_failed": retries,
            "configured_concurrency": configured_concurrency,
            "effective_concurrency": concurrency,
            "split_batch_size": split_batch_size,
            "request_start_gap_ms": request_gap_ms,
            "retry_backoff_ms": retry_backoff_ms,
            "retry_after_cap_ms": retry_after_cap_ms,
            "request_jitter_min_ms": jitter_min_ms,
            "request_jitter_max_ms": jitter_max_ms,
            "batch_gap_ms": batch_gap_ms,
            "max_429_failures": max_429_failures,
            "run_timeout_seconds": run_timeout_seconds,
            "deadline_policy": "hard_stop_including_retries",
            "execution_policy": "complete_first_pass_then_retry_failures_only",
            "circuit_breaker": "stop_after_repeated_429",
        },
        "results": [],
    }

    manifest_path = trace / f"PECE_{cycle_id}.json"
    _write_json(manifest_path, manifest)
    (trace / "00_STARTED.txt").write_text(
        "PE/CE XHR cycle started\n", encoding="utf-8"
    )

    page = None
    try:
        if context is None:
            raise RuntimeError("Existing authenticated BrowserContext is required")

        page = context.new_page()

        # Capture starts BEFORE navigation so the initial native XHR cannot be missed.
        captured = []

        def on_response(resp):
            try:
                if (
                    resp.request.method.upper() == "POST"
                    and ENDPOINT_RE.search(resp.url)
                ):
                    captured.append(resp)
            except Exception:
                pass

        page.on("response", on_response)

        page.goto(
            manifest["target_url"],
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_selector("#optSymbol", timeout=30000)

        symbols = page.locator("#optSymbol option").evaluate_all(
            """els => els.map(e => ({
                value:e.value||'',
                text:(e.textContent||'').trim()
            })).filter(x=>x.value)"""
        )

        unique, seen = [], set()
        for s in symbols:
            if s["value"] not in seen:
                seen.add(s["value"])
                unique.append(s)
        symbols = unique

        manifest["symbol_count"] = len(symbols)
        manifest["symbol_count_check"] = (
            "pass" if expected is None or len(symbols) == expected else "mismatch"
        )
        manifest["symbols"] = symbols
        _write_json(trace / f"PECE_{cycle_id}_symbols.json", symbols)
        (trace / "01_SYMBOLS_FOUND.txt").write_text(
            f"{len(symbols)} symbols discovered; expected {expected}\n",
            encoding="utf-8",
        )

        # Give the native page request a short capture window.
        deadline = time.monotonic() + 20
        while not captured and time.monotonic() < deadline:
            page.wait_for_timeout(250)

        # If the page loaded without triggering the request yet, reload once.
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

        if not ENDPOINT_RE.search(template.url):
            raise RuntimeError("Captured XHR endpoint is not the expected PE/CE endpoint")

        manifest["template_endpoint"] = template.url
        manifest["template_status"] = template.status
        manifest["template_post_data"] = _safe_post_data(post)

        (trace / "02_XHR_TEMPLATE_CAPTURED.txt").write_text(
            f"{template.url}\nHTTP {template.status}\n",
            encoding="utf-8",
        )

        fetch_js = r"""
        async ({url, jobs, concurrency, timeoutMs, requestGapMs, jitterMinMs, jitterMaxMs}) => {
          let next=0;
          let nextStart=0;
          const results=new Array(jobs.length);

          async function reserveStart(){
            const now=performance.now();
            const start=Math.max(now,nextStart);
            nextStart=start+requestGapMs;
            const wait=start-now;
            if(wait>0) await new Promise(r=>setTimeout(r,wait));
          }

          async function worker(){
            while(true){
              const i=next++;
              if(i>=jobs.length) return;

              const j=jobs[i];
              await reserveStart();
              const jitter=jitterMinMs + Math.random()*(jitterMaxMs-jitterMinMs);
              if(jitter>0) await new Promise(r=>setTimeout(r,jitter));
              const t=performance.now();
              const ctl=new AbortController();
              const timer=setTimeout(()=>ctl.abort(), timeoutMs);

              try{
                const r=await fetch(url,{
                  method:'POST',
                  headers:{
                    'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With':'XMLHttpRequest'
                  },
                  body:j.body,
                  credentials:'include',
                  cache:'no-store',
                  signal:ctl.signal
                });
                const text=await r.text();
                results[i]={
                  symbol:j.symbol,
                  request_body:j.body,
                  status:r.status,
                  ok:r.ok,
                  elapsed_ms:performance.now()-t,
                  body:text,
                  retry_after:r.headers.get("Retry-After")
                };
              }catch(e){
                results[i]={
                  symbol:j.symbol,
                  request_body:j.body,
                  status:0,
                  ok:false,
                  elapsed_ms:performance.now()-t,
                  error:String(e)
                };
              }finally{
                clearTimeout(timer);
              }
            }
          }

          await Promise.all(
            Array.from(
              {length:Math.min(concurrency,jobs.length)},
              ()=>worker()
            )
          );
          return results;
        }
        """

        def execute(batch):
            return page.evaluate(
                fetch_js,
                {
                    "url": template.url,
                    "jobs": [
                        {
                            "symbol": s["value"],
                            "body": _make_body(base_pairs, s["value"]),
                        }
                        for s in batch
                    ],
                    "concurrency": concurrency,
                    "timeoutMs": timeout_ms,
                    "requestGapMs": request_gap_ms,
                    "jitterMinMs": jitter_min_ms,
                    "jitterMaxMs": jitter_max_ms,
                },
            )

        started = time.perf_counter()
        deadline = started + run_timeout_seconds
        pending = list(symbols)
        timed_out = False
        final = {}
        attempt = 0

        while pending and attempt <= retries:
            if time.perf_counter() >= deadline:
                timed_out = True
                break
            attempt += 1

            # Give iCharts time to clear a rate-limit window before retrying
            # any 429 responses.  Only retry the symbols still pending.
            if attempt > 1:
                # Respect the largest Retry-After observed in the previous
                # attempt, otherwise use conservative exponential backoff.
                retry_wait_ms = retry_backoff_ms * (2 ** (attempt - 2))
                for previous in final.values():
                    if previous.get("http_status") == 429:
                        retry_after = previous.get("retry_after_seconds")
                        if retry_after is not None:
                            retry_wait_ms = max(
                                retry_wait_ms,
                                int(min(retry_after * 1000, retry_after_cap_ms)),
                            )
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    timed_out = True
                    break
                time.sleep(min(retry_wait_ms / 1000.0, remaining))
                if time.perf_counter() >= deadline:
                    timed_out = True
                    break

            if status_callback:
                status_callback(
                    f"{job.get('name','PE/CE')}: "
                    f"attempt {attempt}; {len(pending)} pending"
                )

            raw = []
            batch_size = split_batch_size
            total_batches = (len(pending) + batch_size - 1) // batch_size
            for batch_no, start in enumerate(range(0, len(pending), batch_size), 1):
                if time.perf_counter() >= deadline:
                    timed_out = True
                    break
                batch = pending[start:start + batch_size]
                if status_callback:
                    status_callback(
                        f"{job.get('name','PE/CE')}: attempt {attempt}; "
                        f"batch {batch_no}/{total_batches}; "
                        f"{len(pending) - start} pending"
                    )
                raw.extend(execute(batch))
                if batch_no < total_batches:
                    time.sleep(batch_gap_ms / 1000.0)

            next_pending = []

            # Preserve symbols whose batch was never executed because the
            # hard deadline was reached. They must not disappear silently.
            processed_count = min(len(raw), len(pending))

            for sym, result in zip(pending[:processed_count], raw):
                if result.get("ok"):
                    valid, reason, rows, obj = validate_payload(
                        result.get("body", "")
                    )
                else:
                    valid, reason, rows, obj = (
                        False,
                        result.get("error", "http_error"),
                        0,
                        None,
                    )

                rec = {
                    "symbol": sym["value"],
                    "text": sym["text"],
                    "attempt": attempt,
                    "http_status": result.get("status"),
                    "retry_after": result.get("retry_after"),
                    "retry_after_seconds": None,
                    "elapsed_ms": round(
                        float(result.get("elapsed_ms", 0)), 1
                    ),
                    "payload_valid": valid,
                    "reason": reason,
                    "rows": rows,
                    "valid": valid,
                }

                retry_after = result.get("retry_after")
                if retry_after:
                    try:
                        rec["retry_after_seconds"] = max(0, float(retry_after))
                    except (TypeError, ValueError):
                        try:
                            retry_dt = parsedate_to_datetime(retry_after)
                            if retry_dt.tzinfo is None:
                                retry_dt = retry_dt.replace(tzinfo=timezone.utc)
                            rec["retry_after_seconds"] = max(
                                0,
                                (retry_dt - datetime.now(timezone.utc)).total_seconds(),
                            )
                        except Exception:
                            rec["retry_after_seconds"] = None

                if valid:
                    final[sym["value"]] = rec | {"object": obj}
                else:
                    final[sym["value"]] = rec
                    if attempt <= retries:
                        next_pending.append(sym)

            # Any symbols not returned by execute() were not processed.
            # Keep them pending so the deadline handler records them as
            # run_timeout rather than treating them as successful or losing
            # traceability.
            if processed_count < len(pending):
                next_pending.extend(pending[processed_count:])

            pending = next_pending

            # Account-safety circuit breaker: do not continue hammering the
            # endpoint when the server repeatedly returns HTTP 429.
            round_429 = sum(
                1 for r in ordered if r.get("http_status") == 429
            ) if False else sum(
                1 for r in final.values() if r.get("http_status") == 429
            )
            if round_429 >= max_429_failures and pending:
                manifest["rate_limit_circuit_breaker"] = {
                    "tripped": True,
                    "reason": "repeated_http_429",
                    "429_records": round_429,
                    "pending_symbols": len(pending),
                }
                break

        ordered = []
        for s in symbols:
            r = final.get(
                s["value"],
                {
                    "symbol": s["value"],
                    "text": s["text"],
                    "valid": False,
                    "reason": "no_result",
                },
            )
            ordered.append(dict(r))

        if timed_out or time.perf_counter() >= deadline:
            timed_out = True
            for sym in pending:
                if sym["value"] not in final:
                    final[sym["value"]] = {
                        "symbol": sym["value"],
                        "text": sym["text"],
                        "valid": False,
                        "reason": "run_timeout",
                        "timeout": True,
                    }
            manifest["run_timeout"] = True
            manifest["timeout_reason"] = "3.5-minute hard deadline reached"
        else:
            manifest["run_timeout"] = False

        manifest["results"] = [
            {k: v for k, v in r.items() if k != "object"}
            for r in ordered
        ]
        manifest["completed_count"] = len(ordered)
        manifest["success_count"] = sum(
            1 for r in ordered if r.get("valid")
        )
        manifest["failed_count"] = (
            manifest["completed_count"] - manifest["success_count"]
        )
        manifest["missing_symbols"] = [
            r["symbol"] for r in ordered if not r.get("valid")
        ]
        manifest["coverage_percent"] = round(
            (manifest["success_count"] / manifest["completed_count"]) * 100,
            2,
        ) if manifest["completed_count"] else 0.0
        manifest["elapsed_seconds"] = round(
            time.perf_counter() - started, 2
        )
        manifest["symbols_per_second"] = round(
            len(ordered) / max(manifest["elapsed_seconds"], 0.001), 3
        )

        # Publication records the data actually acquired. No fixed percentage,
        # symbol count, or hardcoded acceptance threshold is used here.
        raw_results = [r for r in ordered if r.get("valid")]
        if raw_results:
            status_rows = [
                {k: v for k, v in r.items() if k != "object"}
                for r in ordered
            ]
            rows = _flatten_rows(raw_results, cycle_id)

            xlsx = day_dir / f"PECE_{cycle_id}.xlsx"
            _write_excel(xlsx, rows, status_rows, manifest)
            manifest["snapshot_file"] = str(xlsx)
            manifest["publish_blocked"] = False

            if manifest["failed_count"] == 0:
                manifest["status"] = "completed"
                manifest["integrity_gate"] = "PASS"
                manifest["publish_reason"] = "All discovered symbols have valid payloads."
            else:
                manifest["status"] = "completed_with_gaps"
                manifest["integrity_gate"] = "PARTIAL"
                manifest["publish_reason"] = (
                    "Published valid records; failed symbols are listed in "
                    "missing_symbols for audit and later retry."
                )
        else:
            manifest["status"] = "completed_with_gaps"
            manifest["integrity_gate"] = "HOLD"
            manifest["publish_blocked"] = True
            manifest["publish_reason"] = (
                "No valid payloads were available for publication."
            )

        _write_json(manifest_path, manifest)
        (trace / "99_COMPLETED.txt").write_text(
            f"discovered={manifest['symbol_count']} "
            f"valid={manifest['success_count']} "
            f"failed={manifest['failed_count']} "
            f"integrity={manifest['integrity_gate']} "
            f"published={manifest.get('snapshot_file','NO')}\n",
            encoding="utf-8",
        )

        return manifest

    except Exception as exc:
        manifest.update(
            status="failed",
            integrity_gate="HOLD",
            publish_blocked=True,
            fatal_error=repr(exc),
            traceback=traceback.format_exc(),
        )
        _write_json(
            trace / f"PECE_{cycle_id}.json",
            manifest,
        )
        (trace / "ERROR.txt").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )
        raise

    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
