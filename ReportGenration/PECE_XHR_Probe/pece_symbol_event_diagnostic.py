from pathlib import Path
import json
from datetime import datetime
from urllib.parse import parse_qsl, urlencode

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
SYMBOL_SELECTOR = "#optSymbol"

def _safe_post_data(post_data):
    if not post_data:
        return None
    try:
        pairs=parse_qsl(post_data,keep_blank_values=True)
    except Exception:
        return "[REDACTED_UNPARSEABLE_POST_DATA]"
    sensitive={"sessionid","phpsessid","token","password","passwd","username","user_name","userpassword","cf_clearance"}
    return urlencode([(k,"[REDACTED]" if k.strip().lower() in sensitive else v) for k,v in pairs])

def _xhr_symbol(post_data):
    if not post_data: return None
    try:
        for k,v in parse_qsl(post_data,keep_blank_values=True):
            if k=="optSymbol": return v
    except Exception: pass
    return None

def discover_symbol_change(context, production_page, output_root, wait_seconds=6.0):
    output_root=Path(output_root)
    out=output_root/f"symbol_change_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True,exist_ok=False)
    page=context.new_page()
    events=[]; errors=[]
    before={"url":production_page.url,"closed":production_page.is_closed()}
    def on_response(response):
        try:
            req=response.request
            symbol=_xhr_symbol(req.post_data)
            if symbol or "getDataForTotalPECEOIDiff" in response.url:
                rec={"url":response.url,"status":response.status,"resource_type":req.resource_type,
                     "method":req.method,"xhr_symbol":symbol,
                     "post_data":_safe_post_data(req.post_data)}
                try:
                    body=response.body()
                    fn=f"response_{len(events)+1:04d}.bin"
                    (out/fn).write_bytes(body)
                    rec["body_file"]=fn; rec["body_length"]=len(body)
                except Exception as exc: rec["body_error"]=str(exc)
                events.append(rec)
        except Exception as exc: errors.append(f"response handler: {exc}")
    def on_requestfailed(request):
        errors.append(f"requestfailed: {request.method} {request.url} :: {request.failure}")
    def on_pageerror(exc): errors.append(f"pageerror: {exc}")
    page.on("response",on_response); page.on("requestfailed",on_requestfailed); page.on("pageerror",on_pageerror)
    try:
        page.goto(TARGET_URL,wait_until="domcontentloaded",timeout=60000)
        page.wait_for_timeout(int(wait_seconds*1000))
        selector=page.locator(SYMBOL_SELECTOR)
        selector.wait_for(state="attached",timeout=30000)
        option_count=selector.locator("option").count()
        original=selector.input_value()
        options=[]
        for i in range(min(option_count,300)):
            opt=selector.locator("option").nth(i)
            options.append({"text":opt.inner_text(),"value":opt.get_attribute("value")})
        test=next((x["value"] for x in options if x["value"] and x["value"]!=original),None)
        if not test: raise RuntimeError("No alternate symbol found in #optSymbol")
        selector.select_option(test)
        page.wait_for_timeout(int(wait_seconds*1000))
        changed=selector.input_value()
        selector.select_option(original)
        page.wait_for_timeout(1000)
        restored=selector.input_value()
        manifest={"target_url":TARGET_URL,"symbol_selector":SYMBOL_SELECTOR,
                  "original_symbol":original,"test_symbol":test,"changed_dom_value":changed,
                  "restored_dom_value":restored,"option_count":option_count,"options":options,
                  "events":events,"errors":errors,
                  "production_page_before":before,
                  "production_page_after":{"url":production_page.url,"closed":production_page.is_closed()}}
        (out/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
        return out
    finally:
        try: page.close()
        except Exception: pass
