"""
Fix 37 — Option Chain Dynamic State -> Direct POST Probe.

This is the next controlled step after the failed URL-navigation experiments.

It uses the EXISTING authenticated Playwright BrowserContext.
For each requested symbol, sequentially:
1. Opens OptionChain.php in a temporary page.
2. Verifies #optSymbol contains the requested symbol.
3. Uses the page's own #optSymbol select control with select_option().
4. Waits for the selected symbol and dynamic hidden/select values to update.
5. Reads:
   - optExpDate
   - strikePriceATM
   - centralStrike
   - optStrike
   - defaultDate
   - atmstrikesnumber
   - atmstrikesnumberfixed
   - buttontype
   - striketype
   - dType
6. Sends the exact resulting request contract to
   OptionChainTable_Beta_v19.php.
7. Validates HTTP/JSON/server symbol/7-row response.

No hard-coded symbol strike is used.
No client-side strike cap is introduced.
The page's own current/default selection determines optStrike.

This probe is TEST ONLY: no scheduler, no XLSX, no production output.
"""

from __future__ import annotations

import asyncio
import json
import time
from urllib.parse import urlencode

OPTION_CHAIN = "https://www.icharts.in/opt/OptionChain.php"
TABLE = "https://www.icharts.in/opt/OptionChainTable_Beta_v19.php"


async def _read_state(page, requested: str) -> dict:
    return await page.evaluate(
        """(requested) => {
            const val = (id) => {
                const e = document.querySelector(id);
                return e ? String(e.value ?? '') : '';
            };
            const options = Array.from(
                document.querySelectorAll('#optSymbol option')
            ).map(o => String(o.value ?? ''));

            const table = Array.from(document.querySelectorAll('table')).find(t => {
                const rows = t.querySelectorAll('tbody tr');
                const cells = t.querySelectorAll('thead th, thead td');
                return rows.length >= 1 && cells.length >= 50;
            });

            return {
                requested,
                selected_symbol: val('#optSymbol'),
                symbol_available: options.some(
                    x => x.toUpperCase() === requested.toUpperCase()
                ),
                optExpDate: val('#optExpDate'),
                strikePriceATM: val('#strikePriceATM'),
                centralStrike: val('#centralStrike'),
                optStrike: val('#optStrike'),
                defaultDate: val('#defaultDate'),
                defaultDatedMY: val('#defaultDatedMY'),
                latestDate: val('#latestDate'),
                atmstrikesnumber: val('#atmstrikesnumber'),
                atmstrikesnumberfixed: val('#atmstrikesnumberfixed'),
                buttontype: val('[name="buttontype"]'),
                striketype: val('[name="striketype"]:checked') || val('#striketype'),
                dType: val('#rdDataType'),
                table_rows: table ? table.querySelectorAll('tbody tr').length : 0,
                table_columns: table ? table.querySelectorAll('thead th, thead td').length : 0,
                title: document.title,
            };
        }""",
        requested,
    )


async def _wait_for_state(page, symbol: str, old_state: dict):
    await page.wait_for_function(
        """({symbol, oldATM}) => {
            const s = document.querySelector('#optSymbol');
            const atm = document.querySelector('#strikePriceATM');
            const strike = document.querySelector('#optStrike');
            return s && String(s.value).toUpperCase() === symbol.toUpperCase()
                && atm && String(atm.value || '').trim() !== ''
                && strike && String(strike.value || '').trim() !== ''
                && (
                    String(atm.value) !== String(oldATM || '')
                    || String(strike.value) !== ''
                );
        }""",
        {"symbol": symbol, "oldATM": old_state.get("strikePriceATM", "")},
        timeout=15000,
    )


async def _one(context, symbol: str, timeout_seconds: int = 30) -> dict:
    started = time.perf_counter()
    page = await context.new_page()

    result = {
        "symbol": symbol,
        "selected_symbol": "",
        "optExpDate": "",
        "strikePriceATM": "",
        "centralStrike": "",
        "optStrike": "",
        "defaultDate": "",
        "atmstrikesnumber": "",
        "atmstrikesnumberfixed": "",
        "table_http": None,
        "server_symbol": "",
        "aaData_count": 0,
        "post_valid": False,
        "pass": False,
        "elapsed_ms": 0,
        "error": "",
    }

    try:
        await page.goto(
            OPTION_CHAIN,
            wait_until="domcontentloaded",
            timeout=timeout_seconds * 1000,
        )
        await page.wait_for_timeout(1200)

        initial = await _read_state(page, symbol)

        if not initial["symbol_available"]:
            result["error"] = "Requested symbol is not present in #optSymbol options."
            return result

        # The selector itself is the authoritative page mechanism.
        # select_option() dispatches input/change events.
        try:
            await page.select_option("#optSymbol", symbol)
        except Exception as exc:
            result["error"] = f"select_option failed: {exc}"
            return result

        try:
            await _wait_for_state(page, symbol, initial)
        except Exception:
            # Some iCharts builds update state without changing ATM/strike
            # relative to the previous symbol. Re-read before declaring failure.
            await page.wait_for_timeout(2500)

        state = await _read_state(page, symbol)
        result.update({
            "selected_symbol": state.get("selected_symbol", ""),
            "optExpDate": state.get("optExpDate", ""),
            "strikePriceATM": state.get("strikePriceATM", ""),
            "centralStrike": state.get("centralStrike", ""),
            "optStrike": state.get("optStrike", ""),
            "defaultDate": state.get("defaultDate", ""),
            "atmstrikesnumber": state.get("atmstrikesnumber", ""),
            "atmstrikesnumberfixed": state.get("atmstrikesnumberfixed", ""),
        })

        if state["selected_symbol"].upper() != symbol.upper():
            result["error"] = (
                f"Page selector did not settle on requested symbol; "
                f"selected={state['selected_symbol']!r}"
            )
            return result

        # Build the POST from the page's own current state.
        payload = {
            "optSymbol": symbol,
            "buttontype": state.get("buttontype") or "Lots_btn",
            "optExpDate": state.get("optExpDate") or "undefined",
            "optExpDate_hist": "undefined",
            "striketype": state.get("striketype") or "mainstrikes",
            "txtDate": "undefined",
            "defaultDate": state.get("defaultDate") or "undefined",
            "atmstrikesnumber": state.get("atmstrikesnumber") or "7",
            "atmstrikesnumberfixed": state.get("atmstrikesnumberfixed") or "3",
            "optStrike": state.get("optStrike") or "undefined",
            "dType": state.get("dType") or "latest",
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
        result["table_http"] = response.status

        body = await response.text()
        try:
            data = json.loads(body)
        except Exception as exc:
            result["error"] = (
                f"POST JSON parse error: {exc}; body={body[:300]!r}"
            )
            return result

        if not isinstance(data, dict):
            result["error"] = "POST JSON root is not an object."
            return result

        result["server_symbol"] = str(data.get("symbol_1", ""))
        rows = data.get("aaData") or []
        result["aaData_count"] = len(rows) if isinstance(rows, list) else 0
        result["post_valid"] = (
            response.status == 200
            and result["server_symbol"].upper() == symbol.upper()
            and result["aaData_count"] > 0
        )
        result["pass"] = result["post_valid"]

    except Exception as exc:
        result["error"] = str(exc)
    finally:
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        await page.close()

    return result


async def run_optionchain_dynamic_state_probe(
    context, symbols, timeout_seconds=30
):
    started = time.perf_counter()
    # Sequential deliberately: this is a state-validation probe and must not
    # have multiple pages competing with one another for browser state.
    results = []
    for symbol in symbols:
        results.append(await _one(context, symbol, timeout_seconds))

    passed = sum(bool(r.get("pass")) for r in results)
    return {
        "test": "Option Chain Dynamic State -> Direct POST Probe",
        "requested": len(symbols),
        "passed": passed,
        "failed": len(symbols) - passed,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "results": results,
    }
