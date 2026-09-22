from __future__ import annotations
import asyncio, json, time
from urllib.parse import urlencode

ENDPOINT = "https://www.icharts.in/opt/OptionChainTable_Beta_v19.php"

BASE = {
    "buttontype": "Lots_btn",
    "optExpDate": "29SEP26",
    "optExpDate_hist": "undefined",
    "striketype": "mainstrikes",
    "txtDate": "undefined",
    "defaultDate": "undefined",
    "atmstrikesnumber": "7",
    "atmstrikesnumberfixed": "3",
    "optStrike": "undefined",
    "dType": "latest",
}

async def _one(context, symbol: str, timeout_seconds: int = 30) -> dict:
    started = time.perf_counter()
    page = await context.new_page()
    try:
        payload = dict(BASE)
        payload["optSymbol"] = symbol
        response = await page.request.post(
            ENDPOINT,
            data=urlencode(payload),
            timeout=timeout_seconds * 1000,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        )
        text = await response.text()
        r = {
            "symbol": symbol, "http_status": response.status,
            "elapsed_ms": round((time.perf_counter()-started)*1000,1),
            "json_valid": False, "server_symbol": "", "optExpDate": "",
            "strikePriceATM": "", "optStrike": "", "futuresPriceStr": "",
            "reported_total_records": 0, "aaData_count": 0,
            "returned_strikes": [], "pass": False, "error": "",
        }
        try:
            data = json.loads(text)
            r["json_valid"] = isinstance(data, dict)
            if not isinstance(data, dict):
                r["error"] = "JSON root is not an object"
                return r
            r["server_symbol"] = str(data.get("symbol_1", ""))
            r["optExpDate"] = str(data.get("optExpDate", ""))
            r["strikePriceATM"] = str(data.get("strikePriceATM", ""))
            r["optStrike"] = str(data.get("optStrike", ""))
            r["futuresPriceStr"] = str(data.get("futuresPriceStr", ""))
            r["reported_total_records"] = int(data.get("iTotalRecords") or 0)
            rows = data.get("aaData") or []
            r["aaData_count"] = len(rows) if isinstance(rows, list) else 0
            if isinstance(rows, list):
                r["returned_strikes"] = [
                    str(row[32]) for row in rows
                    if isinstance(row, list) and len(row) > 32
                ]
            r["symbol_match"] = r["server_symbol"].strip().upper() == symbol.upper()
            r["parameter_complete"] = all(
                str(r[k]).strip() for k in
                ("server_symbol","optExpDate","strikePriceATM","optStrike")
            )
            r["seven_rows"] = r["aaData_count"] == 7
            r["pass"] = (
                response.status == 200 and r["json_valid"] and
                r["symbol_match"] and r["parameter_complete"] and r["seven_rows"]
            )
        except Exception as exc:
            r["error"] = f"JSON parse/shape error: {exc}"
        return r
    except Exception as exc:
        return {
            "symbol": symbol, "http_status": None,
            "elapsed_ms": round((time.perf_counter()-started)*1000,1),
            "pass": False, "error": str(exc),
        }
    finally:
        await page.close()

async def run_direct_response_parameter_probe(context, symbols, timeout_seconds=30, concurrency=5):
    started = time.perf_counter()
    sem = asyncio.Semaphore(max(1, int(concurrency)))
    async def worker(symbol):
        async with sem:
            return await _one(context, symbol, timeout_seconds)
    results = await asyncio.gather(*(worker(s) for s in symbols))
    passed = sum(bool(r.get("pass")) for r in results)
    return {
        "test": "Option Chain direct-response parameter probe",
        "requested": len(symbols), "passed": passed,
        "failed": len(symbols)-passed,
        "elapsed_ms": round((time.perf_counter()-started)*1000,1),
        "results": results,
    }
