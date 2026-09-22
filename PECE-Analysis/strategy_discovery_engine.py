"""
PCR/OI Strategy Discovery Engine V1.2
Fast numpy searchsorted forward alignment; same symbol/date only.
"""
from pathlib import Path
import json
import numpy as np,pandas as pd
BASE=Path(__file__).resolve().parent; CFG=json.loads((BASE/"CONFIG.json").read_text(encoding="utf-8"))
ROOT=Path(CFG["output_root"]); FEATURE=ROOT/"Feature_Layer"/"pcr_market_state_features.csv"; OUT=ROOT/"Strategy_Research"; OUT.mkdir(parents=True,exist_ok=True)
def summ(x,label,h):
 x=pd.Series(x).dropna()
 if not len(x):return {"horizon_minutes":h,"condition":label,"n":0,"mean_return_pct":np.nan,"median_return_pct":np.nan,"positive_pct":np.nan,"gt_025_pct":np.nan,"lt_neg025_pct":np.nan,"gain_loss_ratio":np.nan,"adequate":False}
 gain=x[x>0].sum(); loss=-x[x<0].sum()
 return {"horizon_minutes":h,"condition":label,"n":len(x),"mean_return_pct":x.mean(),"median_return_pct":x.median(),"positive_pct":(x>0).mean()*100,"gt_025_pct":(x>.25).mean()*100,"lt_neg025_pct":(x<-.25).mean()*100,"gain_loss_ratio":gain/loss if loss else np.nan,"adequate":len(x)>=CFG["minimum_sample_per_rule"]}
def add_forward(d,mins):
 ret=np.full(len(d),np.nan); elapsed=np.full(len(d),np.nan)
 for (sym,day),idx0 in d.groupby(["Symbol","_date"],sort=False).groups.items():
  idx=np.asarray(list(idx0)); idx=idx[np.argsort(d.loc[idx,"_time"].astype("int64").to_numpy())]
  ts=d.loc[idx,"_time"].astype("int64").to_numpy(); price=d.loc[idx,"Fut Price"].to_numpy(dtype=float)
  j=np.searchsorted(ts,ts+pd.Timedelta(minutes=mins).value,side="left"); valid=j<len(ts)
  ii=idx[valid]; jj=j[valid]; p=price[valid]; fp=price[jj]
  ret[ii]=np.where((p!=0)&np.isfinite(p)&np.isfinite(fp),(fp-p)/p*100,np.nan)
  elapsed[ii]=(ts[jj]-ts[valid])/60e9
 return ret,elapsed
def main():
 if not FEATURE.exists():raise FileNotFoundError(FEATURE)
 d=pd.read_csv(FEATURE,low_memory=False,parse_dates=["_time","_date"]); d["_date"]=d["_time"].dt.normalize(); d=d.sort_values(["Symbol","_time"]).reset_index(drop=True)
 for h in CFG["horizons_minutes"]:
  d[f"ret_{h}m_pct"],d[f"elapsed_{h}m"]=add_forward(d,h)
 masks={
 "All observations":pd.Series(True,index=d.index),"LB":d.futures_position.eq("LB"),"SB":d.futures_position.eq("SB"),"SC":d.futures_position.eq("SC"),"LU":d.futures_position.eq("LU"),
 "Strong CE Skew":d.skew_state.eq("Strong CE Skew"),"Moderate CE Skew":d.skew_state.eq("Moderate CE Skew"),"Balanced":d.skew_state.eq("Balanced"),"Moderate PE Skew":d.skew_state.eq("Moderate PE Skew"),"Strong PE Skew":d.skew_state.eq("Strong PE Skew"),
 "Above VWAP":d.vwap_state.eq("Above VWAP"),"Below VWAP":d.vwap_state.eq("Below VWAP"),"PE Confirming":d.volume_oi_relation.eq("PE Confirming"),"CE Confirming":d.volume_oi_relation.eq("CE Confirming"),
 "PE Volume / CE OI Divergence":d.volume_oi_relation.eq("PE Volume / CE OI Divergence"),"CE Volume / PE OI Divergence":d.volume_oi_relation.eq("CE Volume / PE OI Divergence"),
 "Fresh Skew (1-2)":d.skew_persistence.le(2),"Persistent Skew (>=4)":d.skew_persistence.ge(4),"High Activity":d.activity_state.eq("High Futures Activity")}
 for a in ["LB","SB","SC","LU"]:
  for b in ["Strong CE Skew","Moderate CE Skew","Balanced","Moderate PE Skew","Strong PE Skew","Above VWAP","Below VWAP","PE Confirming","CE Confirming","PE Volume / CE OI Divergence","CE Volume / PE OI Divergence","Fresh Skew (1-2)","Persistent Skew (>=4)","High Activity"]:
   masks[f"{a} + {b}"]=masks[a]&masks[b]
 rows=[]; directional=[]
 for h in CFG["horizons_minutes"]:
  col=f"ret_{h}m_pct"
  for n,m in masks.items():
   rows.append(summ(d.loc[m,col],n,h))
   direction=np.where(d.futures_position.isin(["LB","SC"]),1,np.where(d.futures_position.isin(["SB","LU"]),-1,0))
   u=m&(direction!=0)&d[col].notna(); sr=d.loc[u,col]*direction[u]
   q=summ(sr,n,h); q["directional_hit_pct"]=(sr>0).mean()*100 if len(sr) else np.nan; q["directional_gt_025_pct"]=(sr>.25).mean()*100 if len(sr) else np.nan; q["directional_lt_neg025_pct"]=(sr<-.25).mean()*100 if len(sr) else np.nan; directional.append(q)
 cand=pd.DataFrame(rows); direct=pd.DataFrame(directional)
 stability=[]
 for h in CFG["horizons_minutes"]:
  for n,m in masks.items():
   for day,gd in d.loc[m].groupby("_date"):
    r=gd[f"ret_{h}m_pct"].dropna()
    if len(r):stability.append({"date":str(day.date()),"horizon_minutes":h,"condition":n,"n":len(r),"mean_return_pct":r.mean(),"positive_pct":(r>0).mean()*100})
 stability=pd.DataFrame(stability)
 state=d.groupby(["futures_position","skew_state","volume_oi_relation"],dropna=False).size().reset_index(name="observations")
 coverage=pd.DataFrame([{"observations":len(d),"symbols":d.Symbol.nunique(),"dates":d._date.nunique(),"first_time":d._time.min(),"last_time":d._time.max()}])
 notes=pd.DataFrame({"Topic":["Purpose","Look-ahead","Timestamp","Interpretation","Validation"],"Finding":[
 "Research combinations of PCR Volume, PCR OI, CE/PE OI, Futures LB/SB/SC/LU, VWAP and activity.",
 "Features at signal time only; forward outcomes stay within the same symbol and market date.",
 "Market observation = source date + workbook Time; Snapshot is provenance.",
 "Discovery statistics are not proof of a successful strategy.",
 "Freeze candidates after discovery and validate on additional chronological trading days."
 ]})
 report=OUT/CFG["report_filename"]
 with pd.ExcelWriter(report,engine="openpyxl") as w:
  cand.to_excel(w,index=False,sheet_name="Return_Candidates"); direct.to_excel(w,index=False,sheet_name="Directional_Hypotheses"); stability.to_excel(w,index=False,sheet_name="Day_Stability"); state.to_excel(w,index=False,sheet_name="State_Matrix"); coverage.to_excel(w,index=False,sheet_name="Data_Coverage"); notes.to_excel(w,index=False,sheet_name="Research_Notes")
 status={"status":"SUCCESS","report":str(report),"observations":len(d),"symbols":int(d.Symbol.nunique()),"dates":int(d._date.nunique()),"horizons":CFG["horizons_minutes"],"candidate_rules":len(masks),"research_status":"PRELIMINARY - discovery only"}
 (OUT/"strategy_research_status.json").write_text(json.dumps(status,indent=2,default=str),encoding="utf-8"); print(json.dumps(status,separators=(",",":")))
if __name__=="__main__":main()
