from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any

from .dynamic_params_probe import DETAILS_ENDPOINT

OPTION_URL = "https://www.icharts.in/opt/OptionChain.php"
ENDPOINT = "https://www.icharts.in/opt/OptionChainTable_Beta_v19.php"


def _to_float(value):
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


async def _dynamic_futures(api, symbol: str, timeout_ms: int) -> dict[str, Any]:
    r = await api.post(
        DETAILS_ENDPOINT,
        form={
            "optSymbol": symbol,
            "optExpDate": "undefined",
            "monthlyExpDate": "undefined",
            "Presentday": "undefined",
            "Prevday": "undefined",
            "rdDataType": "latest",
            "txtDate": "undefined",
            "defaultDate": "undefined",
            "e": "1",
        },
        headers={
            "Referer": OPTION_URL,
            "Origin": "https://www.icharts.in",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=timeout_ms,
    )
    body = await r.body()
    if r.status != 200:
        raise RuntimeError(f"getTopRightDetails HTTP {r.status}")
    obj = json.loads(body.decode("utf-8", "replace"))
    fut = obj.get("futures") if isinstance(obj, dict) else None
    if not isinstance(fut, list) or len(fut) < 3:
        raise RuntimeError("Dynamic futures array missing")
    return {
        "expiry": str(fut[1]),
        "futures_price": _to_float(fut[2]),
        "futures_raw": [str(x) for x in fut[:6]],
    }


async def _one(context, symbol: str, timeout_ms: int) -> dict[str, Any]:
    started = time.perf_counter()
    page = await context.new_page()
    out: dict[str, Any] = {
        "symbol": symbol,
        "status": "FAILED",
        "http_status": None,
        "elapsed_ms": None,
        "expiry": "",
        "futures_price": None,
        "default_date": "",
        "latest_date": "",
        "central_strike": None,
        "strike_price_atm": None,
        "selected_strike": None,
        "strike_options": [],
        "strike_option_count": 0,
        "returned_strikes": [],
        "payload_opt_strike": None,
        "payload_futures_price": None,
        "payload_records": 0,
        "symbol_match": False,
        "center_match": False,
        "strike_sequence_valid": False,
        "error": "",
    }
    try:
        await page.goto(OPTION_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.locator("#optSymbol").wait_for(state="attached", timeout=timeout_ms)

        # The authenticated page itself is the source of truth for the symbol's
        # strike ladder and ATM/central strike. This avoids hard-coded strike rules.
        await page.select_option("#optSymbol", symbol, timeout=timeout_ms)
        await page.wait_for_timeout(700)

        await page.wait_for_function(
            """() => {
                const s = document.querySelector('#optSymbol');
                const c = document.querySelector('#centralStrike');
                return s && s.value && c && String(c.value || '').trim() !== '';
            }""",
            timeout=timeout_ms,
        )
        # Allow the page's dependent controls to finish updating.
        await page.wait_for_timeout(250)

        selected_symbol = await page.locator("#optSymbol").input_value()
        if selected_symbol.upper() != symbol.upper():
            raise RuntimeError(f"Symbol selection mismatch: {selected_symbol}")

        out["expiry"] = await page.locator("#optExpDate").input_value()
        out["default_date"] = await page.locator("#defaultDate").input_value()
        out["latest_date"] = await page.locator("#latestDate").input_value()
        out["selected_strike"] = _to_float(await page.locator("#optStrike").input_value())
        out["central_strike"] = _to_float(await page.locator("#centralStrike").input_value())
        out["strike_price_atm"] = _to_float(await page.locator("#strikePriceATM").input_value())

        options = await page.locator("#optStrike option").evaluate_all(
            "els => els.map(o => ({value:o.value, text:(o.textContent||'').trim()}))"
        )
        strikes = []
        for item in options:
            value = _to_float(item.get("value"))
            if value is not None and value != 0:
                strikes.append(value)
        out["strike_options"] = strikes
        out["strike_option_count"] = len(strikes)

        if out["central_strike"] is None:
            raise RuntimeError("centralStrike is empty")
        if out["central_strike"] not in strikes:
            raise RuntimeError("centralStrike is not present in optStrike options")

        dynamic = await _dynamic_futures(context.request, symbol, timeout_ms)
        # The page expiry and endpoint expiry must agree before replay.
        if dynamic["expiry"] and dynamic["expiry"] != out["expiry"]:
            raise RuntimeError(
                f"Expiry mismatch: page={out['expiry']} endpoint={dynamic['expiry']}"
            )
        out["futures_price"] = dynamic["futures_price"]

        params = {
            "optSymbol": symbol,
            "buttontype": "Lots_btn",
            "optExpDate": out["expiry"],
            "optExpDate_hist": "undefined",
            "striketype": "mainstrikes",
            "txtDate": "undefined",
            "defaultDate": out["default_date"],
            "atmstrikesnumber": "7",
            "atmstrikesnumberfixed": "3",
            "optStrike": str(int(out["central_strike"])),
            "dType": "latest",
        }
        response = await context.request.post(
            ENDPOINT,
            form=params,
            headers={
                "Referer": OPTION_URL,
                "Origin": "https://www.icharts.in",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=timeout_ms,
        )
        body = await response.body()
        out["http_status"] = response.status
        if response.status != 200:
            raise RuntimeError(f"OptionChainTable HTTP {response.status}")

        payload = json.loads(body.decode("utf-8", "replace"))
        if not isinstance(payload, dict):
            raise RuntimeError("OptionChain payload is not a JSON object")

        aa = payload.get("aaData")
        if not isinstance(aa, list):
            aa = []
        out["payload_records"] = len(aa)
        out["payload_opt_strike"] = _to_float(payload.get("optStrike"))
        out["payload_futures_price"] = _to_float(payload.get("futuresPriceStr"))
        out["symbol_match"] = str(payload.get("symbol_1", "")).upper() == symbol.upper()

        returned = []
        for row in aa:
            if isinstance(row, list) and len(row) > 32:
                value = _to_float(row[32])
                if value is not None:
                    returned.append(value)
        out["returned_strikes"] = returned
        out["center_match"] = (
            out["payload_opt_strike"] == out["central_strike"]
            and out["selected_strike"] == out["central_strike"]
        )
        out["strike_sequence_valid"] = (
            len(returned) == len(aa) == 7
            and out["central_strike"] in returned
        )

        if not out["symbol_match"]:
            raise RuntimeError("Payload symbol mismatch")
        if not out["center_match"]:
            raise RuntimeError(
                f"Center mismatch: page={out['central_strike']} payload={out['payload_opt_strike']}"
            )
        if not out["strike_sequence_valid"]:
            raise RuntimeError(
                f"Unexpected returned strike sequence: {returned}"
            )

        out["status"] = "PASS"
    except Exception as exc:
        out["error"] = str(exc)
    finally:
        out["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        try:
            await page.close()
        except Exception:
            pass
    return out


async def run_strike_probe(context, symbols, timeout_seconds=30, concurrency=5):
    symbols = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if not symbols:
        raise ValueError("At least one symbol is required.")
    if not context:
        raise ValueError("Authenticated Playwright browser context is required.")

    sem = asyncio.Semaphore(max(1, int(concurrency)))
    started = time.perf_counter()

    async def worker(symbol):
        async with sem:
            return await _one(context, symbol, int(timeout_seconds * 1000))

    results = await asyncio.gather(*(worker(s) for s in symbols))
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    passed = sum(x["status"] == "PASS" for x in results)
    return {
        "test": "Option Chain dynamic strike + parameter + direct POST validation",
        "requested": len(symbols),
        "concurrency": int(concurrency),
        "passed": passed,
        "failed": len(results) - passed,
        "elapsed_ms": elapsed,
        "results": results,
        "production_scheduler_activated": False,
        "production_output_written": False,
        "note": "Controlled validation only. No XLSX or scheduler output is written.",
    }
