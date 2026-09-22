import json,numpy as np,pandas as pd
from pathlib import Path
def C(d,*n):
 m={str(x).lower():x for x in d.columns}
 for x in n:
  if x.lower() in m:return m[x.lower()]
def N(d,*n):
 c=C(d,*n); return pd.to_numeric(d[c],errors="coerce") if c else pd.Series(np.nan,index=d.index)
def outcomes(d,hs):
 for h in hs:
  d[f"ret_{h}m_pct"]=np.nan
  for _,ix in d.groupby("_symbol",sort=False).groups.items():
   s=d.loc[ix].sort_values("_ts"); t=s._ts.astype("int64").to_numpy(); p=s.price.to_numpy(float)
   q=np.searchsorted(t,t+int(h*60*1e9),side="left"); ok=q<len(t); fut=np.full(len(s),np.nan); fut[ok]=p[q[ok]]
   r=np.full(len(s),np.nan); good=ok&np.isfinite(p)&(p!=0)&np.isfinite(fut); r[good]=(fut[good]/p[good]-1)*100
   d.loc[s.index,f"ret_{h}m_pct"]=r
 return d
def main():
 c=json.loads(Path("CONFIG.json").read_text()); d=pd.read_csv(c["market_state_cache"],low_memory=False); d.columns=[str(x).strip() for x in d.columns]
 d["_symbol"]=d["_symbol"].astype(str).str.strip(); d["_ts"]=pd.to_datetime(d.snapshot_time,errors="coerce"); d=d.dropna(subset=["_symbol","_ts"]).copy()
 d["price"]=N(d,"Close","Price","Futures Price"); d["price_chg_pct"]=N(d,"Price Chg %","Price Chg (%)","Price chg (%)"); d["oi_chg_pct"]=N(d,"OI Chg %","OI Chg (%)","Total OI Chg (%)","Fut OI Chg %"); d["volume_chg_pct"]=N(d,"Volume Chg (%)","Volume Chg %","Volume Chg"); d["mwpl_pct"]=N(d,"MWPL (%)","MWPL"); d["pcr"]=N(d,"PCR"); d["ivr"]=N(d,"IVR"); d["vwap"]=N(d,"VWAP")
 b=C(d,"Buildup"); d["buildup"]=d[b].astype(str).str.strip() if b else ""
 d["price_oi_state"]=np.select([(d.price_chg_pct>0)&(d.oi_chg_pct>0),(d.price_chg_pct<0)&(d.oi_chg_pct>0),(d.price_chg_pct>0)&(d.oi_chg_pct<0),(d.price_chg_pct<0)&(d.oi_chg_pct<0)],["LB","SB","SC","LU"],default="Unknown")
 d["mwpl_state"]=pd.cut(d.mwpl_pct,[-np.inf,40,60,70,80,90,np.inf],labels=["<40","40-60","60-70","70-80","80-90","90+"])
 d["ivr_state"]=pd.cut(d.ivr,[-np.inf,20,40,60,80,np.inf],labels=["<20","20-40","40-60","60-80","80+"])
 d["volume_state"]=pd.cut(d.volume_chg_pct,[-np.inf,-25,0,25,50,np.inf],labels=["<-25","-25-0","0-25","25-50","50+"])
 d["oi_state"]=pd.cut(d.oi_chg_pct,[-np.inf,-5,-1,1,5,np.inf],labels=["<-5","-5--1","-1-1","1-5","5+"])
 d["vwap_relation"]=np.select([d.price>d.vwap,d.price<d.vwap],["Above VWAP","Below VWAP"],default="Unknown")
 d["pcr_state"]=pd.cut(d.pcr,[-np.inf,.5,.75,1,1.25,1.5,np.inf],labels=["<.5",".5-.75",".75-1","1-1.25","1.25-1.5","1.5+"])
 d=outcomes(d,c["horizons"]); rows=[]; features=["price_oi_state","buildup","mwpl_state","ivr_state","volume_state","oi_state","vwap_relation","pcr_state"]
 for f in features:
  for state,g in d.groupby(f,dropna=False):
   for h in c["horizons"]:
    x=pd.to_numeric(g[f"ret_{h}m_pct"],errors="coerce").dropna(); base=pd.to_numeric(d[f"ret_{h}m_pct"],errors="coerce").dropna()
    if len(x)>=c["minimum_group_observations"] and len(base):
     rows.append({"feature":f,"state":str(state),"horizon_min":h,"observations":len(x),"mean_pct":x.mean(),"median_pct":x.median(),"positive_pct":(x>0).mean()*100,"gt_025_pct":(x>.25).mean()*100,"lt_neg025_pct":(x<-.25).mean()*100,"base_mean_pct":base.mean(),"delta_mean_vs_base_pct":x.mean()-base.mean(),"delta_positive_vs_base_pct":(x>0).mean()*100-(base>0).mean()*100})
 contrib=pd.DataFrame(rows)
 nums=["price_chg_pct","oi_chg_pct","volume_chg_pct","mwpl_pct","pcr","ivr","vwap"]
 corr=d[nums].corr(method="spearman").reset_index().rename(columns={"index":"feature"})
 cov=pd.DataFrame([{"feature":x,"non_null":int(d[x].notna().sum()),"coverage_pct":float(d[x].notna().mean()*100)} for x in nums+["price_oi_state","buildup","vwap_relation"]])
 base=pd.DataFrame([{"horizon_min":h,"observations":len(x),"mean_pct":x.mean(),"median_pct":x.median(),"positive_pct":(x>0).mean()*100,"gt_025_pct":(x>.25).mean()*100,"lt_neg025_pct":(x<-.25).mean()*100} for h in c["horizons"] for x in [pd.to_numeric(d[f"ret_{h}m_pct"],errors="coerce").dropna()]])
 out=Path(c["output_dir"]); out.mkdir(parents=True,exist_ok=True); report=out/"evidence_fusion_V2_incremental.xlsx"
 with pd.ExcelWriter(report,engine="openpyxl") as w:
  contrib.to_excel(w,sheet_name="Feature_Contribution",index=False); corr.to_excel(w,sheet_name="Feature_Correlation",index=False); cov.to_excel(w,sheet_name="Feature_Coverage",index=False); base.to_excel(w,sheet_name="Horizon_Base_Rates",index=False)
 print(json.dumps({"status":"SUCCESS","observations":len(d),"symbols":int(d._symbol.nunique()),"snapshots":int(d._ts.nunique()),"feature_states_tested":len(contrib),"report":str(report),"research_status":"PRELIMINARY - incremental evidence discovery only"},separators=(",",":")))
if __name__=="__main__":main()
