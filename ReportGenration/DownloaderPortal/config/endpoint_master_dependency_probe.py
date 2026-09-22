"""
Fix 32 — Endpoint Master Dependency Probe.

Uses the existing authenticated Playwright context and the endpoint definitions
stored in config/OptionChain_Endpoint_Master.json.

This is TEST ONLY. It does not create XLSX, start the scheduler, or change
production jobs.

Purpose:
1. Call getTopRightDetails for each symbol.
2. Call OptionChainTable_Beta_v19 using the expiry returned by step 1.
3. Initially leave optStrike as undefined to determine whether the server
   resolves it itself.
4. Report server_symbol, expiry, futures, ATM, optStrike, rows and strikes.

This directly tests the unresolved dependency chain recorded in the master.
"""

from __future__ import annotations
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import urlencode

TOP_RIGHT = "https://www.icharts.in/opt/hcharts/stx8req/php/getTopRightDetails.php"
TABLE = "https://www.icharts.in/opt/OptionChainTable_Beta_v19.php"

def _parse_top_right(data):
    futures = data.get("futures") if isinstance(data, dict) else None
    if isinstance(futures, list):
        return {
            "symbol": str(futures[0]) if len(futures) > 0 else "",
            "expiry": str(futures[1]) if len(futures) > 1 else "",
            "futures": str(futures[2]) if len(futures) > 2 else "",
            "change": str(futures[3]) if len(futures) > 3 else "",
            "change_percent": str(futures[4]) if len(futures) > 4 else "",
            "date": str(futures[5]) if len(futures) > 5 else "",
        }
    return {}

async def _one(context, symbol, timeout_seconds=30):
    started = time.perf_counter()
    page = await context.new_page()
    try:
        top_payload = {
            "optSymbol": symbol,
            "optExpDate": "undefined",
            "monthlyExpDate": "undefined",
            "Presentday": "undefined",
            "Prevday": "undefined",
            "rdDataType": "latest",
            "txtDate": "undefined",
            "defaultDate": "undefined",
            "e": "1",
        }
        tr = await page.request.post(
            TOP_RIGHT,
            data=urlencode(top_payload),
            timeout=timeout_seconds * 1000,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        )
        tr_text = await tr.text()
        tr_json = json.loads(tr_text)
        details = _parse_top_right(tr_json)
        expiry = details.get("expiry", "")

        table_payload = {
            "optSymbol": symbol,
            "buttontype": "Lots_btn",
            "optExpDate": expiry or "undefined",
            "optExpDate_hist": "undefined",
            "striketype": "mainstrikes",
            "txtDate": "undefined",
            "defaultDate": "undefined",
            "atmstrikesnumber": "7",
            "atmstrikesnumberfixed": "3",
            "optStrike": "undefined",
            "dType": "latest",
        }
        tb = await page.request.post(
            TABLE,
            data=urlencode(table_payload),
            timeout=timeout_seconds * 1000,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        )
        tb_text = await tb.text()
        data = json.loads(tb_text)

        rows = data.get("aaData") or []
        strikes = [
            str(row[32]) for row in rows
            if isinstance(row, list) and len(row) > 32
        ]

        server_symbol = str(data.get("symbol_1", ""))
        result = {
            "symbol": symbol,
            "top_right_http": tr.status,
            "table_http": tb.status,
            "top_right_symbol": details.get("symbol", ""),
            "resolved_expiry": expiry,
            "futures": details.get("futures", ""),
            "table_server_symbol": server_symbol,
            "strikePriceATM": str(data.get("strikePriceATM", "")),
            "optStrike": str(data.get("optStrike", "")),
            "aaData_count": len(rows) if isinstance(rows, list) else 0,
            "returned_strikes": strikes,
            "symbol_match": server_symbol.upper() == symbol.upper(),
            "seven_rows": len(rows) == 7,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "pass": (
                tr.status == 200 and tb.status == 200 and
                server_symbol.upper() == symbol.upper() and
                bool(expiry) and len(rows) == 7
            ),
            "error": "",
        }
        return result
    except Exception as exc:
        return {
            "symbol": symbol,
            "pass": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": str(exc),
        }
    finally:
        await page.close()

async def run_endpoint_master_dependency_probe(context, symbols, timeout_seconds=30, concurrency=5):
    started = time.perf_counter()
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async def worker(symbol):
        async with sem:
            return await _one(context, symbol, timeout_seconds)

    results = await asyncio.gather(*(worker(s) for s in symbols))
    passed = sum(bool(r.get("pass")) for r in results)
    return {
        "test": "Option Chain Endpoint Master dependency probe",
        "requested": len(symbols),
        "passed": passed,
        "failed": len(symbols) - passed,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "results": results,
    }
