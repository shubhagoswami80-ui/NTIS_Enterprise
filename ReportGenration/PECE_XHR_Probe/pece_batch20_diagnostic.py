from pathlib import Path
import json
from datetime import datetime
from urllib.parse import parse_qsl, urlencode

TARGET_URL="https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
SELECTOR="#optSymbol"

def _safe(pd):
    if not pd: return None
    try: pairs=parse_qsl(pd,keep_blank_values=True)
    except Exception: return "[REDACTED]"
    sensitive={"sessionid","phpsessid","token","password","passwd","username","user_name","userpassword","cf_clearance"}
    return urlencode([(k,"[REDACTED]" if k.lower().strip() in sensitive else v) for k,v in pairs])

def _sym(pd):
    if not pd: return None
    try:
        for k,v in parse_qsl(pd,keep_blank_values=True):
            if k=="optSymbol": return v
    except Exception: pass
    return None

def discover_batch20(context,production_page,output_root):
    root=Path(output_root)
    out=root/f"batch20_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True,exist_ok=False)
    page=context.new_page()
    events=[]; errors=[]
    before={"url":production_page.url,"closed":production_page.is_closed()}
    original=None
    def response_cb(response):
        try:
            req=response.request
            sym=_sym(req.post_data)
            if sym or "getDataForTotalPECEOIDiff" in response.url:
                rec={"url":response.url,"status":response.status,"method":req.method,
                     "resource_type":req.resource_type,"xhr_symbol":sym,
                     "post_data":_safe(req.post_data)}
                try:
                    body=response.body()
                    fn=f"response_{len(events)+1:04d}.bin"
                    (out/fn).write_bytes(body)
                    rec["body_file"]=fn
                    rec["body_length"]=len(body)
                except Exception as exc: rec["body_error"]=str(exc)
                events.append(rec)
        except Exception as exc: errors.append(f"response: {exc}")
    page.on("response",response_cb)
    page.on("requestfailed",lambda r: errors.append(f"requestfailed: {r.method} {r.url} :: {r.failure}"))
    page.on("pageerror",lambda e: errors.append(f"pageerror: {e}"))
    try:
        page.goto(TARGET_URL,wait_until="domcontentloaded",timeout=60000)
        page.wait_for_timeout(5000)
        sel=page.locator(SELECTOR)
        sel.wait_for(state="attached",timeout=30000)
        count=sel.locator("option").count()
        original=sel.input_value()
        symbols=[]
        for i in range(min(count,20)):
            v=sel.locator("option").nth(i).get_attribute("value")
            if v and v not in symbols: symbols.append(v)
        if len(symbols)<20: raise RuntimeError(f"Only {len(symbols)} usable symbols found")
        results=[]
        batch_started=datetime.now()
        for sym in symbols:
            before_n=len(events)
            sel.select_option(sym)
            page.wait_for_timeout(5000)
            changed=sel.input_value()
            new_events=events[before_n:]
            results.append({"symbol":sym,"dom_value":changed,
                            "xhr_symbols":[e.get("xhr_symbol") for e in new_events],
                            "event_count":len(new_events),
                            "body_lengths":[e.get("body_length") for e in new_events]})
        batch_finished=datetime.now()
        sel.select_option(original)
        page.wait_for_timeout(1000)
        manifest={"target_url":TARGET_URL,"selector":SELECTOR,"original_symbol":original,
                  "test_count":len(symbols),
                  "batch_started":batch_started.isoformat(),
                  "batch_finished":batch_finished.isoformat(),
                  "elapsed_seconds":(batch_finished-batch_started).total_seconds(),
                  "symbols_per_second":(len(symbols)/(batch_finished-batch_started).total_seconds()) if (batch_finished-batch_started).total_seconds()>0 else None,
                  "tested_symbols":symbols,"option_count":count,"results":results,
                  "events":events,"errors":errors,
                  "production_page_before":before,
                  "production_page_after":{"url":production_page.url,"closed":production_page.is_closed()}}
        (out/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
        return out
    finally:
        try: page.close()
        except Exception: pass
