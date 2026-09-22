"""
Controlled Option Chain symbol-state probe.

Purpose:
- TEST ONLY. No scheduler, no XLSX, no production output.
- Determine whether OptionChain.php can be initialized directly for a requested
  symbol without UI symbol switching.
- If the page initializes for the requested symbol, capture:
    selected symbol, selected expiry, strikePriceATM, centralStrike,
    selected optStrike, number of strike options, and the 7-row table.
- This is the missing validation needed before production direct-XHR collection.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import async_playwright


OPTION_CHAIN = "https://www.icharts.in/opt/OptionChain.php"
DEFAULT_SYMBOLS = ["DIXON", "RELIANCE", "INFY", "TCS", "HDFCBANK"]


def profile_path() -> str:
    # Match the controlled portal's persistent profile location if present.
    candidates = [
        os.getenv("DOWNLOADER_PORTAL_BROWSER_PROFILE", ""),
        str(Path(__file__).resolve().parents[1] / "browser_profile"),
        str(Path(__file__).resolve().parents[2] / "ReportGenration" / "DownloaderPortal" / "browser_profile"),
    ]
    for p in candidates:
        if p and Path(p).exists():
            return p
    # The first candidate is created by Playwright if it does not exist.
    return candidates[0] or candidates[1]


async def inspect(page, requested: str, url: str) -> dict:
    started = time.perf_counter()
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2500)

    result = await page.evaluate(
        """() => {
            const val = (sel) => {
                const e = document.querySelector(sel);
                return e ? String(e.value ?? '') : '';
            };
            const opts = (sel) => Array.from(document.querySelectorAll(sel + ' option'))
                .map(o => ({value: String(o.value ?? ''), text: String(o.textContent ?? '').trim()}));
            const table = document.querySelector('table');
            const tables = Array.from(document.querySelectorAll('table'));
            let main = null;
            for (const t of tables) {
                const headers = Array.from(t.querySelectorAll('thead th, thead td')).map(x => x.textContent.trim());
                const rows = Array.from(t.querySelectorAll('tbody tr'));
                if (headers.length >= 50 && rows.length >= 1) {
                    main = {headers, rows: rows.map(r => Array.from(r.querySelectorAll('td')).map(x => x.textContent.trim()))};
                    break;
                }
            }
            return {
                title: document.title,
                url: location.href,
                selected_symbol: val('#optSymbol'),
                selected_expiry: val('#optExpDate'),
                strike_price_atm: val('#strikePriceATM'),
                central_strike: val('#centralStrike'),
                selected_opt_strike: val('#optStrike'),
                opt_strike_options: opts('#optStrike'),
                main_table: main,
            };
        }"""
    )

    result.update({
        "requested_symbol": requested,
        "url_used": url,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "symbol_match": result.get("selected_symbol", "").upper() == requested.upper(),
        "strike_state_present": bool(
            result.get("strike_price_atm")
            or result.get("central_strike")
            or result.get("selected_opt_strike")
        ),
    })
    return result


async def main():
    symbols = sys.argv[1:] or DEFAULT_SYMBOLS
    profile = profile_path()
    if not profile:
        raise RuntimeError(
            "Persistent browser profile not found. Set DOWNLOADER_PORTAL_BROWSER_PROFILE "
            "to the existing authenticated DownloaderPortal browser_profile."
        )

    print("Option Chain Symbol-State Probe")
    print(f"Profile: {profile}")
    print(f"Symbols: {', '.join(symbols)}")
    print("TEST ONLY: no scheduler, no XLSX, no production output.")
    print()

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            profile,
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        try:
            results = []
            for symbol in symbols:
                # First test query-string initialization.
                qurl = OPTION_CHAIN + "?" + urlencode({"optSymbol": symbol})
                page = await context.new_page()
                try:
                    r = await inspect(page, symbol, qurl)
                    results.append(r)
                    print(json.dumps({
                        "symbol": symbol,
                        "selected_symbol": r["selected_symbol"],
                        "selected_expiry": r["selected_expiry"],
                        "strikePriceATM": r["strike_price_atm"],
                        "centralStrike": r["central_strike"],
                        "optStrike": r["selected_opt_strike"],
                        "strike_options": len(r["opt_strike_options"]),
                        "rows": len((r.get("main_table") or {}).get("rows", [])),
                        "symbol_match": r["symbol_match"],
                        "elapsed_ms": r["elapsed_ms"],
                    }, ensure_ascii=False))
                finally:
                    await page.close()

            summary = {
                "requested": len(results),
                "symbol_match_pass": sum(bool(x["symbol_match"]) for x in results),
                "strike_state_present": sum(bool(x["strike_state_present"]) for x in results),
                "seven_row_table": sum(
                    len((x.get("main_table") or {}).get("rows", [])) == 7 for x in results
                ),
                "results": results,
            }
            print("\nSUMMARY")
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())
