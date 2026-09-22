"""
Fix 36 — Option Chain Default-Scope Probe.

User-approved behavior:
- Do NOT impose a strike-count cap in our request.
- Let iCharts apply the authenticated page/default strike selection.
- We only inspect what the server actually returns.
- The browser's current/default selection is not rewritten.

The proven runtime.dynamic_params_probe implementation is used first to obtain
symbol-specific expiry. We then call OptionChainTable_Beta_v19.php with the
symbol and resolved expiry, while deliberately omitting:
    atmstrikesnumber
    atmstrikesnumberfixed
    optStrike
    strikePriceATM
from the request.

This is a TEST ONLY probe. No scheduler, XLSX, or production output.
"""

from __future__ import annotations

import asyncio
import json
import time
from urllib.parse import urlencode

from runtime.dynamic_params_probe import run_dynamic_params_probe

TABLE = "https://www.icharts.in/opt/OptionChainTable_Beta_v19.php"


def _extract_expiry(candidate_fields: dict) -> str:
    if not isinstance(candidate_fields, dict):
        return ""
    # Known successful structure from the existing probe:
    # futures[1] = expiry.
    for key in ("futures[1]", "expiry", "optExpDate"):
        value = candidate_fields.get(key)
        if value:
            return str(value)
    # Be tolerant if the working probe nests candidate fields.
    futures = candidate_fields.get("futures")
    if isinstance(futures, (list, tuple)) and len(futures) > 1:
        return str(futures[1])
    return ""


async def _table_request(context, symbol: str, expiry: str, timeout_seconds: int):
    started = time.perf_counter()
    page = await context.new_page()
    try:
        # Deliberately omit strike-count/strike parameters.
        # iCharts should apply its own authenticated/default selection.
        payload = {
            "optSymbol": symbol,
            "optExpDate": expiry,
            "optExpDate_hist": "undefined",
            "striketype": "mainstrikes",
            "txtDate": "undefined",
            "defaultDate": "undefined",
            "dType": "latest",
            "buttontype": "Lots_btn",
        }

        response = await page.request.post(
            TABLE,
            data=urlencode(payload),
            timeout=timeout_seconds * 1000,
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded; charset=UTF-8"
            },
        )

        body = await response.text()
        result = {
            "symbol": symbol,
            "table_http": response.status,
            "server_symbol": "",
            "strikePriceATM": "",
            "optStrike": "",
            "aaData_count": 0,
            "aaData_row_length": 0,
            "returned_strikes": [],
            "json_valid": False,
            "pass": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": "",
        }

        try:
            data = json.loads(body)
        except Exception as exc:
            result["error"] = f"Table JSON parse error: {exc}; body={body[:300]!r}"
            return result

        if not isinstance(data, dict):
            result["error"] = "Table JSON root is not an object."
            return result

        result["json_valid"] = True
        result["server_symbol"] = str(data.get("symbol_1", ""))
        result["strikePriceATM"] = str(data.get("strikePriceATM", ""))
        result["optStrike"] = str(data.get("optStrike", ""))

        rows = data.get("aaData") or []
        if isinstance(rows, list):
            result["aaData_count"] = len(rows)
            if rows and isinstance(rows[0], list):
                result["aaData_row_length"] = len(rows[0])
            result["returned_strikes"] = [
                str(row[32])
                for row in rows
                if isinstance(row, list) and len(row) > 32
            ]

        result["pass"] = (
            response.status == 200
            and result["json_valid"]
            and result["server_symbol"].upper() == symbol.upper()
            and result["aaData_count"] > 0
        )
        return result
    except Exception as exc:
        return {
            "symbol": symbol,
            "table_http": None,
            "pass": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": str(exc),
        }
    finally:
        await page.close()


async def _one(context, symbol: str, timeout_seconds: int):
    started = time.perf_counter()

    dynamic = await run_dynamic_params_probe(
        context=context,
        symbols=[symbol],
        timeout_seconds=min(15, timeout_seconds),
        concurrency=1,
    )

    if not dynamic.get("results"):
        return {
            "symbol": symbol,
            "pass": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": "Dynamic parameter probe returned no result.",
        }

    d = dynamic["results"][0]
    candidate = d.get("candidate_fields") or {}
    expiry = _extract_expiry(candidate)

    if not expiry:
        return {
            "symbol": symbol,
            "dynamic_http": d.get("http_status"),
            "expiry": "",
            "pass": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": "Could not extract expiry from the proven Dynamic Parameters response.",
            "candidate_fields": candidate,
        }

    table = await _table_request(context, symbol, expiry, timeout_seconds)

    return {
        "symbol": symbol,
        "dynamic_http": d.get("http_status"),
        "expiry": expiry,
        "table_http": table.get("table_http"),
        "server_symbol": table.get("server_symbol"),
        "strikePriceATM": table.get("strikePriceATM"),
        "optStrike": table.get("optStrike"),
        "aaData_count": table.get("aaData_count", 0),
        "aaData_row_length": table.get("aaData_row_length", 0),
        "returned_strikes": table.get("returned_strikes", []),
        "pass": table.get("pass", False),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "error": table.get("error", ""),
    }


async def run_optionchain_default_scope_probe(
    context, symbols, timeout_seconds=30, concurrency=5
):
    started = time.perf_counter()
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async def worker(symbol):
        async with sem:
            return await _one(context, symbol, timeout_seconds)

    results = await asyncio.gather(*(worker(s) for s in symbols))
    passed = sum(bool(r.get("pass")) for r in results)

    return {
        "test": "Option Chain Default-Scope Probe",
        "scope_policy": "No client-side strike cap; iCharts default/authenticated scope",
        "requested": len(symbols),
        "passed": passed,
        "failed": len(symbols) - passed,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "results": results,
    }
