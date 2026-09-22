import json, numpy as np, pandas as pd
from pathlib import Path

def cfg(): return json.loads(Path("CONFIG.json").read_text(encoding="utf-8"))
def col(d,*names):
    m={str(x).strip().lower():x for x in d.columns}
    for n in names:
        if n.lower() in m:return m[n.lower()]
    return None
def num(d,*names):
    c=col(d,*names)
    return pd.to_numeric(d[c],errors="coerce") if c else pd.Series(np.nan,index=d.index)

def add_outcomes(d, horizons):
    d=d.sort_values(["_symbol","_session","_ts"]).reset_index(drop=True)
    for h in horizons:
        out=np.full(len(d),np.nan)
        for _,ix in d.groupby(["_symbol","_session"],sort=False).groups.items():
            s=d.loc[ix].sort_values("_ts")
            # Use datetime-aware arithmetic. Raw int64 timestamp arithmetic is
            # intentionally avoided because pandas/numpy timestamp units can differ.
            t=s["_ts"].to_numpy(dtype="datetime64[ns]")
            p=pd.to_numeric(s["price"],errors="coerce").to_numpy(float)
            target=t+np.timedelta64(int(h*60),"m")
            pos=np.searchsorted(t,target,side="left")
            ok=pos<len(t)
            fut=np.full(len(s),np.nan); fut[ok]=p[pos[ok]]
            r=np.full(len(s),np.nan)
            good=ok&np.isfinite(p)&(p!=0)&np.isfinite(fut)
            r[good]=(fut[good]/p[good]-1)*100
            out[s.index.to_numpy()]=r
        d[f"ret_{h}m_pct"]=out
    return d

def main():
    c=cfg()
    cache=Path(c["market_state_cache"])
    if not cache.exists(): raise FileNotFoundError(cache)
    d=pd.read_csv(cache,low_memory=False)
    d.columns=[str(x).strip() for x in d.columns]
    if "_symbol" not in d or "snapshot_time" not in d: raise ValueError("Missing _symbol/snapshot_time")
    d["_symbol"]=d["_symbol"].astype(str).str.strip()
    d["_ts"]=pd.to_datetime(d["snapshot_time"],errors="coerce")
    d=d.dropna(subset=["_symbol","_ts"]).copy()
    d["_session"]=d["_ts"].dt.strftime("%Y-%m-%d")
    d["price"]=num(d,"Close")
    d["price_chg_pct"]=num(d,"Price Chg %")
    d["oi_chg_pct"]=num(d,"OI Chg %")
    d["volume_chg_pct"]=num(d,"Volume Chg (%)")
    d["mwpl_pct"]=num(d,"MWPL (%)")
    d["mwpl_chg"]=num(d,"MWPL (%) Chg")
    d["pcr_chg_pct"]=num(d,"PCR Chg %")
    d["ivr"]=num(d,"IVR")
    d["ivp"]=num(d,"IVP")
    d["vwap"]=num(d,"VWAP")
    d["pe_ce_oi"]=num(d,"Tot PE-CE OI")
    d["pe_ce_oi_chg"]=num(d,"Tot PE-CE OI Chg")
    b=col(d,"Buildup")
    d["buildup"]=d[b].astype(str).str.strip() if b else ""
    # Preserve supplied canonical states when present.
    for name in ["futures_positioning","options_oi_state","volume_confirmation","vwap_relation","mwpl_state","iv_regime"]:
        if name not in d: d[name]=""

    d["price_oi_state"]=np.select([
        (d.price_chg_pct>0)&(d.oi_chg_pct>0),
        (d.price_chg_pct<0)&(d.oi_chg_pct>0),
        (d.price_chg_pct>0)&(d.oi_chg_pct<0),
        (d.price_chg_pct<0)&(d.oi_chg_pct<0)],
        ["LB","SB","SC","LU"],default="Unknown")
    d["mwpl_bin"]=pd.cut(d.mwpl_pct,[-np.inf,40,60,70,80,90,np.inf],labels=["<40","40-60","60-70","70-80","80-90","90+"])
    d["ivr_bin"]=pd.cut(d.ivr,[-np.inf,20,40,60,80,np.inf],labels=["<20","20-40","40-60","60-80","80+"])
    d["volume_bin"]=pd.cut(d.volume_chg_pct,[-np.inf,-25,0,25,50,np.inf],labels=["<-25","-25-0","0-25","25-50","50+"])
    d["oi_bin"]=pd.cut(d.oi_chg_pct,[-np.inf,-5,-1,1,5,np.inf],labels=["<-5","-5--1","-1-1","1-5","5+"])
    d["pcr_chg_bin"]=pd.cut(d.pcr_chg_pct,[-np.inf,-10,-2,2,10,np.inf],labels=["<-10","-10--2","-2-2","2-10","10+"])
    d["vwap_relation_calc"]=np.select([d.price>d.vwap,d.price<d.vwap],["Above VWAP","Below VWAP"],default="Unknown")

    d=add_outcomes(d,c["horizons"])

    features=[
        "price_oi_state","futures_positioning","options_oi_state","volume_confirmation",
        "vwap_relation","vwap_relation_calc","mwpl_state","mwpl_bin","iv_regime","ivr_bin",
        "buildup","volume_bin","oi_bin","pcr_chg_bin"
    ]
    rows=[]
    for f in features:
        if f not in d: continue
        for state,g in d.groupby(f,dropna=False):
            for h in c["horizons"]:
                x=pd.to_numeric(g[f"ret_{h}m_pct"],errors="coerce").dropna()
                base=pd.to_numeric(d[f"ret_{h}m_pct"],errors="coerce").dropna()
                if len(x)<c["minimum_group_observations"] or not len(base): continue
                rows.append({
                    "feature":f,"state":str(state),"horizon_min":h,"observations":len(x),
                    "mean_pct":x.mean(),"median_pct":x.median(),
                    "positive_pct":(x>0).mean()*100,"gt_025_pct":(x>.25).mean()*100,
                    "lt_neg025_pct":(x<-.25).mean()*100,
                    "base_mean_pct":base.mean(),"base_median_pct":base.median(),
                    "delta_mean_vs_base_pct":x.mean()-base.mean(),
                    "delta_positive_vs_base_pct":(x>0).mean()*100-(base>0).mean()*100
                })
    contrib=pd.DataFrame(rows)
    nums=["price_chg_pct","oi_chg_pct","volume_chg_pct","mwpl_pct","mwpl_chg","pcr_chg_pct","ivr","ivp","vwap","pe_ce_oi","pe_ce_oi_chg"]
    corr=d[nums].corr(method="spearman").reset_index().rename(columns={"index":"feature"})
    coverage=pd.DataFrame([{
        "feature":x,"non_null":int(d[x].notna().sum()),"coverage_pct":float(d[x].notna().mean()*100)
    } for x in nums+features if x in d])
    base=pd.DataFrame([{
        "horizon_min":h,
        "observations":len(x),
        "mean_pct":x.mean(),
        "median_pct":x.median(),
        "positive_pct":(x>0).mean()*100,
        "gt_025_pct":(x>.25).mean()*100,
        "lt_neg025_pct":(x<-.25).mean()*100
    } for h in c["horizons"] for x in [pd.to_numeric(d[f"ret_{h}m_pct"],errors="coerce").dropna()]])
    quality=pd.DataFrame([{
        "horizon_min":h,
        "usable_forward_observations":int(d[f"ret_{h}m_pct"].notna().sum()),
        "coverage_pct":float(d[f"ret_{h}m_pct"].notna().mean()*100)
    } for h in c["horizons"]])
    notes=pd.DataFrame([
        ["Version","V2.2 - datetime-safe forward outcome calculation"],
        ["Status",c["research_status"]],
        ["Outcome construction","Same symbol + same session; first observation at or after requested horizon"],
        ["Timestamp source","V1.6 snapshot_time"],
        ["No fabrication","No interpolation and no synthetic timestamps"],
        ["Baseline","Unconditional forward-return distribution for each horizon"],
        ["Interpretation","Conditional differences are associations, not causal or profitability claims"],
        ["Multiple testing","All states/horizons require out-of-sample confirmation"],
        ["Sparse fields","Missing MWPL/Buildup/etc. are retained as missing and coverage is reported"]
    ],columns=["item","value"])
    out=Path(c["output_dir"]); out.mkdir(parents=True,exist_ok=True)
    report=out/"evidence_fusion_V2_2_incremental.xlsx"
    with pd.ExcelWriter(report,engine="openpyxl") as w:
        contrib.to_excel(w,sheet_name="Feature_Contribution",index=False)
        corr.to_excel(w,sheet_name="Feature_Correlation",index=False)
        coverage.to_excel(w,sheet_name="Feature_Coverage",index=False)
        base.to_excel(w,sheet_name="Horizon_Base_Rates",index=False)
        quality.to_excel(w,sheet_name="Forward_Data_Quality",index=False)
        notes.to_excel(w,sheet_name="Research_Notes",index=False)
    print(json.dumps({
        "status":"SUCCESS","observations":len(d),"symbols":int(d._symbol.nunique()),
        "snapshots":int(d._ts.nunique()),"feature_states_tested":len(contrib),
        "forward_observations":{"5m":int(d.ret_5m_pct.notna().sum()),"15m":int(d.ret_15m_pct.notna().sum()),"30m":int(d.ret_30m_pct.notna().sum()),"60m":int(d.ret_60m_pct.notna().sum())},
        "report":str(report),"research_status":c["research_status"]
    },separators=(",",":")))
if __name__=="__main__": main()
