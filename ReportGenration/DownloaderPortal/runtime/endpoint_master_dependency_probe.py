"""
Fix 35 — Endpoint Master diagnostic with observed expiry seed.

Why:
Fix 34 still returned 0/5. The previously validated getTopRightDetails
requests were observed with optExpDate=29SEP26, whereas Fix 34 changed that
field to "undefined". This diagnostic restores the observed request contract
for TEST ONLY and exposes the actual top-right response shape/error.

It does not make 29SEP26 a production hard-code. It is a diagnostic seed to
determine whether getTopRightDetails requires an expiry input.

No scheduler, XLSX, production output, or new Chromium.
"""

from __future__ import annotations
import asyncio,json,time
from urllib.parse import urlencode

TOP_RIGHT="https://www.icharts.in/opt/hcharts/stx8req/php/getTopRightDetails.php"
TABLE="https://www.icharts.in/opt/OptionChainTable_Beta_v19.php"
OBSERVED_EXPIRY="29SEP26"

def find_futures(obj):
    if isinstance(obj,dict):
        if "futures" in obj:
            return obj["futures"]
        for k,v in obj.items():
            found=find_futures(v)
            if found is not None:
                return found
    elif isinstance(obj,list):
        for v in obj:
            found=find_futures(v)
            if found is not None:
                return found
    return None

def parse_futures(data):
    f=find_futures(data)
    if isinstance(f,list):
        return {
            "symbol":str(f[0]) if len(f)>0 else "",
            "expiry":str(f[1]) if len(f)>1 else "",
            "futures":str(f[2]) if len(f)>2 else "",
            "date":str(f[5]) if len(f)>5 else "",
            "shape":"list",
        }
    return {"symbol":"","expiry":"","futures":"","date":"","shape":type(f).__name__}

def compact_raw(data):
    try:
        s=json.dumps(data,ensure_ascii=False)
        return s[:1800]
    except Exception:
        return str(data)[:1800]

async def one(context,symbol,timeout_seconds=30):
    started=time.perf_counter()
    page=await context.new_page()
    try:
        top={
            "optSymbol":symbol,
            "optExpDate":OBSERVED_EXPIRY,
            "monthlyExpDate":"undefined",
            "Presentday":"undefined",
            "Prevday":"undefined",
            "rdDataType":"latest",
            "txtDate":"undefined",
            "defaultDate":"undefined",
            "e":"1",
        }
        tr=await page.request.post(
            TOP_RIGHT,data=urlencode(top),timeout=timeout_seconds*1000,
            headers={"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8"}
        )
        tr_text=await tr.text()
        tr_data=json.loads(tr_text)
        f=parse_futures(tr_data)
        expiry=f.get("expiry") or OBSERVED_EXPIRY

        table={
            "optSymbol":symbol,
            "buttontype":"Lots_btn",
            "optExpDate":expiry,
            "optExpDate_hist":"undefined",
            "striketype":"mainstrikes",
            "txtDate":"undefined",
            "defaultDate":"undefined",
            "atmstrikesnumber":"7",
            "atmstrikesnumberfixed":"3",
            "optStrike":"undefined",
            "dType":"latest",
        }
        tb=await page.request.post(
            TABLE,data=urlencode(table),timeout=timeout_seconds*1000,
            headers={"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8"}
        )
        tb_text=await tb.text()
        tb_data=json.loads(tb_text)
        rows=tb_data.get("aaData") or []
        server=str(tb_data.get("symbol_1",""))
        strikes=[str(r[32]) for r in rows if isinstance(r,list) and len(r)>32]

        return {
            "symbol":symbol,
            "top_http":tr.status,
            "table_http":tb.status,
            "top_symbol":f.get("symbol",""),
            "top_expiry":f.get("expiry",""),
            "futures":f.get("futures",""),
            "top_shape":f.get("shape",""),
            "table_server_symbol":server,
            "ATM":str(tb_data.get("strikePriceATM","")),
            "optStrike":str(tb_data.get("optStrike","")),
            "rows":len(rows) if isinstance(rows,list) else 0,
            "strikes":strikes,
            "symbol_match":server.upper()==symbol.upper(),
            "pass":tr.status==200 and tb.status==200 and server.upper()==symbol.upper() and len(rows)==7,
            "top_raw":compact_raw(tr_data),
            "elapsed_ms":round((time.perf_counter()-started)*1000,1),
            "error":"",
        }
    except Exception as exc:
        return {
            "symbol":symbol,"pass":False,
            "elapsed_ms":round((time.perf_counter()-started)*1000,1),
            "error":str(exc)
        }
    finally:
        await page.close()

async def run_endpoint_master_dependency_probe(context,symbols,timeout_seconds=30,concurrency=5):
    started=time.perf_counter()
    sem=asyncio.Semaphore(max(1,int(concurrency)))
    async def worker(s):
        async with sem:
            return await one(context,s,timeout_seconds)
    results=await asyncio.gather(*(worker(s) for s in symbols))
    passed=sum(bool(r.get("pass")) for r in results)
    return {
        "test":"Option Chain Endpoint Master seed-expiry diagnostic",
        "seed_expiry":OBSERVED_EXPIRY,
        "requested":len(symbols),
        "passed":passed,
        "failed":len(symbols)-passed,
        "elapsed_ms":round((time.perf_counter()-started)*1000,1),
        "results":results,
    }
