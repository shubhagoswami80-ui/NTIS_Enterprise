from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any

ENDPOINT = "https://www.icharts.in/opt/OptionChainTable_Beta_v19.php"

OPTION_CHAIN_HEADERS = [
    "Calls","Puts","Buildup","Trend","Time","Vega","Theta","Gamma","Delta","IV Chg%","OI Chg%","OI Chg","OI","Volume Chg %","Volume Chg","Volume","OH/OL","Open","High","Low","Close Price Chg %","Close Price Chg","Prev Close Price","Close Price","LTP Chg %","LTP Chg","LTP","VWAP","Bid","Strike Price","PE-CE OI","PE-CE OI Chg","VWAP","LTP","LTP Chg","LTP Chg %","Close Price","Prev Close Price","Close Price Chg","Close Price Chg %","Open","High","Low","OH/OL","Volume","Volume Chg","Volume Chg %","OI Chg","OI Chg%","IV","IV Chg%","Delta","Gamma","Theta","Vega","PCR-OI","PCR-OI Chg","PCR-Vol","Time","Trend","Buildup"
]

def extract_mapped_rows(result: dict) -> list[dict]:
    aa = result.get("aaData_first_rows", [])
    mapped = []
    for row_no, row in enumerate(aa, start=1):
        if not isinstance(row, list) or len(row) < 64:
            continue
        vals = row[3:64]
        mapped.append({"row_number": row_no, **{OPTION_CHAIN_HEADERS[i]: vals[i] for i in range(61)}})
    return mapped



def _inspect_payload(body: bytes, requested_symbol: str) -> dict[str, Any]:
    result = {
        "json_valid": False,
        "top_level_type": "",
        "top_level_keys": [],
        "records_detected": 0,
        "reported_total_records": None,
        "aaData_count": 0,
        "nonempty_string_values": 0,
        "symbol_match_detected": False,
        "payload_structure": "UNKNOWN",
        "data_state": "UNKNOWN",
        "aaData_row_type": "",
        "aaData_row_length": None,
        "aaData_first_row_preview": [],
        "aaData_first_rows": [],
    }
    text = body.decode("utf-8", errors="replace")
    try:
        obj = json.loads(text)
    except Exception:
        return result

    result["json_valid"] = True
    result["top_level_type"] = type(obj).__name__

    if isinstance(obj, dict):
        result["top_level_keys"] = [str(k) for k in list(obj.keys())[:30]]

        for key in ("iTotalRecords", "iTotalDisplayRecords"):
            if key in obj:
                try:
                    result["reported_total_records"] = int(obj[key])
                    break
                except (TypeError, ValueError):
                    pass

        aa = obj.get("aaData")
        if isinstance(aa, list):
            result["aaData_count"] = len(aa)
            result["records_detected"] = len(aa)
            if aa:
                first = aa[0]
                result["aaData_row_type"] = type(first).__name__
                if isinstance(first, (list, tuple)):
                    result["aaData_row_length"] = len(first)
                    result["aaData_first_row_preview"] = [f"{i}: {str(x)[:300]}" for i, x in enumerate(first)]
                    result["aaData_first_rows"] = aa
                elif isinstance(first, dict):
                    result["aaData_row_length"] = len(first)
                    result["aaData_first_row_preview"] = {str(k): str(v)[:120] for k, v in list(first.items())[:12]}
                else:
                    result["aaData_row_length"] = None
                    result["aaData_first_row_preview"] = [str(first)[:500]]

        if result["reported_total_records"] == 0 and result["aaData_count"] == 0:
            result["data_state"] = "NO_OPTION_DATA"
        elif result["aaData_count"] > 0:
            result["data_state"] = "OPTION_DATA_PRESENT"

    def walk(v: Any, depth: int = 0):
        if depth > 8:
            return
        if isinstance(v, dict):
            for k, value in v.items():
                if isinstance(value, str):
                    if value.strip():
                        result["nonempty_string_values"] += 1
                    if requested_symbol.upper() in value.upper():
                        result["symbol_match_detected"] = True
                walk(value, depth + 1)
        elif isinstance(v, list):
            for item in v[:50]:
                walk(item, depth + 1)
        elif isinstance(v, str):
            if v.strip():
                result["nonempty_string_values"] += 1
            if requested_symbol.upper() in v.upper():
                result["symbol_match_detected"] = True

    walk(obj)

    if result["data_state"] == "OPTION_DATA_PRESENT":
        result["payload_structure"] = "OPTION_DATA"
    elif result["data_state"] == "NO_OPTION_DATA":
        result["payload_structure"] = "NO_OPTION_DATA"
    elif result["nonempty_string_values"] > 0:
        result["payload_structure"] = "NONEMPTY_JSON"
    else:
        result["payload_structure"] = "EMPTY_JSON"

    return result


async def _request(
    api,
    symbol: str,
    timeout_ms: int,
    common_params: dict[str, str],
    max_retries: int,
    backoff_initial_ms: int,
    backoff_max_ms: int,
    request_gap_ms: int,
    jitter_ms: int,
):
    started = time.perf_counter()
    params = dict(common_params)
    params["optSymbol"] = symbol

    result = {
        "symbol": symbol,
        "status": "FAILED",
        "http_status": None,
        "attempts": 0,
        "elapsed_ms": None,
        "response_url": ENDPOINT,
        "response_content_type": "",
        "response_bytes": 0,
        "retry_after_ms": None,
        "json_valid": False,
        "top_level_type": "",
        "top_level_keys": [],
        "records_detected": 0,
        "reported_total_records": None,
        "aaData_count": 0,
        "symbol_match_detected": False,
        "payload_structure": "UNKNOWN",
        "data_state": "UNKNOWN",
        "mapped_rows": [],
        "error": "",
    }

    try:
        # Small initial spacing between workers. This is deliberately modest;
        # 429 handling remains the primary protection.
        if request_gap_ms:
            await asyncio.sleep(request_gap_ms / 1000.0 + random.uniform(0, jitter_ms) / 1000.0)

        for attempt in range(max_retries + 1):
            result["attempts"] = attempt + 1

            try:
                response = await api.post(
                    ENDPOINT,
                    form=params,
                    headers={
                        "Referer": "https://www.icharts.in/opt/OptionChain.php",
                        "Origin": "https://www.icharts.in",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    timeout=timeout_ms,
                )
                body = await response.body()
                result["http_status"] = response.status
                result["response_content_type"] = response.headers.get("content-type", "")
                result["response_bytes"] = len(body)

                if response.status == 429 and attempt < max_retries:
                    retry_after = response.headers.get("retry-after")
                    delay_ms = None
                    if retry_after:
                        try:
                            delay_ms = max(1000, int(float(retry_after) * 1000))
                        except ValueError:
                            delay_ms = None
                    if delay_ms is None:
                        delay_ms = min(
                            backoff_max_ms,
                            backoff_initial_ms * (2 ** attempt),
                        )
                    delay_ms += random.randint(0, max(0, jitter_ms))
                    result["retry_after_ms"] = delay_ms
                    await asyncio.sleep(delay_ms / 1000.0)
                    continue

                if response.status != 200:
                    result["error"] = f"HTTP {response.status}"
                    return result

                inspection = _inspect_payload(body, symbol)
                result.update(inspection)
                result["mapped_rows"] = extract_mapped_rows(result)

                if not inspection["json_valid"]:
                    result["error"] = "HTTP 200 but response is not valid JSON"
                    return result

                if inspection["payload_structure"] == "EMPTY_JSON":
                    result["error"] = "HTTP 200 but JSON payload is empty"
                    return result

                # NO_OPTION_DATA is a valid transport result, not a request failure.
                if inspection["payload_structure"] == "NO_OPTION_DATA":
                    result["status"] = "NO_DATA"
                else:
                    result["status"] = "PASS"
                return result

            except Exception as exc:
                if attempt >= max_retries:
                    result["error"] = str(exc)
                    return result
                delay_ms = min(
                    backoff_max_ms,
                    backoff_initial_ms * (2 ** attempt),
                ) + random.randint(0, max(0, jitter_ms))
                await asyncio.sleep(delay_ms / 1000.0)

    finally:
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)

    return result


async def run_direct_post_probe(
    context,
    symbols,
    timeout_seconds=30,
    concurrency=5,
    common_params=None,
    max_retries=2,
    backoff_initial_ms=1500,
    backoff_max_ms=15000,
    request_gap_ms=100,
    jitter_ms=100,
):
    symbols = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if not symbols:
        raise ValueError("At least one symbol is required.")
    if not context:
        raise ValueError("Authenticated Playwright browser context is required.")

    params = common_params or {
        "buttontype": "Lots_btn",
        "optExpDate": "29SEP26",
        "optExpDate_hist": "undefined",
        "striketype": "mainstrikes",
        "txtDate": "undefined",
        "defaultDate": "2026-09-18",
        "atmstrikesnumber": "7",
        "atmstrikesnumberfixed": "3",
        "optStrike": "13250",
        "dType": "latest",
    }

    api = context.request
    semaphore = asyncio.Semaphore(max(1, int(concurrency)))
    started = time.perf_counter()

    async def worker(symbol):
        async with semaphore:
            return await _request(
                api,
                symbol,
                int(timeout_seconds * 1000),
                params,
                int(max_retries),
                int(backoff_initial_ms),
                int(backoff_max_ms),
                int(request_gap_ms),
                int(jitter_ms),
            )

    results = await asyncio.gather(*(worker(s) for s in symbols))
    elapsed = round((time.perf_counter() - started) * 1000, 1)

    return {
        "test": "Option Chain direct POST payload + 429 backoff validation",
        "endpoint": ENDPOINT,
        "symbols": symbols,
        "requested": len(symbols),
        "concurrency": int(concurrency),
        "passed": sum(x["status"] == "PASS" for x in results),
        "no_data": sum(x["status"] == "NO_DATA" for x in results),
        "failed": sum(x["status"] == "FAILED" for x in results),
        "elapsed_ms": elapsed,
        "max_retries": int(max_retries),
        "backoff_initial_ms": int(backoff_initial_ms),
        "backoff_max_ms": int(backoff_max_ms),
        "request_gap_ms": int(request_gap_ms),
        "jitter_ms": int(jitter_ms),
        "results": results,
        "production_scheduler_activated": False,
        "production_output_written": False,
        "note": "Probe only. Response bodies are inspected in memory and not persisted.",
    }
