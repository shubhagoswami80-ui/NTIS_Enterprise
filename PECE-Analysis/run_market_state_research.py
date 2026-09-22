from pathlib import Path
import re,json,sys
import numpy as np,pandas as pd
P={"daywise":"Daywise_Price_and_OI_Summary_*.xlsx","ivr_ivp":"IVR-IVP_*_Report_*.xlsx","resistance":"Resistance_*_Scan_*.xlsx","sector":"Sector_Summary_*_Report_*.xlsx","support_resistance":"Support_Resistance_*_Scan_*.xlsx","spikes":"VolumeAndOISpikesScans_*_Report_*.xlsx"}
def ts(p):
 m=re.search(r"(20\d{6})_(\d{6})",Path(p).name); return pd.to_datetime(m.group(1)+m.group(2),format="%Y%m%d%H%M%S") if m else pd.NaT
def rd(p):
 d=pd.read_excel(p); d.columns=[str(x).strip() for x in d.columns]; return d
def discover(root):
 root=Path(root); cycles=[]; audit=[]
 for day in sorted(x for x in root.iterdir() if x.is_dir() and re.fullmatch(r"20\d\d-\d\d-\d\d",x.name)):
  fs={k:sorted(day.glob(v)) for k,v in P.items()}
  for k,arr in fs.items():
   for f in arr: audit.append({"date":day.name,"report":k,"file":f.name,"timestamp":ts(f),"rows":len(rd(f))})
  for dw in fs["daywise"]:
   t=ts(dw); chosen={"daywise":dw}; ds=[]
   for k in P:
    if k=="daywise": continue
    opts=[(f,abs((ts(f)-t).total_seconds())) for f in fs[k] if pd.notna(ts(f))]
    if not opts: break
    f,delta=min(opts,key=lambda z:z[1]); chosen[k]=f; ds.append(delta)
   if len(chosen)==6 and max(ds)<=180: cycles.append({"date":day.name,"timestamp":t,"files":chosen,"max_delta_seconds":max(ds)})
 return cycles,pd.DataFrame(audit)
def cycle(c):
 b=rd(c["files"]["daywise"]); b["Symbol"]=b.Symbol.astype(str).str.strip(); b=b[b.Symbol.ne("")].drop_duplicates("Symbol").copy()
 b["snapshot_time"]=c["timestamp"]; b["source_date"]=c["date"]
 specs={"ivr_ivp":["PCR","IV","IV Chg (%)","IVR","IVP","IV/HV10 %","IV/HV20 %","IV/HV30 %"],"resistance":["Strike","Call OI","Call OI Chg","Put OI","Put OI Chg","Dist. From Strike %","Fut Buildup"],"support_resistance":["Strike","Call OI","Call OI Chg","Put OI","Put OI Chg","Dist. From Strike %","Fut Buildup"],"spikes":["OI chg (%)","OI Chg (Value)","Volume Chg (%)"],"sector":["Sector Name","Price chg (%)","Volume chg (%)","OI chg (%)","Buildup","Tol CE OI Chg","Tol PE OI Chg","Tol PE-CE OI Chg","Tol PE-CE OI Chg %"]}
 for k,cols in specs.items():
  d=rd(c["files"][k])
  if k=="ivr_ivp" and len(d) and str(d.iloc[0,0]).strip()=="Symbol": d=d.iloc[1:].copy()
  if "Symbol" not in d: continue
  d["Symbol"]=d.Symbol.astype(str).str.strip(); keep=[x for x in cols if x in d]
  if keep: b=b.merge(d[["Symbol"]+keep].drop_duplicates("Symbol").rename(columns={x:f"{k}__{x}" for x in keep}),on="Symbol",how="left",validate="one_to_one")
 for x in ["Open","High","Low","Close","VWAP","Price Chg %","OI Chg %","Volume Chg (%)","MWPL (%)","MWPL (%) Chg","IV","IVR","IVP","Tot CE OI","Tot PE OI","Tot PE-CE OI","Tot CE OI Chg %","Tot PE OI Chg %","Tot PE-CE OI Chg","Rollover (%)","Delivery (%)","5D Price Chg %","5D OI Chg %","Max Pain"]:
  if x in b: b[x]=pd.to_numeric(b[x].astype(str).str.replace(",","",regex=False).str.replace("%","",regex=False),errors="coerce")
 p=b.get("Price Chg %",pd.Series(np.nan,index=b.index)); o=b.get("OI Chg %",pd.Series(np.nan,index=b.index)); v=b.get("Volume Chg (%)",pd.Series(np.nan,index=b.index))
 b["futures_positioning"]=np.select([(p>0)&(o>0),(p<0)&(o>0),(p>0)&(o<0),(p<0)&(o<0)],["LB","SB","SC","LU"],default="Flat/Mixed")
 ce=b.get("Tot CE OI Chg %",pd.Series(np.nan,index=b.index)); pe=b.get("Tot PE OI Chg %",pd.Series(np.nan,index=b.index))
 b["options_oi_state"]=np.select([pe>ce,pe<ce],["PE-OI dominant","CE-OI dominant"],default="Balanced/Unavailable")
 b["volume_confirmation"]=np.select([(p>0)&(v>0),(p<0)&(v>0)],["Up+Volume","Down+Volume"],default="Weak/Unavailable")
 vw=b.get("VWAP",pd.Series(np.nan,index=b.index)); cl=b.get("Close",pd.Series(np.nan,index=b.index)); b["vwap_relation"]=np.select([cl>vw,cl<vw],["Above VWAP","Below VWAP"],default="VWAP unavailable")
 mw=b.get("MWPL (%)",pd.Series(np.nan,index=b.index)); b["mwpl_state"]=pd.cut(mw,[-np.inf,60,70,80,90,np.inf],labels=["<60","60-70","70-80","80-90",">=90"],right=False).astype(object).where(mw.notna(),"MWPL unavailable")
 ivp=b.get("IVP",pd.Series(np.nan,index=b.index)); b["iv_regime"]=np.select([ivp>=80,ivp>=50,ivp<=20],["High IVP","Mid IVP","Low IVP"],default="IVP unavailable/normal")
 return b
def forward(d):
 d=d.sort_values(["Symbol","snapshot_time"]).copy(); parts=[]
 for _,g in d.groupby("Symbol",sort=False):
  g=g.copy(); t=g.snapshot_time.astype("int64").to_numpy()/1e9/60; px=pd.to_numeric(g.Close,errors="coerce").to_numpy(float); dates=g.snapshot_time.dt.date.to_numpy()
  for h in [5,15,30,60]:
   ix=np.searchsorted(t,t+h); ok=ix<len(g); safe=np.minimum(ix,len(g)-1); ok &= dates==dates[safe]; r=np.full(len(g),np.nan); r[ok]=(px[ix[ok]]/px[ok]-1)*100; g[f"fwd_{h}m_pct"]=r
  parts.append(g)
 return pd.concat(parts,ignore_index=True)
def main(root,outroot):
 cs,audit=discover(root)
 if not cs: raise SystemExit("No complete six-report cycles found.")
 d=forward(pd.concat([cycle(c) for c in cs],ignore_index=True).drop_duplicates(["Symbol","snapshot_time"]))
 out=Path(outroot); out.mkdir(parents=True,exist_ok=True); report=out/"market_state_evidence_V1_6.xlsx"
 with pd.ExcelWriter(report,engine="openpyxl") as w:
  audit.to_excel(w,index=False,sheet_name="Source_Audit")
  pd.DataFrame([{"validated_cycles":len(cs),"observations":len(d),"symbols":d.Symbol.nunique(),"snapshots":d.snapshot_time.nunique(),"first_snapshot":d.snapshot_time.min(),"last_snapshot":d.snapshot_time.max()}]).to_excel(w,index=False,sheet_name="Executive_Summary")
  pd.DataFrame([{"date":c["date"],"timestamp":c["timestamp"],"max_delta_seconds":c["max_delta_seconds"],**{k:v.name for k,v in c["files"].items()}} for c in cs]).to_excel(w,index=False,sheet_name="Validated_Cycles")
  d.to_excel(w,index=False,sheet_name="Market_State_Data")
 status={"status":"SUCCESS","validated_cycles":len(cs),"observations":len(d),"symbols":int(d.Symbol.nunique()),"snapshots":int(d.snapshot_time.nunique()),"report":str(report),"research_status":"PRELIMINARY - validated-cycle evidence discovery only"}
 (out/"market_state_evidence_status.json").write_text(json.dumps(status,default=str,indent=2),encoding="utf-8"); print(json.dumps(status,separators=(",",":"),default=str))
if __name__=="__main__":
 cfg=json.loads(Path(__file__).with_name("CONFIG.json").read_text()); main(sys.argv[1] if len(sys.argv)>1 else cfg["source_root"],cfg["output_root"])
