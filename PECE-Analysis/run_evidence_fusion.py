import json
from pathlib import Path
import numpy as np
import pandas as pd

def main():
    c=json.loads(Path("CONFIG.json").read_text(encoding="utf-8"))
    cache=Path(c["market_state_cache"])
    if not cache.exists():
        print("CACHE_MISSING - run build_market_state_cache.py first"); return
    d=pd.read_csv(cache,low_memory=False)
    d.columns=[str(x).strip() for x in d.columns]
    d["_symbol"]=d["_symbol"].astype(str).str.strip()
    d["_ts"]=pd.to_datetime(d["snapshot_time"],errors="coerce")
    d=d.dropna(subset=["_symbol","_ts"]).sort_values(["_symbol","_ts"]).reset_index(drop=True)

    def col(*names):
        m={str(x).lower():x for x in d.columns}
        for n in names:
            if n.lower() in m:return m[n.lower()]
    def num(name,*alts):
        z=col(name,*alts)
        return pd.to_numeric(d[z],errors="coerce") if z else pd.Series(np.nan,index=d.index)

    d["price_chg_pct"]=num("Price Chg %","Price Chg (%)","Price chg (%)")
    d["oi_chg_pct"]=num("OI Chg %","OI Chg (%)","Total OI Chg (%)","Fut OI Chg %")
    d["volume_chg_pct"]=num("Volume Chg (%)","Volume Chg %","Volume Chg")
    d["mwpl_pct"]=num("MWPL (%)","MWPL")
    d["mwpl_chg"]=num("MWPL (%) Chg","MWPL Chg")
    d["pcr"]=num("PCR")
    d["ivr"]=num("IVR")
    d["ivp"]=num("IVP")
    d["price"]=num("Close","Price","Futures Price")
    b=col("Buildup")
    d["buildup"]=d[b].astype(str) if b else ""

    d["price_oi_state"]=np.select([
        (d.price_chg_pct>0)&(d.oi_chg_pct>0),
        (d.price_chg_pct<0)&(d.oi_chg_pct>0),
        (d.price_chg_pct>0)&(d.oi_chg_pct<0),
        (d.price_chg_pct<0)&(d.oi_chg_pct<0)],
        ["LB","SB","SC","LU"],default="Unknown")
    d["mwpl_state"]=pd.cut(d.mwpl_pct,[-np.inf,40,60,70,80,90,np.inf],
                            labels=["<40","40-60","60-70","70-80","80-90","90+"])
    d["iv_state"]=pd.cut(d.ivr,[-np.inf,20,40,60,80,np.inf],
                          labels=["low","20-40","40-60","60-80","high"])

    for h in c["forward_horizons_minutes"]:
        d[f"ret_{h}m_pct"]=np.nan
        for _,idx in d.groupby("_symbol",sort=False).groups.items():
            s=d.loc[idx].sort_values("_ts")
            t=s["_ts"].astype("int64").to_numpy()
            p=pd.to_numeric(s["price"],errors="coerce").to_numpy(float)
            pos=np.searchsorted(t,t+int(h*60*1e9),side="left")
            ok=pos<len(t)
            fut=np.full(len(s),np.nan); fut[ok]=p[pos[ok]]
            ret=np.full(len(s),np.nan)
            good=ok&np.isfinite(p)&(p!=0)&np.isfinite(fut)
            ret[good]=(fut[good]/p[good]-1)*100
            d.loc[s.index,f"ret_{h}m_pct"]=ret

    summary=[]
    for feature in ["price_oi_state","mwpl_state","iv_state","buildup"]:
        for value,g in d.groupby(feature,dropna=False):
            r={"feature":feature,"state":str(value),"observations":len(g)}
            for h in c["forward_horizons_minutes"]:
                x=pd.to_numeric(g[f"ret_{h}m_pct"],errors="coerce").dropna()
                r[f"{h}m_mean_pct"]=x.mean() if len(x) else np.nan
                r[f"{h}m_median_pct"]=x.median() if len(x) else np.nan
                r[f"{h}m_positive_pct"]=(x>0).mean()*100 if len(x) else np.nan
                r[f"{h}m_gt_025_pct"]=(x>0.25).mean()*100 if len(x) else np.nan
                r[f"{h}m_lt_neg025_pct"]=(x<-0.25).mean()*100 if len(x) else np.nan
            summary.append(r)
    summary=pd.DataFrame(summary)
    out=Path(c["output_dir"]); out.mkdir(parents=True,exist_ok=True)
    report=out/"evidence_fusion_V1.xlsx"
    coverage=pd.DataFrame([{"feature":x,"coverage_pct":d[x].notna().mean()*100}
        for x in ["price_chg_pct","oi_chg_pct","volume_chg_pct","mwpl_pct","mwpl_chg","pcr","ivr","ivp"]])
    notes=pd.DataFrame([
        ["Status","PRELIMINARY - evidence discovery only; no validated trading rule"],
        ["Baseline","Market-State V1.6 successful validated-cycle output"],
        ["Performance","Research uses canonical cache instead of rescanning six raw reports"],
        ["Next gate","Incremental comparison against PCR/OI V1.2 and out-of-sample validation"]
    ],columns=["item","value"])
    with pd.ExcelWriter(report,engine="openpyxl") as w:
        summary.to_excel(w,sheet_name="State_Evidence",index=False)
        coverage.to_excel(w,sheet_name="Feature_Coverage",index=False)
        d.to_excel(w,sheet_name="Canonical_Data",index=False)
        notes.to_excel(w,sheet_name="Research_Notes",index=False)
    print(json.dumps({"status":"SUCCESS","observations":len(d),"symbols":d._symbol.nunique(),
                      "snapshots":d._ts.nunique(),"report":str(report),
                      "research_status":"PRELIMINARY - evidence discovery only"},separators=(",",":")))
if __name__=="__main__": main()

