from __future__ import annotations

import asyncio
import json
import time
from typing import Any


OPTIONCHAIN_ENDPOINT = "OptionChainTable_Beta_v19.php"
SYMBOL_SELECTOR = 'select[name="optSymbol"]'


async def _probe_symbol(context, symbol: str, timeout_ms: int = 30000) -> dict[str, Any]:
    page = await context.new_page()
    started = time.perf_counter()
    result: dict[str, Any] = {
        "symbol": symbol,
        "status": "FAILED",
        "http_status": None,
        "elapsed_ms": None,
        "response_url": None,
        "response_content_type": None,
        "response_bytes": 0,
        "table_rows": 0,
        "table_columns": 0,
        "error": "",
    }

    try:
        await page.goto(
            "https://www.icharts.in/opt/OptionChain.php",
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
        await page.wait_for_timeout(1200)

        selector = page.locator(SYMBOL_SELECTOR)
        if await selector.count() == 0:
            raise RuntimeError("Option Chain symbol selector was not found.")

        # Confirm the requested symbol exists before changing the page.
        option_values = await selector.locator("option").evaluate_all(
            "els => els.map(e => e.value)"
        )
        if symbol not in option_values:
            raise RuntimeError(f"Symbol {symbol} is not present in the live selector.")

        async with page.expect_response(
            lambda r: (
                OPTIONCHAIN_ENDPOINT in r.url
                and r.request.method.upper() == "POST"
            ),
            timeout=timeout_ms,
        ) as response_info:
            await selector.select_option(symbol)

        response = await response_info.value
        body = await response.body()

        result["http_status"] = response.status
        result["response_url"] = response.url
        result["response_content_type"] = response.headers.get("content-type", "")
        result["response_bytes"] = len(body)

        await page.wait_for_timeout(500)

        # The main Option Chain table is the first table with a substantial
        # number of headers. Do not persist the response or create a report.
        tables = page.locator("table")
        best = None
        for i in range(min(await tables.count(), 10)):
            table = tables.nth(i)
            headers = await table.locator("th").all_text_contents()
            headers = [h.strip() for h in headers if h.strip()]
            rows = await table.locator("tbody tr").count()
            if len(headers) >= 40:
                best = (len(headers), rows)
                break

        if best:
            result["table_columns"] = best[0]
            result["table_rows"] = best[1]

        result["status"] = "PASS" if response.ok and result["table_columns"] >= 40 else "FAILED"
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        await page.close()

    return result


async def run_parallel_probe(context, symbols: list[str], timeout_ms: int = 30000) -> dict[str, Any]:
    symbols = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if not symbols:
        raise ValueError("At least one symbol is required.")

    # This is intentionally a bounded probe, not the production scheduler.
    cycle_started = time.perf_counter()
    results = await asyncio.gather(
        *[_probe_symbol(context, symbol, timeout_ms) for symbol in symbols],
        return_exceptions=False,
    )
    elapsed_ms = round((time.perf_counter() - cycle_started) * 1000, 1)

    return {
        "test": "Option Chain controlled parallel browser probe",
        "symbols": symbols,
        "requested": len(symbols),
        "passed": sum(r["status"] == "PASS" for r in results),
        "failed": sum(r["status"] != "PASS" for r in results),
        "elapsed_ms": elapsed_ms,
        "results": results,
        "production_scheduler_activated": False,
        "production_output_written": False,
    }
