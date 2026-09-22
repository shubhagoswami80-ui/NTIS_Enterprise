from __future__ import annotations
import json, re, time, traceback, shutil
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
ENDPOINT_RE = re.compile(r"/getDataForTotalPECEOIDiff_Beta_v7_chart_v5\.php(?:\?|$)", re.I)

def _safe_post_data(post_data: str) -> str:
    pairs = parse_qsl(post_data or "", keep_blank_values=True)
    secret = {"sessionid","phpsessid","cf_clearance","password","passwd","token"}
    return urlencode([(k, "<redacted>" if k.lower() in secret or "session" in k.lower() else v)
                      for k,v in pairs])

def _rows(body):
    try:
        obj=json.loads(body)
        return len(obj.get("aaData") or []) if isinstance(obj,dict) else 0
    except Exception:
        return 0

def run_full_220(context, output_root, wait_first=10.0, concurrency=6):
    out=Path(output_root)/f"batch220_native_{time.strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=False)
    page=context.new_page()
    manifest={"status":"running","target_url":TARGET_URL,"started_at":time.strftime("%Y-%m-%dT%H:%M:%S"),
              "results":[],"errors":[]}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    try:
        page.goto(TARGET_URL,wait_until="domcontentloaded",timeout=60000)
        page.wait_for_selector("#optSymbol",timeout=30000)
        symbols=page.locator("#optSymbol option").evaluate_all(
            "(els)=>els.map(e=>({value:e.value,text:(e.textContent||'').trim()})).filter(x=>x.value)")
        seen=set(); symbols=[x for x in symbols if not (x["value"] in seen or seen.add(x["value"]))]
        manifest["symbol_count"]=len(symbols)
        manifest["symbols"]=symbols
        (out/"symbols.json").write_text(json.dumps(symbols,indent=2),encoding="utf-8")
        if len(symbols)<200:
            raise RuntimeError(f"Expected about 220 stocks, found {len(symbols)}")

        captured={}
        def on_response(resp):
            if ENDPOINT_RE.search(resp.url) and resp.request.method=="POST" and "resp" not in captured:
                captured["resp"]=resp
        page.on("response",on_response)
        page.reload(wait_until="domcontentloaded",timeout=60000)
        page.wait_for_timeout(int(wait_first*1000))
        resp=captured.get("resp")
        if not resp:
            raise RuntimeError("Native PE/CE XHR template was not captured")
        req=resp.request
        post=req.post_data or ""
        if not post:
            raise RuntimeError("Captured PE/CE XHR has no POST data")
        endpoint=resp.url
        manifest["template_endpoint"]=endpoint
        manifest["template_post_data"]=_safe_post_data(post)

        base=parse_qsl(post,keep_blank_values=True)
        def body_for(sym):
            return urlencode([(k,sym if k=="optSymbol" else v) for k,v in base])

        js="""async ({url,bodies,concurrency})=>{
          let next=0, results=new Array(bodies.length);
          async function worker(){
            while(true){
              const i=next++; if(i>=bodies.length) return;
              const t=performance.now();
              try{
                const r=await fetch(url,{method:'POST',
                  headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
                  body:bodies[i],credentials:'include',cache:'no-store'});
                const text=await r.text();
                results[i]={status:r.status,ok:r.ok,ms:performance.now()-t,body:text};
              }catch(e){results[i]={status:0,ok:false,ms:performance.now()-t,error:String(e)}}
            }
          }
          await Promise.all(Array.from({length:Math.min(concurrency,bodies.length)},worker));
          return results;
        }"""

        started=time.perf_counter()
        all_results=[]
        for pos in range(0,len(symbols),20):
            batch=symbols[pos:pos+20]
            results=page.evaluate(js,{"url":endpoint,"bodies":[body_for(x["value"]) for x in batch],"concurrency":concurrency})
            for sym,r in zip(batch,results):
                rec={"symbol":sym["value"],"text":sym["text"],"status":r.get("status"),
                     "ok":r.get("ok",False),"elapsed_ms":round(r.get("ms",0),1),
                     "rows":_rows(r.get("body",""))}
                if rec["ok"] and rec["rows"]>0:
                    fn=out/f"{len(all_results)+1:03d}_{re.sub(r'[^A-Za-z0-9_.-]','_',sym['value'])}.json"
                    fn.write_text(r.get("body",""),encoding="utf-8")
                    rec["file"]=fn.name
                else:
                    rec["error"]=r.get("error","HTTP/non-data response")
                    manifest["errors"].append(rec.copy())
                all_results.append(rec)
                elapsed=time.perf_counter()-started
                manifest.update(completed_count=len(all_results),
                                success_count=sum(1 for x in all_results if x.get("file")),
                                failed_count=sum(1 for x in all_results if not x.get("file")),
                                elapsed_seconds=round(elapsed,2),
                                symbols_per_second=round(len(all_results)/max(elapsed,.001),3),
                                results=all_results)
                (out/"progress.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

        import pandas as pd
        status_df=pd.DataFrame(all_results)
        data=[]
        for rec in all_results:
            if rec.get("file"):
                obj=json.loads((out/rec["file"]).read_text(encoding="utf-8"))
                for row in obj.get("aaData") or []:
                    data.append({"Symbol":rec["symbol"],"Data":json.dumps(row,separators=(",",":"))})
        data_df=pd.DataFrame(data)
        xlsx=out/"PECE_220_Snapshot.xlsx"
        with pd.ExcelWriter(xlsx,engine="openpyxl") as writer:
            status_df.to_excel(writer,index=False,sheet_name="Stock_Status")
            data_df.to_excel(writer,index=False,sheet_name="PECE_Data")
        latest=out.parent/"Latest_PECE_220.xlsx"
        shutil.copy2(xlsx,latest)
        elapsed=time.perf_counter()-started
        manifest.update(status="completed",finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                        elapsed_seconds=round(elapsed,2),
                        symbols_per_second=round(len(all_results)/max(elapsed,.001),3),
                        projected_220_seconds=round(220/(len(all_results)/max(elapsed,.001)),2),
                        excel=xlsx.name,latest=latest.name)
        (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        return manifest
    except Exception as exc:
        manifest.update(status="failed",fatal_error=repr(exc),traceback=traceback.format_exc())
        (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        raise
    finally:
        try: page.close()
        except Exception: pass
