"""
Fix 41 — Direct Replay v2: Correct Symbol Capture.

Fix 40 exposed a race/selection issue: the captured request for every symbol
was the page's existing/background HDFCBANK request. That explains the result
where all five rows showed:
    Captured Server = HDFCBANK
    Captured ATM = 740
while only HDFCBANK passed.

Fix 41 accepts a captured OptionChainTable POST ONLY when its POST body has:
    optSymbol == requested symbol

This filters out:
- initial page-load requests
- background refresh requests
- stale requests generated before the symbol selector changes

The browser page is still used only to trigger and capture the exact request.
The exact captured request is then replayed through the authenticated context.

No manual parameter construction, no hard-coded ATM, no strike cap.
"""

from __future__ import annotations

import asyncio
import json
import time
from urllib.parse import parse_qs

OPTION_CHAIN = "https://www.icharts.in/opt/OptionChain.php"
TABLE_MARKER = "OptionChainTable_Beta_v19.php"


def _form(body):
    try:
        p = parse_qs(body or "", keep_blank_values=True)
        return {k: (v[0] if v else "") for k, v in p.items()}
    except Exception:
        return {}


def _signature(data):
    if not isinstance(data, dict):
        return None
    rows = data.get("aaData") or []
    return {
        "server_symbol": str(data.get("symbol_1", "")),
        "expiry": str(data.get("optExpDate", "")),
        "atm": str(data.get("strikePriceATM", "")),
        "optStrike": str(data.get("optStrike", "")),
        "rows": len(rows) if isinstance(rows, list) else 0,
        "strikes": [
            str(r[32])
            for r in rows
            if isinstance(r, list) and len(r) > 32
        ],
    }


async def _one(context, symbol, timeout_seconds=30):
    started = time.perf_counter()
    page = await context.new_page()

    try:
        await page.goto(
            OPTION_CHAIN,
            wait_until="domcontentloaded",
            timeout=timeout_seconds * 1000,
        )
        await page.wait_for_timeout(1200)

        options = await page.locator("#optSymbol option").evaluate_all(
            """els => els.map(e => String(e.value || '').toUpperCase())"""
        )
        if symbol.upper() not in options:
            raise RuntimeError(
                "Requested symbol is not present in #optSymbol options."
            )

        # IMPORTANT:
        # The page may generate a request for its initially selected symbol
        # before/while the selector is being changed. Use expect_request with
        # a predicate on POST optSymbol, so only the requested symbol's actual
        # iCharts request can satisfy the capture.
        def is_target_request(req):
            if TABLE_MARKER not in req.url:
                return False
            if req.method.upper() != "POST":
                return False
            params = _form(req.post_data or "")
            return params.get("optSymbol", "").upper() == symbol.upper()

        async with page.expect_request(
            is_target_request,
            timeout=timeout_seconds * 1000,
        ) as req_info:
            await page.select_option("#optSymbol", symbol)

        req = await req_info.value
        response = await req.response()
        if response is None:
            raise RuntimeError("Captured target request has no response.")

        request_body = req.post_data or ""
        request_params = _form(request_body)
        response_text = await response.text()

        try:
            captured_json = json.loads(response_text)
        except Exception as exc:
            raise RuntimeError(
                f"Captured target response is not JSON: {exc}; "
                f"body={response_text[:300]!r}"
            )

        captured_sig = _signature(captured_json)
        if captured_sig is None:
            raise RuntimeError("Captured response JSON root is not an object.")

        # Relevant browser headers only. Authentication cookies remain in the
        # existing Playwright BrowserContext.
        replay_headers = {
            k: v
            for k, v in req.headers.items()
            if k.lower() in {
                "content-type",
                "referer",
                "origin",
                "x-requested-with",
                "accept",
            }
        }
        replay_headers.pop("content-length", None)

        replay = await context.request.post(
            req.url,
            data=request_body,
            headers=replay_headers,
            timeout=timeout_seconds * 1000,
        )
        replay_text = await replay.text()

        try:
            replay_json = json.loads(replay_text)
        except Exception as exc:
            return {
                "symbol": symbol,
                "captured_optSymbol": request_params.get("optSymbol", ""),
                "captured_http": response.status,
                "replay_http": replay.status,
                "captured_server_symbol": captured_sig["server_symbol"],
                "replay_server_symbol": "",
                "captured_atm": captured_sig["atm"],
                "replay_atm": "",
                "captured_rows": captured_sig["rows"],
                "replay_rows": 0,
                "payload_match": False,
                "pass": False,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "error": f"Replay response is not JSON: {exc}; body={replay_text[:300]!r}",
                "request_params": request_params,
            }

        replay_sig = _signature(replay_json)
        payload_match = replay_sig == captured_sig

        passed = (
            response.status == 200
            and replay.status == 200
            and request_params.get("optSymbol", "").upper() == symbol.upper()
            and captured_sig["server_symbol"].upper() == symbol.upper()
            and replay_sig["server_symbol"].upper() == symbol.upper()
            and payload_match
        )

        return {
            "symbol": symbol,
            "captured_optSymbol": request_params.get("optSymbol", ""),
            "captured_http": response.status,
            "replay_http": replay.status,
            "captured_server_symbol": captured_sig["server_symbol"],
            "replay_server_symbol": replay_sig["server_symbol"],
            "captured_atm": captured_sig["atm"],
            "replay_atm": replay_sig["atm"],
            "captured_rows": captured_sig["rows"],
            "replay_rows": replay_sig["rows"],
            "captured_strikes": captured_sig["strikes"],
            "replay_strikes": replay_sig["strikes"],
            "captured_expiry": captured_sig["expiry"],
            "replay_expiry": replay_sig["expiry"],
            "captured_optStrike": captured_sig["optStrike"],
            "replay_optStrike": replay_sig["optStrike"],
            "payload_match": payload_match,
            "request_url": req.url,
            "request_params": request_params,
            "request_headers": replay_headers,
            "pass": passed,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": "",
        }

    except Exception as exc:
        return {
            "symbol": symbol,
            "pass": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": str(exc),
        }
    finally:
        await page.close()


async def run_optionchain_direct_replay_probe_v2(
    context, symbols, timeout_seconds=30
):
    started = time.perf_counter()
    results = []

    # Sequential browser-state capture. Direct replay is inside each cycle.
    for symbol in symbols:
        results.append(await _one(context, symbol, timeout_seconds))

    passed = sum(bool(r.get("pass")) for r in results)
    return {
        "test": "Option Chain Direct Replay Probe v2 — Correct Symbol Capture",
        "requested": len(symbols),
        "passed": passed,
        "failed": len(symbols) - passed,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "results": results,
    }
