"""
Fix 29 — shared Chromium Option Chain symbol-state probe.

TEST ONLY. Reuses the existing Chromium instance owned by Downloader Portal.
It never launches another persistent context against the same profile.

Strategy:
1. Connect over CDP to the existing Chromium, if the portal exposes a CDP endpoint.
2. Otherwise connect through the portal's browser manager if available.
3. Create temporary pages in the existing authenticated context.
4. Test direct URL initialization per symbol.
5. Close only temporary pages.

Environment:
DOWNLOADER_PORTAL_CDP_URL
    Optional, e.g. http://127.0.0.1:9222
DOWNLOADER_PORTAL_BROWSER_URL
    Optional alternative name.

The portal must expose CDP for this probe. If it does not, the probe exits
with a clear instruction rather than attempting to launch the locked profile.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from urllib.parse import urlencode

from playwright.async_api import async_playwright, Error as PlaywrightError

OPTION_CHAIN = "https://www.icharts.in/opt/OptionChain.php"
DEFAULT_SYMBOLS = ["DIXON", "RELIANCE", "INFY", "TCS", "HDFCBANK"]


def cdp_url() -> str:
    return (
        os.getenv("DOWNLOADER_PORTAL_CDP_URL", "").strip()
        or os.getenv("DOWNLOADER_PORTAL_BROWSER_URL", "").strip()
    )


async def inspect(page, requested: str) -> dict:
    started = time.perf_counter()
    await page.goto(
        OPTION_CHAIN + "?" + urlencode({"optSymbol": requested}),
        wait_until="domcontentloaded",
        timeout=45000,
    )
    await page.wait_for_timeout(2500)

    data = await page.evaluate(
        """() => {
            const val = (sel) => {
                const e = document.querySelector(sel);
                return e ? String(e.value ?? '') : '';
            };
            const opts = (sel) => Array.from(document.querySelectorAll(sel + ' option'))
                .map(o => ({value:String(o.value ?? ''), text:String(o.textContent ?? '').trim()}));

            let main = null;
            for (const t of document.querySelectorAll('table')) {
                const headers = Array.from(
                    t.querySelectorAll('thead th, thead td')
                ).map(x => x.textContent.trim());
                const rows = Array.from(t.querySelectorAll('tbody tr'));
                if (headers.length >= 50 && rows.length >= 1) {
                    main = {
                        headers,
                        rows: rows.map(r =>
                            Array.from(r.querySelectorAll('td'))
                                .map(x => x.textContent.trim())
                        )
                    };
                    break;
                }
            }

            return {
                title: document.title,
                final_url: location.href,
                selected_symbol: val('#optSymbol'),
                selected_expiry: val('#optExpDate'),
                strikePriceATM: val('#strikePriceATM'),
                centralStrike: val('#centralStrike'),
                optStrike: val('#optStrike'),
                strike_options: opts('#optStrike'),
                rows: main ? main.rows.length : 0,
                column_count: main ? main.headers.length : 0,
                first_row: main && main.rows.length ? main.rows[0] : []
            };
        }"""
    )

    data.update({
        "requested_symbol": requested,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "symbol_match": str(data.get("selected_symbol", "")).upper()
            == requested.upper(),
        "strike_state_present": all(
            str(data.get(k, "")).strip()
            for k in ("strikePriceATM", "centralStrike", "optStrike")
        ),
        "seven_rows": data.get("rows") == 7,
        "sixty_one_columns": data.get("column_count") == 61,
    })
    return data


async def main():
    symbols = sys.argv[1:] or DEFAULT_SYMBOLS
    endpoint = cdp_url()

    if not endpoint:
        print("ERROR: No CDP endpoint supplied.")
        print()
        print("The existing Downloader Portal owns the persistent browser profile.")
        print("This probe deliberately refuses to launch another Chromium instance.")
        print()
        print("Set the browser's CDP endpoint in the portal configuration/runtime")
        print("or export:")
        print('$env:DOWNLOADER_PORTAL_CDP_URL="http://127.0.0.1:<CDP_PORT>"')
        print()
        print("Then rerun this probe.")
        raise SystemExit(2)

    print("Option Chain Shared-Browser Symbol-State Probe")
    print(f"CDP: {endpoint}")
    print(f"Symbols: {', '.join(symbols)}")
    print("TEST ONLY: no scheduler, no XLSX, no production output.")
    print()

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(endpoint)
        except Exception as exc:
            print(f"ERROR: Could not connect to existing Chromium over CDP: {exc}")
            raise SystemExit(3)

        contexts = browser.contexts
        if not contexts:
            print("ERROR: Connected to Chromium, but no browser context is available.")
            raise SystemExit(4)

        context = contexts[0]
        results = []

        try:
            for symbol in symbols:
                page = await context.new_page()
                try:
                    result = await inspect(page, symbol)
                    results.append(result)
                    print(json.dumps({
                        "symbol": symbol,
                        "selected_symbol": result["selected_symbol"],
                        "expiry": result["selected_expiry"],
                        "strikePriceATM": result["strikePriceATM"],
                        "centralStrike": result["centralStrike"],
                        "optStrike": result["optStrike"],
                        "strike_options": len(result["strike_options"]),
                        "rows": result["rows"],
                        "columns": result["column_count"],
                        "symbol_match": result["symbol_match"],
                        "elapsed_ms": result["elapsed_ms"],
                    }, ensure_ascii=False))
                except Exception as exc:
                    results.append({
                        "requested_symbol": symbol,
                        "error": str(exc),
                        "symbol_match": False,
                    })
                    print(json.dumps({
                        "symbol": symbol,
                        "ERROR": str(exc),
                    }))
                finally:
                    await page.close()

            summary = {
                "requested": len(results),
                "symbol_match_pass": sum(
                    bool(x.get("symbol_match")) for x in results
                ),
                "strike_state_pass": sum(
                    bool(x.get("strike_state_present")) for x in results
                ),
                "seven_row_pass": sum(
                    bool(x.get("seven_rows")) for x in results
                ),
                "61_column_pass": sum(
                    bool(x.get("sixty_one_columns")) for x in results
                ),
                "results": results,
            }

            print("\nSUMMARY")
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        finally:
            # Disconnect only. Do not close the user's Chromium/browser.
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
