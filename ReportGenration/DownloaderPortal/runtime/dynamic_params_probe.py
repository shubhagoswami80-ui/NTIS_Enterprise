from __future__ import annotations
import asyncio, json, time
from typing import Any

DETAILS_ENDPOINT = "https://www.icharts.in/opt/hcharts/stx8req/php/getTopRightDetails.php"

async def _one(api, symbol: str, timeout_ms: int) -> dict[str, Any]:
    params = {
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
    t=time.perf_counter()
    out={"symbol":symbol,"http_status":None,"json_valid":False,"content_type":"","elapsed_ms":None,"top_level_type":"","keys":[],"preview":{},"candidate_fields":{},"error":""}
    try:
        r=await api.post(DETAILS_ENDPOINT, form=params, headers={"Referer":"https://www.icharts.in/opt/OptionChain.php","Origin":"https://www.icharts.in","X-Requested-With":"XMLHttpRequest"}, timeout=timeout_ms)
        body=await r.body(); out["http_status"]=r.status; out["content_type"]=r.headers.get("content-type","")
        if r.status != 200: out["error"]=f"HTTP {r.status}"; return out
        try: obj=json.loads(body.decode('utf-8',errors='replace')); out["json_valid"]=True
        except Exception as e: out["error"]=f"Invalid JSON: {e}"; return out
        out["top_level_type"]=type(obj).__name__
        if isinstance(obj,dict):
            out["keys"]=[str(k) for k in obj.keys()]
            out["preview"]={str(k):obj[k] for k in list(obj.keys())[:30]}
            def walk(v, path="", out=None, depth=0):
                if out is None: out={}
                if depth>4: return out
                if isinstance(v, dict):
                    for k,val in v.items():
                        p=(path+"." if path else "")+str(k)
                        if isinstance(val,(dict,list)): walk(val,p,out,depth+1)
                        else: out[p]=val
                elif isinstance(v, list):
                    for i,val in enumerate(v[:10]):
                        p=f"{path}[{i}]"
                        if isinstance(val,(dict,list)): walk(val,p,out,depth+1)
                        else: out[p]=val
                return out
            leaves=walk(obj)
            out["candidate_fields"]={k:v for k,v in leaves.items() if any(x.lower() in k.lower() for x in ("symbol","exp","strike","future","date","time","lot"))}
            out["leaf_fields_preview"] = dict(list(leaves.items())[:120])
        else: out["preview"]=str(obj)[:2000]
    except Exception as e: out["error"]=str(e)
    finally: out["elapsed_ms"]=round((time.perf_counter()-t)*1000,1)
    return out

async def run_dynamic_params_probe(context, symbols, timeout_seconds=15, concurrency=5):
    symbols=[str(s).strip().upper() for s in symbols if str(s).strip()]
    if not symbols: raise ValueError('At least one symbol is required.')
    api=context.request; sem=asyncio.Semaphore(max(1,int(concurrency)))
    async def worker(s):
        async with sem: return await _one(api,s,int(timeout_seconds*1000))
    started=time.perf_counter(); results=await asyncio.gather(*(worker(s) for s in symbols))
    return {"endpoint":DETAILS_ENDPOINT,"requested":len(symbols),"passed":sum(x['http_status']==200 and x['json_valid'] for x in results),"failed":sum(not(x['http_status']==200 and x['json_valid']) for x in results),"elapsed_ms":round((time.perf_counter()-started)*1000,1),"results":results}
