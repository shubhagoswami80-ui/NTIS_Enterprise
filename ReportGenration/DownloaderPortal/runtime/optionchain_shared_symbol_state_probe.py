from __future__ import annotations

import asyncio
import time
from urllib.parse import urlencode

from playwright.async_api import BrowserContext


OPTION_CHAIN_URL = "https://www.icharts.in/opt/OptionChain.php"


async def _inspect_symbol(context: BrowserContext, symbol: str, timeout_seconds: int) -> dict:
    started = time.perf_counter()
    page = await context.new_page()
    try:
        url = OPTION_CHAIN_URL + "?" + urlencode({"optSymbol": symbol})
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
        # Allow the authenticated page JavaScript to populate the controls/table.
        await page.wait_for_timeout(2000)

        data = await page.evaluate(
            """() => {
                const value = (selector) => {
                    const e = document.querySelector(selector);
                    return e ? String(e.value ?? '').trim() : '';
                };
                const options = (selector) => Array.from(
                    document.querySelectorAll(selector + ' option')
                ).map(e => ({
                    value: String(e.value ?? '').trim(),
                    text: String(e.textContent ?? '').trim(),
                    selected: !!e.selected
                }));

                let main = null;
                for (const table of document.querySelectorAll('table')) {
                    const headers = Array.from(
                        table.querySelectorAll('thead th, thead td')
                    ).map(e => e.textContent.trim());
                    const rows = Array.from(table.querySelectorAll('tbody tr'))
                        .map(r => Array.from(r.querySelectorAll('td'))
                            .map(e => e.textContent.trim()));
                    if (headers.length >= 50 && rows.length > 0) {
                        main = {headers, rows};
                        break;
                    }
                }

                return {
                    title: document.title,
                    final_url: location.href,
                    selected_symbol: value('#optSymbol'),
                    selected_expiry: value('#optExpDate'),
                    strikePriceATM: value('#strikePriceATM'),
                    centralStrike: value('#centralStrike'),
                    optStrike: value('#optStrike'),
                    strike_options: options('#optStrike'),
                    row_count: main ? main.rows.length : 0,
                    column_count: main ? main.headers.length : 0,
                    first_row: main && main.rows.length ? main.rows[0] : []
                };
            }"""
        )

        data["requested_symbol"] = symbol
        data["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        data["symbol_match"] = (
            str(data.get("selected_symbol", "")).upper() == symbol.upper()
        )
        data["strike_state_present"] = all(
            str(data.get(k, "")).strip()
            for k in ("strikePriceATM", "centralStrike", "optStrike")
        )
        data["seven_rows"] = data.get("row_count") == 7
        data["sixty_one_columns"] = data.get("column_count") == 61
        data["pass"] = all(
            (
                data["symbol_match"],
                data["strike_state_present"],
                data["seven_rows"],
                data["sixty_one_columns"],
            )
        )
        return data
    except Exception as exc:
        return {
            "requested_symbol": symbol,
            "pass": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": str(exc),
        }
    finally:
        await page.close()


async def run_shared_symbol_state_probe(
    context: BrowserContext,
    symbols: list[str],
    timeout_seconds: int = 30,
    concurrency: int = 5,
) -> dict:
    started = time.perf_counter()
    semaphore = asyncio.Semaphore(max(1, min(concurrency, len(symbols))))

    async def worker(symbol: str):
        async with semaphore:
            return await _inspect_symbol(context, symbol, timeout_seconds)

    results = await asyncio.gather(*(worker(s) for s in symbols))
    passed = sum(bool(r.get("pass")) for r in results)
    failed = len(results) - passed

    return {
        "test": "Option Chain shared-browser symbol-state probe",
        "requested": len(results),
        "passed": passed,
        "failed": failed,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "results": results,
    }
