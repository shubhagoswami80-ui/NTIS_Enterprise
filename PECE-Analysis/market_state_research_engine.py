import numpy as np
import pandas as pd

def forward(df,horizons=(5,15,30,60)):
    d=df.sort_values(["Symbol","snapshot_time"]).copy()
    parts=[]
    for _,g in d.groupby("Symbol",sort=False):
        g=g.copy(); t=g.snapshot_time.astype("int64").to_numpy()/1e9/60; p=pd.to_numeric(g.Close,errors="coerce").to_numpy(float)
        dates=g.snapshot_time.dt.date.to_numpy()
        for h in horizons:
            ix=np.searchsorted(t,t+h,side="left"); ok=ix<len(g)
            r=np.full(len(g),np.nan); safe=np.minimum(ix,len(g)-1); ok &= dates==dates[safe]
            r[ok]=(p[ix[ok]]/p[ok]-1)*100; g[f"fwd_{h}m_pct"]=r
        parts.append(g)
    return pd.concat(parts,ignore_index=True)

def summary(d,col):
    rows=[]
    for key,g in d.groupby(col,dropna=False):
        for h in (5,15,30,60):
            x=pd.to_numeric(g[f"fwd_{h}m_pct"],errors="coerce").dropna()
            if len(x): rows.append({"group":str(key),"horizon_min":h,"observations":len(x),"mean_pct":x.mean(),"median_pct":x.median(),"positive_pct":(x>0).mean()*100,"gt_0_25_pct":(x>0.25).mean()*100,"lt_minus_0_25_pct":(x<-0.25).mean()*100})
    return pd.DataFrame(rows)

def run(d):
    d=forward(d)
    sheets={"Market_State_Data":d}
    for c in ["futures_positioning","options_oi_state","volume_confirmation","vwap_relation","mwpl_state","iv_regime","market_state_key"]:
        sheets[c[:31]]=summary(d,c)
    if "Buildup" in d: sheets["Buildup"]=summary(d,"Buildup")
    if "Sector" in d: sheets["Sector"]=summary(d,"Sector")
    return sheets
