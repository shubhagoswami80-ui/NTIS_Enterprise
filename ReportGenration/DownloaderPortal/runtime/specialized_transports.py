from __future__ import annotations
import asyncio, json, re, time, traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode
from openpyxl import Workbook

PECE_ENDPOINT_RE = re.compile(r"/getDataForTotalPECEOIDiff_Beta_v7_chart_v5\.php(?:\?|$)", re.I)
PECE_HEADERS = [
    "Time","Fut Price","Fut PriceChg (Day)","Fut PriceChg (Day) %","Fut PriceChg","Fut PriceChg %","VWAP","IV","Fut Volume","Tot Fut OI","Fut OIChg (Day)","Fut OIChg (Day) %","Fut OI Chg","Fut OI Chg %","Tot CEVol (Day)","Tot PEVol (Day)","Diff (PE-CE Volume)","CE Volume","PE Volume","PCR-Volume","TotCE OI","TotPE OI","PCR-OI","Diff(PE-CE OI)","Diff(PE-CE OI %)","Tot CE OIChg (Day)","Tot PE OIChg (Day)","CE OIChg/Vol %","PE OIChg/Vol %","PCR-OI Chg","Diff(PE-CE OI Chg)","Diff(PE-CE OI Chg %)","CE OI Chg","CE OI Chg %","PE OI Chg","PE OI Chg %","OI ChgTrend"
]
PACKED_PAIRS = {3:(2,3),4:(4,5),9:(10,11),10:(12,13),29:(32,33),30:(34,35)}
INDEX_SYMBOLS = {"NIFTY","BANKNIFTY","FINNIFTY","MIDCPNIFTY","NIFTYNXT50","NIFTYFPI","SENSEX","BANKEX"}

def _safe_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def _display(v, preserve_time=False):
    if v is None: return ""
    if isinstance(v,(int,float)): return v
    s=str(v).strip()
    return s if preserve_time else (s.split(":",1)[0].strip() if ":" in s else s)

def _packed(v):
    if v is None: return "", ""
    if isinstance(v,(int,float)): return v, ""
    p=str(v).split(":")
    return (p[0].strip() if p else "", p[1].strip() if len(p)>1 else "")

def _map_row(row):
    row=list(row[:31])+[""]*max(0,31-len(row)); out=[""]*len(PECE_HEADERS)
    out[0]=_display(row[0],True); out[1]=_display(row[1])
    for src,(a,b) in PACKED_PAIRS.items(): out[a],out[b]=_packed(row[src-1])
    for src,target in [(5,6),(6,7),(7,8),(8,9),(11,14),(12,15),(13,16),(14,17),(15,18),(16,19),(17,20),(18,21),(19,22),(20,23),(21,24),(22,25),(23,26),(24,27),(25,28),(26,29),(27,30),(28,31),(31,36)]: out[target]=_display(row[src-1])
    return out

def _validate(body):
    try: obj=json.loads(body or "")
    except Exception: return False,"invalid_or_non_json_response",0,None
    data=obj.get("aaData") if isinstance(obj,dict) else None
    if not isinstance(data,list): return False,"missing_or_invalid_aaData",0,obj
    if not data: return True,"no_data_available",0,obj
    if not all(isinstance(r,list) for r in data): return False,"aaData_contains_non_list_row",0,obj
    widths={len(r) for r in data}
    if len(widths)!=1: return False,"aaData_inconsistent_row_width",0,obj
    return True,f"ok_source_width_{next(iter(widths))}",len(data),obj

def _body(pairs,symbol): return urlencode([(k,symbol if k=="optSymbol" else v) for k,v in pairs])

def _allowed_symbols():
    path=Path("E:/NSE_Daily_Analysis/Output/market_master.csv")
    if not path.exists(): return None
    try:
        import csv
        with path.open(encoding="utf-8-sig",newline="") as fh: vals={str(r.get("Symbol","")).strip().upper() for r in csv.DictReader(fh)}
        vals.discard(""); vals-=INDEX_SYMBOLS
        return vals or None
    except Exception: return None

async def support_resistance(page, job):
    """Faithful async port of the known-working 8506 Support/Resistance path.

    Order is intentionally preserved:
      goto -> login check -> radio discovery/selection/verification -> SUBMIT
      -> wait -> Excel/download control discovery -> expect_download -> save.
    """
    started = time.perf_counter()
    name = str(job.get("name", job.get("id", "Support/Resistance")))
    timeout_ms = int(float(job.get("timeout_seconds", 180)) * 1000)
    wait_ms = int(float(job.get("wait_seconds", 2)) * 1000)

    await page.goto(job["url"], wait_until="domcontentloaded", timeout=timeout_ms)
    await page.wait_for_timeout(1000)

    if "login" in page.url.lower() or "signin" in page.url.lower():
        raise RuntimeError(f"{name}: login required")

    def norm(value):
        return " ".join(str(value or "").split()).strip().casefold()

    wanted = norm(job.get("selection", ""))
    selection_selector = str(job.get("selection_selector", "")).strip()

    async def verify_radio(radio):
        try:
            checked = bool(await radio.is_checked())
        except Exception:
            checked = bool(await radio.evaluate("el => !!el.checked"))
        if not checked:
            return False
        try:
            details = await radio.evaluate("""
                el => ({
                    value: el.value || "",
                    id: el.id || "",
                    name: el.name || "",
                    checked: !!el.checked
                })
            """)
            if not details.get("checked"):
                return False
            group_name = str(details.get("name") or "").strip()
            if group_name:
                selected = page.locator(
                    f'input[type="radio"][name="{group_name}"]:checked'
                )
                if await selected.count() != 1:
                    return False
        except Exception:
            return False
        return True

    async def activate_and_verify(radio):
        # Same native radio operation used by 8506. Try check first, then
        # click as fallback, and verify the actual DOM checked state.
        try:
            try:
                await radio.check(force=True)
            except Exception:
                await radio.click(force=True)
            await page.wait_for_timeout(300)
            if await verify_radio(radio):
                return True
            # Some legacy pages attach their handler to the label click.
            try:
                radio_id = await radio.get_attribute("id")
                if radio_id:
                    label = page.locator(f'label[for="{radio_id}"]').first
                    if await label.count():
                        await label.click(force=True)
                        await page.wait_for_timeout(300)
                        return await verify_radio(radio)
            except Exception:
                pass
        except Exception:
            pass
        return False

    if wanted or selection_selector:
        if selection_selector:
            radio = page.locator(selection_selector).first
            if await radio.count() == 0:
                raise RuntimeError(
                    f"{name}: selection selector not found: {selection_selector}"
                )
            if not await activate_and_verify(radio):
                raise RuntimeError(
                    f"{name}: configured radio could not be verified as selected"
                )
        else:
            radios = page.locator('input[type="radio"]')
            candidates = []

            for index in range(await radios.count()):
                radio = radios.nth(index)
                try:
                    details = await radio.evaluate("""
                        el => {
                            const label = el.id
                                ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`)
                                : null;
                            const parentLabel = el.closest("label");
                            const container = el.closest("label, td, th, div, span, li");
                            return {
                                value: el.value || "",
                                id: el.id || "",
                                name: el.name || "",
                                aria: el.getAttribute("aria-label") || "",
                                title: el.getAttribute("title") || "",
                                label: label ? label.innerText : "",
                                parentLabel: parentLabel ? parentLabel.innerText : "",
                                container: container ? container.innerText : "",
                                checked: !!el.checked
                            };
                        }
                    """)
                except Exception:
                    continue

                fields = [
                    details.get("value"), details.get("id"),
                    details.get("aria"), details.get("title"),
                    details.get("label"), details.get("parentLabel"),
                ]
                if any(wanted == norm(item) for item in fields):
                    candidates.append(radio)

            selected_ok = False
            for radio in candidates:
                if await activate_and_verify(radio):
                    selected_ok = True
                    break

            # Exact label fallback copied from the 8506 implementation.
            if not selected_ok:
                labels = page.locator("label")
                for index in range(await labels.count()):
                    label = labels.nth(index)
                    try:
                        if norm(await label.inner_text()) != wanted:
                            continue
                        target = label.locator('input[type="radio"]').first
                        if await target.count() and await activate_and_verify(target):
                            selected_ok = True
                            break
                        await label.click(force=True)
                        await page.wait_for_timeout(300)
                        target = label.locator('input[type="radio"]').first
                        if await target.count() and await verify_radio(target):
                            selected_ok = True
                            break
                    except Exception:
                        continue

            if not selected_ok:
                raise RuntimeError(
                    f"{name}: selection '{job.get('selection', '')}' not found or not checked; SUBMIT was not attempted"
                )

    # Verify immediately before SUBMIT whenever a radio was requested.
    if wanted:
        # Re-resolve by the exact same matching process so we never submit
        # while the browser is still showing the other default option.
        selected = page.locator('input[type="radio"]:checked')
        selected_text = []
        for i in range(await selected.count()):
            try:
                d = await selected.nth(i).evaluate("""
                    el => {
                        const l = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
                        const p = el.closest("label");
                        return [el.value||"", el.id||"", l?l.innerText:"", p?p.innerText:""];
                    }
                """)
                selected_text.extend(d)
            except Exception:
                pass
        if not any(wanted == norm(v) for v in selected_text):
            raise RuntimeError(
                f"{name}: requested '{job.get('selection')}' is not the selected radio immediately before SUBMIT"
            )

    submit_selector = job.get("submit_selector") or 'button:has-text("SUBMIT")'
    submit = page.locator(submit_selector).first
    if await submit.count() == 0:
        raise RuntimeError(f"{name}: Submit button not found")

    await submit.click(force=True)
    await page.wait_for_timeout(wait_ms)

    raw_root = str(job.get("output_root") or job.get("destination") or "").strip()
    if not raw_root:
        raise RuntimeError(f"{name}: output_root is not configured")
    destination = Path(raw_root)
    now = datetime.now()
    # TEST/live root is a root, never the final day folder. Always derive the
    # year/month/day hierarchy here so specialized reports match Daywise.
    if not (destination.name == now.strftime("%Y-%m-%d") and destination.parent.name.lower() == now.strftime("%B").lower()):
        destination = destination / str(now.year) / now.strftime("%B").lower() / now.strftime("%Y-%m-%d")
    if not str(destination):
        raise RuntimeError(f"{name}: destination folder is empty")
    destination.mkdir(parents=True, exist_ok=True)

    # Exact 8506 selector-first strategy, followed by the full fallback set.
    download_selector = job.get("download_selector") or 'button[title="Download Excel"]'
    button = page.locator(download_selector).first

    if await button.count() == 0:
        fallback_selectors = [
            'button[title*="Excel" i]',
            'a[title*="Excel" i]',
            '[role="button"][title*="Excel" i]',
            'button[aria-label*="Excel" i]',
            'a[aria-label*="Excel" i]',
            '[role="button"][aria-label*="Excel" i]',
            'button[title*="Download" i]',
            'a[title*="Download" i]',
            '[role="button"][title*="Download" i]',
            'button[aria-label*="Download" i]',
            'a[aria-label*="Download" i]',
            '[role="button"][aria-label*="Download" i]',
            'button[title*="Export" i]',
            'a[title*="Export" i]',
            '[role="button"][title*="Export" i]',
            'button[aria-label*="Export" i]',
            'a[aria-label*="Export" i]',
            '[role="button"][aria-label*="Export" i]',
        ]
        for candidate in fallback_selectors:
            locator = page.locator(candidate).first
            if await locator.count() > 0:
                button = locator
                break

    # Exact 8506 last-resort visible-control inspection.
    if await button.count() == 0:
        controls = page.locator('button, a, [role="button"]')
        for index in range(await controls.count()):
            candidate = controls.nth(index)
            try:
                details = await candidate.evaluate("""
                    el => ({
                        text: (el.innerText || "").trim(),
                        title: el.getAttribute("title") || "",
                        aria: el.getAttribute("aria-label") || "",
                        id: el.id || "",
                        cls: typeof el.className === "string" ? el.className : "",
                        html: (el.outerHTML || "").slice(0, 1500)
                    })
                """)
            except Exception:
                continue
            combined = " ".join(
                str(details.get(k, ""))
                for k in ("text", "title", "aria", "id", "cls", "html")
            ).casefold()
            if (
                "excel" in combined
                or "download" in combined
                or "export" in combined
                or ".xlsx" in combined
                or ".xls" in combined
            ):
                button = candidate
                break

    if await button.count() == 0:
        raise RuntimeError(
            f"{name}: Download button not found after SUBMIT. Configured selector: {download_selector}"
        )

    async with page.expect_download(timeout=30000) as event:
        await button.click(force=True)
    download = await event.value

    filename = download.suggested_filename or (
        f"{job['id']}_{datetime.now():%Y%m%d_%H%M%S}.xls"
    )

    if job.get("filename_rule") == "replace_leading_support_with_resistance" or str(job.get("selection", "")).strip().casefold() == "resistance":
        if filename.startswith("Support_Resistance_"):
            filename = "Resistance_" + filename[len("Support_Resistance_"):]
        while filename.startswith("Resistance_Resistance_"):
            filename = filename[len("Resistance_"):]
        if not filename.startswith("Resistance_"):
            filename = "Resistance_" + filename

    suffix = str(job.get("filename_suffix", "")).strip()
    if suffix:
        p = Path(filename)
        filename = f"{p.stem}_{suffix}{p.suffix}"

    p = Path(filename)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = destination / f"{p.stem}_{stamp}{p.suffix}"
    counter = 1
    while output.exists():
        output = destination / f"{p.stem}_{stamp}_{counter:02d}{p.suffix}"
        counter += 1

    await download.save_as(str(output))
    return {
        "status": "SUCCESS",
        "output": str(output),
        "processing_status": "COMPLETE",
        "download_status": "COMPLETE",
        "validation": "download saved",
        "duration_seconds": round(time.perf_counter() - started, 2),
    }

async def pece_xhr_batch(page, job):
    started=time.perf_counter(); dest=Path(job.get("destination") or job.get("output_root") or "")
    if not dest: raise RuntimeError("PE/CE output_root is not configured")
    now=datetime.now(); day=dest/str(now.year)/now.strftime("%B").lower()/now.strftime("%Y-%m-%d"); trace=dest/"_Trace"/str(now.year)/now.strftime("%B").lower()/now.strftime("%Y-%m-%d"); day.mkdir(parents=True,exist_ok=True); trace.mkdir(parents=True,exist_ok=True)
    cycle=now.strftime("%Y%m%d_%H%M%S"); manifest={"cycle_id":cycle,"status":"starting","integrity_gate":"HOLD","target_url":job["url"]}; mp=trace/f"PECE_{cycle}.json"; _safe_json(mp,manifest)
    captured=[]
    def on_response(resp):
        try:
            if resp.request.method.upper()=="POST" and PECE_ENDPOINT_RE.search(resp.url): captured.append(resp)
        except Exception: pass
    page.on("response",on_response)
    try:
        await page.goto(job["url"],wait_until="domcontentloaded",timeout=60000); await page.wait_for_selector("#optSymbol",timeout=30000)
        opts=await page.locator("#optSymbol option").evaluate_all("els=>els.map(e=>({value:e.value||'',text:(e.textContent||'').trim()})).filter(x=>x.value)")
        seen=set(); symbols=[]; allowed=_allowed_symbols()
        for s in opts:
            v=s["value"].upper()
            if s["value"] not in seen and v not in INDEX_SYMBOLS and (allowed is None or v in allowed): seen.add(s["value"]); symbols.append(s)
        manifest["symbol_count"]=len(symbols); manifest["symbols"]=[s["value"] for s in symbols]; _safe_json(trace/f"PECE_{cycle}_symbols.json",symbols)
        deadline=time.monotonic()+20
        while not captured and time.monotonic()<deadline: await page.wait_for_timeout(250)
        if not captured: await page.reload(wait_until="domcontentloaded",timeout=60000); await page.wait_for_timeout(5000)
        if not captured: raise RuntimeError("Native PE/CE XHR template was not captured")
        template=captured[-1]; pairs=parse_qsl(template.request.post_data or "",keep_blank_values=True)
        if not any(k=="optSymbol" for k,_ in pairs): raise RuntimeError("Captured PE/CE XHR has no optSymbol")
        if not PECE_ENDPOINT_RE.search(template.url): raise RuntimeError("Unexpected PE/CE XHR endpoint")
        manifest.update(template_endpoint=template.url,template_status=template.status)
        js='''async ({url,jobs,concurrency,timeoutMs,gapMs,jitterMs})=>{let next=0,nextStart=0,out=new Array(jobs.length);async function reserve(){let n=performance.now(),s=Math.max(n,nextStart);nextStart=s+gapMs;if(s>n)await new Promise(r=>setTimeout(r,s-n));}async function worker(){for(;;){let i=next++;if(i>=jobs.length)return;await reserve();if(jitterMs)await new Promise(r=>setTimeout(r,Math.random()*jitterMs));let j=jobs[i],t=performance.now(),c=new AbortController(),tm=setTimeout(()=>c.abort(),timeoutMs);try{let r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8","X-Requested-With":"XMLHttpRequest"},body:j.body,credentials:"include",cache:"no-store",signal:c.signal});out[i]={status:r.status,ok:r.ok,elapsed_ms:performance.now()-t,body:await r.text(),retry_after:r.headers.get("Retry-After")};}catch(e){out[i]={status:0,ok:false,elapsed_ms:performance.now()-t,error:String(e)};}finally{clearTimeout(tm);}}}await Promise.all(Array.from({length:Math.min(concurrency,jobs.length)},worker));return out}'''
        concurrency=max(1,min(12,int(job.get("concurrency",8)))); gap=max(250,min(20000,int(job.get("request_gap_ms",750)))); jitter=max(0,min(20000,int(job.get("jitter_ms",250)))); timeout=max(3000,min(30000,int(float(job.get("request_timeout_seconds",15))*1000))); retries=max(0,min(5,int(job.get("retry_count",job.get("retries",2))))); run_timeout=max(30,min(240,int(job.get("run_timeout_seconds",job.get("timeout_seconds",180)))))
        pending=list(symbols); final={}; hard=time.monotonic()+run_timeout
        for attempt in range(1,retries+2):
            if not pending or time.monotonic()>=hard: break
            if attempt>1: await asyncio.sleep(min(15*(2**(attempt-2)),max(0,hard-time.monotonic())))
            raw=[]
            for start in range(0,len(pending),concurrency):
                if time.monotonic()>=hard: break
                batch=pending[start:start+concurrency]
                raw.extend(await page.evaluate(js,{"url":template.url,"jobs":[{"body":_body(pairs,s["value"])} for s in batch],"concurrency":concurrency,"timeoutMs":timeout,"gapMs":gap,"jitterMs":jitter}))
            nxt=[]
            for sym,res in zip(pending,raw):
                if res.get("ok"): valid,reason,rows,obj=_validate(res.get("body",""))
                else: valid,reason,rows,obj=False,res.get("error","http_error"),0,None
                rec={"symbol":sym["value"],"attempt":attempt,"http_status":res.get("status"),"elapsed_ms":round(float(res.get("elapsed_ms",0)),1),"reason":reason,"rows":rows,"valid":valid,"retry_after":res.get("retry_after")}
                final[sym["value"]]=rec|({"object":obj} if valid else {}); nxt.append(sym) if not valid else None
            pending=nxt
            if sum(1 for r in final.values() if r.get("http_status")==429)>=int(job.get("max_429_failures",3)): break
        ordered=[final.get(s["value"],{"symbol":s["value"],"valid":False,"reason":"run_timeout" if time.monotonic()>=hard else "no_result"}) for s in symbols]
        valid=[r for r in ordered if r.get("valid")]; rows=[]
        for r in valid:
            for n,row in enumerate(r["object"].get("aaData",[]),1): rows.append(_map_row(row)+[r["symbol"],cycle,n])
        manifest.update(completed_count=len(ordered),success_count=len(valid),failed_count=len(ordered)-len(valid),missing_symbols=[r["symbol"] for r in ordered if not r.get("valid")],elapsed_seconds=round(time.perf_counter()-started,2))
        if rows:
            out=day/f"PECE_{cycle}.xlsx"; wb=Workbook(); ws=wb.active; ws.title="Data"; ws.append(PECE_HEADERS+["Symbol","Snapshot","Response_Row"])
            for row in rows: ws.append(row)
            sw=wb.create_sheet("Status"); keys=sorted({k for r in ordered for k in r}); sw.append(keys)
            for r in ordered: sw.append([r.get(k) for k in keys])
            rw=wb.create_sheet("Run"); rw.append(["Field","Value"])
            for k,v in manifest.items(): rw.append([k,json.dumps(v) if isinstance(v,(dict,list)) else v])
            wb.save(out); manifest["snapshot_file"]=str(out); manifest["integrity_gate"]="PASS" if not manifest["failed_count"] else "PARTIAL"; manifest["status"]="completed"
        else: manifest["status"]="completed_with_gaps"
        _safe_json(mp,manifest)
        return {"status":"SUCCESS" if manifest.get("integrity_gate")=="PASS" else "PARTIAL","processing_status":manifest.get("integrity_gate","HOLD"),"output":manifest.get("snapshot_file",""),"validation":f"{manifest['success_count']}/{manifest['completed_count']} valid; {manifest['failed_count']} failed","error_category":"" if not manifest['failed_count'] else "PARTIAL_DATA","duration_seconds":manifest['elapsed_seconds']}
    except Exception as exc:
        manifest.update(status="failed",fatal_error=repr(exc),traceback=traceback.format_exc()); _safe_json(mp,manifest); raise
