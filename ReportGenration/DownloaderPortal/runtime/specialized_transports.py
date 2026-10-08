from __future__ import annotations
import asyncio, json, re, time, traceback
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode
from openpyxl import Workbook
from .optionchain_daily_universe import get_or_create_daily_universe

PECE_ENDPOINT_RE = re.compile(
    r"/getDataForTotalPECEOIDiff_Beta_v7_chart_v5(?:_1)?\.php(?:\?|$)", re.I
)
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
def _body(pairs,symbol,state):
    expiry = str(state.get("expiry") or "").strip()
    closest = str(state.get("closestPrice") or "").strip()
    if not expiry or not closest:
        raise RuntimeError(f"Missing authoritative TopRightDetails state for {symbol}")

    out = []
    for key, value in pairs:
        if key == "optSymbol":
            value = symbol
        elif key == "optExpDate":
            value = expiry
        elif key == "closestPrice":
            value = closest
        elif key == "save_data":
            try:
                save_obj = json.loads(value)
            except Exception as exc:
                raise RuntimeError(f"Native save_data is not valid JSON for {symbol}") from exc
            save_obj["symbol"] = symbol
            save_obj["exp_date"] = expiry
            value = json.dumps(save_obj, separators=(",", ":"), ensure_ascii=False)
        out.append((key, value))
    return urlencode(out)
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

    raw_destination = str(job.get("output_root") or job.get("destination") or "").strip()
    if not raw_destination:
        raise RuntimeError(f"{name}: destination folder is empty")
    root = Path(raw_destination)
    now = datetime.now()
    month_folder = now.strftime("%B") + now.strftime("%y")
    day_folder = now.strftime("%Y-%m-%d")
    destination = root / month_folder / day_folder
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
    started=time.perf_counter(); dest=Path(job.get("output_root") or job.get("destination") or "")
    if not dest: raise RuntimeError("PE/CE output_root is not configured")
    now=datetime.now()
    year_folder=now.strftime("%Y")
    month_folder=now.strftime("%B").lower()
    day_folder=now.strftime("%Y-%m-%d")
    day=dest/year_folder/month_folder/day_folder
    trace=dest/"_Trace"/year_folder/month_folder/day_folder
    day.mkdir(parents=True,exist_ok=True); trace.mkdir(parents=True,exist_ok=True)
    cycle=now.strftime("%Y%m%d_%H%M%S"); manifest={"cycle_id":cycle,"status":"starting","integrity_gate":"HOLD","target_url":job["url"]}; mp=trace/f"PECE_{cycle}.json"; _safe_json(mp,manifest)
    captured=[]
    def on_response(resp):
        try:
            if resp.request.method.upper()=="POST" and PECE_ENDPOINT_RE.search(resp.url): captured.append(resp)
        except Exception: pass
    page.on("response",on_response)
    try:
        await page.goto(job["url"],wait_until="domcontentloaded",timeout=60000); await page.wait_for_selector("#optSymbol",timeout=30000)
        today = datetime.now().date()
        output_root = job.get("output_root") or job.get("destination")
        if not output_root:
            raise RuntimeError("PE/CE output_root is not configured")

        # PE/CE consumes the same authoritative daily universe used by
        # Option Chain. Existing day's universe is reused; discovery occurs
        # only when that day's authoritative universe does not exist.
        symbols_values, universe_meta, universe_path = await get_or_create_daily_universe(
            page,
            output_root,
            today,
            force_refresh=False,
        )
        if not symbols_values:
            raise RuntimeError("PE/CE authoritative daily universe returned zero symbols")

        symbols = [{"value": s, "text": s} for s in symbols_values]
        manifest["universe_source_state"] = universe_meta.get("source_state", "")
        manifest["universe_symbol_count"] = len(symbols_values)
        manifest["universe_path"] = str(universe_path or "")
        manifest["symbol_count"]=len(symbols); manifest["symbols"]=[s["value"] for s in symbols]; _safe_json(trace/f"PECE_{cycle}_symbols.json",symbols)
        deadline=time.monotonic()+20
        while not captured and time.monotonic()<deadline: await page.wait_for_timeout(250)
        if not captured: await page.reload(wait_until="domcontentloaded",timeout=60000); await page.wait_for_timeout(5000)
        if not captured: raise RuntimeError("Native PE/CE XHR template was not captured")
        template=captured[-1]; pairs=parse_qsl(template.request.post_data or "",keep_blank_values=True)
        if not any(k=="optSymbol" for k,_ in pairs): raise RuntimeError("Captured PE/CE XHR has no optSymbol")
        if not PECE_ENDPOINT_RE.search(template.url): raise RuntimeError("Unexpected PE/CE XHR endpoint")
        manifest.update(template_endpoint=template.url,template_status=template.status)
        js='''async ({url,jobs,concurrency,timeoutMs,gapMs,jitterMinMs,jitterMaxMs})=>{let next=0,nextStart=0,out=new Array(jobs.length);async function reserve(){let n=performance.now(),s=Math.max(n,nextStart);nextStart=s+gapMs;if(s>n)await new Promise(r=>setTimeout(r,s-n));}async function worker(){for(;;){let i=next++;if(i>=jobs.length)return;await reserve();let span=Math.max(0,jitterMaxMs-jitterMinMs),jitter=jitterMinMs+(span?Math.random()*span:0);if(jitter)await new Promise(r=>setTimeout(r,jitter));let j=jobs[i],t=performance.now(),c=new AbortController(),tm=setTimeout(()=>c.abort(),timeoutMs);try{let r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8","X-Requested-With":"XMLHttpRequest"},body:j.body,credentials:"include",cache:"no-store",signal:c.signal});out[i]={status:r.status,ok:r.ok,elapsed_ms:performance.now()-t,body:await r.text(),retry_after:r.headers.get("Retry-After")};}catch(e){out[i]={status:0,ok:false,elapsed_ms:performance.now()-t,error:String(e)};}finally{clearTimeout(tm);}}}await Promise.all(Array.from({length:Math.min(concurrency,jobs.length)},worker));return out}'''
        # PECE_AUTHORITATIVE_STATE_V2
        TOPRIGHT_URL="https://www.icharts.in/opt/hcharts/stx8req/php/getTopRightDetails.php"
        topright_js='''async ({url,symbols,concurrency,timeoutMs,requestGapMs})=>{
            let next=0,nextStart=0,out=new Array(symbols.length);
            async function reserve(){
                let n=performance.now(),s=Math.max(n,nextStart);
                nextStart=s+requestGapMs;
                if(s>n) await new Promise(r=>setTimeout(r,s-n));
            }
            async function worker(){
                for(;;){
                    let i=next++;
                    if(i>=symbols.length) return;
                    await reserve();
                    let symbol=symbols[i],t=performance.now(),ctl=new AbortController();
                    let tm=setTimeout(()=>ctl.abort(),timeoutMs);
                    try{
                        let body=new URLSearchParams({
                            optSymbol:symbol,
                            optExpDate:"undefined",
                            monthlyExpDate:"undefined",
                            Presentday:"undefined",
                            Prevday:"undefined",
                            rdDataType:"latest",
                            txtDate:"undefined",
                            defaultDate:"undefined",
                            e:"1"
                        }).toString();
                        let r=await fetch(url,{
                            method:"POST",
                            headers:{
                                "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
                                "X-Requested-With":"XMLHttpRequest"
                            },
                            body,
                            credentials:"include",
                            cache:"no-store",
                            signal:ctl.signal
                        });
                        let text=await r.text(),obj=null;
                        try{obj=JSON.parse(text);}catch(e){}
                        out[i]={symbol,status:r.status,ok:r.ok,
                            elapsed_ms:performance.now()-t,object:obj,body:text};
                    }catch(e){
                        out[i]={symbol,status:0,ok:false,
                            elapsed_ms:performance.now()-t,error:String(e)};
                    }finally{clearTimeout(tm);}
                }
            }
            await Promise.all(
                Array.from({length:Math.min(concurrency,symbols.length)},worker)
            );
            return out;
        }'''

        async def _resolve_authoritative_states(batch):
            symbols_for_state=[s["value"] for s in batch]
            raw_states=await page.evaluate(
                topright_js,
                {
                    "url":TOPRIGHT_URL,
                    "symbols":symbols_for_state,
                    "concurrency":8,
                    "timeoutMs":5000,
                    "requestGapMs":150
                }
            )
            states={}
            failures=[]
            for item in raw_states:
                symbol=item.get("symbol")
                if not item.get("ok"):
                    failures.append(
                        f"{symbol}: HTTP {item.get('status') or 0} "
                        f"{item.get('error') or 'top-right request failed'}"
                    )
                    continue
                obj=item.get("object")
                futures=obj.get("futures") if isinstance(obj,dict) else None
                iv=obj.get("iv") if isinstance(obj,dict) else None
                if (
                    not isinstance(futures,list) or len(futures)<2
                    or str(futures[0]).strip().upper()!=str(symbol).upper()
                    or not isinstance(iv,list) or len(iv)<3
                ):
                    failures.append(f"{symbol}: invalid TopRightDetails state")
                    continue
                expiry=str(futures[1]).strip()
                closest=str(iv[2]).strip()
                if not expiry or not closest:
                    failures.append(f"{symbol}: missing expiry/closestPrice")
                    continue
                states[symbol]={"expiry":expiry,"closestPrice":closest}
            if failures:
                raise RuntimeError(
                    "Authoritative symbol-state acquisition failed: "
                    + " | ".join(failures)
                )
            return states

        states=await _resolve_authoritative_states(pending)
        concurrency=max(1,min(12,int(job.get("concurrency",8))))
        gap=max(250,min(20000,int(job.get("request_start_gap_ms",job.get("request_gap_ms",750)))))
        jitter_min=max(0,min(15000,int(job.get("request_jitter_min_ms",job.get("jitter_min_ms",250)))))
        jitter_max=max(jitter_min,min(20000,int(job.get("request_jitter_max_ms",job.get("jitter_max_ms",750)))))
        retry_backoff_ms=max(15000,min(180000,int(job.get("retry_backoff_ms",30000))))
        retry_after_cap_ms=max(30000,min(300000,int(job.get("retry_after_cap_ms",120000))))
        batch_gap_ms=max(1000,min(60000,int(job.get("batch_gap_ms",3000))))
        timeout=max(3000,min(30000,int(float(job.get("request_timeout_seconds",15))*1000)))
        retries=max(0,min(5,int(job.get("retries",job.get("retry_count",2)))))
        # PECE_FULL_UNIVERSE_FINAL_429_PATCH_V1
        run_timeout=max(30,min(330,int(job.get("run_timeout_seconds",job.get("timeout_seconds",300)))))
        pending=list(symbols); final={}; hard=time.monotonic()+run_timeout
        for attempt in range(1,retries+2):
            if not pending or time.monotonic()>=hard: break
            if attempt>1:
                retry_wait_ms=retry_backoff_ms*(2**(attempt-2))
                for previous in final.values():
                    if previous.get("http_status")==429:
                        retry_after=previous.get("retry_after_seconds")
                        if retry_after is not None:
                            retry_wait_ms=max(
                                retry_wait_ms,
                                int(min(retry_after*1000,retry_after_cap_ms)),
                            )
                remaining=max(0,hard-time.monotonic())
                if remaining<=0: break
                await asyncio.sleep(min(retry_wait_ms/1000.0,remaining))
                if time.monotonic()>=hard: break

            raw=[]
            if time.monotonic() < hard:
                raw = await page.evaluate(
                    js,
                    {
                        "url":template.url,
                        "jobs":[{"body":_body(pairs,s["value"],states[s["value"]])} for s in pending],
                        "concurrency":concurrency,
                        "timeoutMs":timeout,
                        "gapMs":gap,
                        "jitterMinMs":jitter_min,
                        "jitterMaxMs":jitter_max
                    }
                )

            nxt=[]
            processed_count=min(len(raw),len(pending))

            for sym,res in zip(pending[:processed_count],raw):
                if res.get("ok"):
                    valid,reason,rows,obj=_validate(res.get("body",""))
                else:
                    valid,reason,rows,obj=False,res.get("error","http_error"),0,None

                retry_after=res.get("retry_after")
                retry_after_seconds=None
                if retry_after:
                    try:
                        retry_after_seconds=max(0,float(retry_after))
                    except (TypeError,ValueError):
                        try:
                            retry_dt=parsedate_to_datetime(retry_after)
                            if retry_dt.tzinfo is None:
                                retry_dt=retry_dt.replace(tzinfo=timezone.utc)
                            retry_after_seconds=max(
                                0,
                                (retry_dt-datetime.now(timezone.utc)).total_seconds(),
                            )
                        except Exception:
                            retry_after_seconds=None

                rec={
                    "symbol":sym["value"],
                    "attempt":attempt,
                    "http_status":res.get("status"),
                    "elapsed_ms":round(float(res.get("elapsed_ms",0)),1),
                    "reason":reason,
                    "rows":rows,
                    "valid":valid,
                    "retry_after":retry_after,
                    "retry_after_seconds":retry_after_seconds
                }
                final[sym["value"]]=rec|({"object":obj} if valid else {})

                if not valid and attempt<=retries:
                    nxt.append(sym)

            pending=nxt

            # PECE_FULL_UNIVERSE_FINAL_429_PATCH_V1
            # Do not permanently stop on cumulative 429s.
            # Pending symbols remain pending and use Retry-After/backoff.
            attempt_429=sum(1 for r in final.values() if r.get("attempt")==attempt and r.get("http_status")==429)
            if attempt_429>=int(job.get("max_429_failures",3)) and pending:
                manifest["last_attempt_429_count"]=attempt_429
                manifest["rate_limit_action"]="retry_pending_with_retry_after_backoff"

        # PECE_NATIVE_SYMBOL_FALLBACK_V1
        native_failed = [s for s in symbols if not bool(final.get(s["value"], {}).get("valid"))]
        native_timeout_ms = max(5000, min(30000, int(job.get("native_symbol_fallback_timeout_ms", 12000))))
        native_recovered = 0
        if native_failed and time.monotonic() < hard:
            native_responses = []
            def _on_native_symbol_response(resp):
                try:
                    if resp.request.method.upper() == "POST" and PECE_ENDPOINT_RE.search(resp.url):
                        native_responses.append(resp)
                except Exception:
                    pass
            page.on("response", _on_native_symbol_response)
            try:
                for sym in native_failed:
                    if time.monotonic() >= hard:
                        break
                    symbol = str(sym["value"]).strip()
                    native_responses.clear()
                    select = page.locator("#optSymbol")
                    if await select.count() == 0:
                        break
                    try:
                        await select.select_option(value=symbol)
                    except Exception:
                        try:
                            await page.evaluate(
                                "sym => { const el=document.querySelector('#optSymbol'); if(!el)return false; el.value=sym; el.dispatchEvent(new Event('change',{bubbles:true})); return true; }",
                                symbol,
                            )
                        except Exception:
                            continue
                    deadline_native = time.monotonic() + native_timeout_ms / 1000.0
                    matched = None
                    while time.monotonic() < deadline_native and time.monotonic() < hard:
                        for resp in list(native_responses):
                            try:
                                request_pairs = parse_qsl(resp.request.post_data or "", keep_blank_values=True)
                                request_symbol = next((str(v).strip().upper() for k,v in request_pairs if k=="optSymbol"), "")
                                if request_symbol != symbol.upper():
                                    continue
                                body = await resp.text()
                                valid2, reason2, rows2, obj2 = _validate(body)
                                if valid2:
                                    matched = {"symbol":symbol,"attempt":int(final.get(symbol,{}).get("attempt",1))+1,
                                               "http_status":resp.status,"elapsed_ms":0.0,"reason":f"native_{reason2}",
                                               "rows":rows2,"valid":True,"retry_after":resp.headers.get("retry-after"),
                                               "object":obj2}
                                    break
                            except Exception:
                                continue
                        if matched:
                            break
                        await page.wait_for_timeout(250)
                    if matched:
                        final[symbol] = matched
                        native_recovered += 1
            finally:
                try:
                    page.remove_listener("response", _on_native_symbol_response)
                except Exception:
                    pass
        manifest["native_symbol_fallback_attempted"] = len(native_failed)
        manifest["native_symbol_fallback_recovered"] = native_recovered
        manifest["native_symbol_fallback_unrecovered"] = [s["value"] for s in symbols if not bool(final.get(s["value"],{}).get("valid"))]

        ordered=[final.get(s["value"],{"symbol":s["value"],"valid":False,"reason":"run_timeout" if time.monotonic()>=hard else "no_result"}) for s in symbols]
        valid=[r for r in ordered if r.get("valid")]; rows=[]
        for r in valid:
            for n,row in enumerate(r["object"].get("aaData",[]),1): rows.append(_map_row(row)+[r["symbol"],cycle,n])
        manifest.update(completed_count=len(ordered),success_count=len(valid),failed_count=len(ordered)-len(valid),missing_symbols=[r["symbol"] for r in ordered if not r.get("valid")],elapsed_seconds=round(time.perf_counter()-started,2))
        if rows:
            out=day/f"PECE_{cycle}.xlsx"; wb=Workbook(); ws=wb.active; ws.title="Data"; ws.append(PECE_HEADERS+["Symbol","Snapshot","Response_Row"])
            for row in rows: ws.append(row)
            sw=wb.create_sheet("Status"); status_keys=["symbol","attempt","http_status","elapsed_ms","reason","rows","valid","retry_after","retry_after_seconds"]; sw.append(status_keys)
            for r in ordered: sw.append([r.get(k) for k in status_keys])
            manifest["snapshot_file"]=str(out)
            manifest["integrity_gate"]="PASS" if not manifest["failed_count"] else "PARTIAL"
            manifest["status"]="completed"
            rw=wb.create_sheet("Run"); rw.append(["Field","Value"])
            for k,v in manifest.items(): rw.append([k,json.dumps(v) if isinstance(v,(dict,list)) else v])
            wb.save(out)
        else:
            # PECE_FULL_UNIVERSE_FINAL_429_PATCH_V1
            # Always create an audit workbook. Never fabricate Data rows.
            out=day/f"PECE_{cycle}.xlsx"
            wb=Workbook()
            ws=wb.active; ws.title="Data"
            ws.append(PECE_HEADERS+["Symbol","Snapshot","Response_Row"])
            sw=wb.create_sheet("Status")
            status_keys=["symbol","attempt","http_status","elapsed_ms","reason","rows","valid","retry_after","retry_after_seconds"]
            sw.append(status_keys)
            for r in ordered: sw.append([r.get(k) for k in status_keys])
            manifest["snapshot_file"]=str(out)
            manifest["integrity_gate"]="HOLD"
            manifest["status"]="completed_with_gaps"
            manifest["publish_blocked"]=True
            rw=wb.create_sheet("Run"); rw.append(["Field","Value"])
            for k,v in manifest.items(): rw.append([k,json.dumps(v) if isinstance(v,(dict,list)) else v])
            wb.save(out)
        _safe_json(mp,manifest)
        return {"status":"SUCCESS" if manifest.get("integrity_gate")=="PASS" else "PARTIAL","processing_status":manifest.get("integrity_gate","HOLD"),"output":manifest.get("snapshot_file",""),"validation":f"{manifest['success_count']}/{manifest['completed_count']} valid; {manifest['failed_count']} failed","error_category":"" if not manifest['failed_count'] else "PARTIAL_DATA","duration_seconds":manifest['elapsed_seconds']}
    except Exception as exc:
        manifest.update(status="failed",fatal_error=repr(exc),traceback=traceback.format_exc()); _safe_json(mp,manifest); raise
