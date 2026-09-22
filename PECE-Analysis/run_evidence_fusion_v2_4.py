import json
from pathlib import Path
import numpy as np
import pandas as pd

def cfg():
    p=Path(__file__).with_name("CONFIG.json")
    return json.loads(p.read_text(encoding="utf-8"))

def col(d,*names):
    m={str(x).strip().lower():x for x in d.columns}
    for n in names:
        if n.lower() in m:
            return m[n.lower()]
    return None

def num(d,*names):
    c=col(d,*names)
    return pd.to_numeric(d[c],errors="coerce") if c else pd.Series(np.nan,index=d.index)

def add_outcomes(d,horizons):
    d=d.sort_values(["_symbol","_session","_ts"]).reset_index(drop=True)
    for h in horizons:
        out=np.full(len(d),np.nan)
        for _,ix in d.groupby(["_symbol","_session"],sort=False).groups.items():
            s=d.loc[ix].sort_values("_ts")
            t=s["_ts"].to_numpy(dtype="datetime64[ns]")
            p=pd.to_numeric(s["price"],errors="coerce").to_numpy(float)
            if int(h) not in (5,15,30,60):
                raise ValueError(f"Unsupported horizon: {h}")
            target=t+np.timedelta64(int(h),"m")
            pos=np.searchsorted(t,target,side="left")
            ok=pos<len(t)
            fut=np.full(len(s),np.nan)
            fut[ok]=p[pos[ok]]
            r=np.full(len(s),np.nan)
            good=ok&np.isfinite(p)&(p!=0)&np.isfinite(fut)
            r[good]=(fut[good]/p[good]-1)*100
            out[s.index.to_numpy()]=r
        d[f"ret_{h}m_pct"]=out
    return d

def clean_state(s):
    return s.astype(str).str.strip().replace({"":np.nan,"nan":np.nan,"None":np.nan})

def main():
    c=cfg()
    cache=Path(c["market_state_cache"])
    if not cache.exists():
        raise FileNotFoundError(cache)

    d=pd.read_csv(cache,low_memory=False)
    d.columns=[str(x).strip() for x in d.columns]
    d["_symbol"]=d["_symbol"].astype(str).str.strip()
    d["_ts"]=pd.to_datetime(d["snapshot_time"],errors="coerce")
    d=d.dropna(subset=["_symbol","_ts"]).copy()
    d["_session"]=d["_ts"].dt.strftime("%Y-%m-%d")
    d["price"]=num(d,"Close")

    # Preserve canonical states; derive only missing/blank state labels.
    for x in ["futures_positioning","options_oi_state","volume_confirmation",
              "vwap_relation","mwpl_state","iv_regime","Buildup"]:
        if x not in d:
            d[x]=np.nan
        d[x]=clean_state(d[x])

    d["pcr_chg_pct"]=num(d,"PCR Chg %")
    d["volume_chg_pct"]=num(d,"Volume Chg (%)")
    d["oi_chg_pct"]=num(d,"OI Chg %")
    d["mwpl_pct"]=num(d,"MWPL (%)")
    d["mwpl_state"]=d["mwpl_state"].where(d["mwpl_state"].notna(),
                                           pd.cut(d["mwpl_pct"],[-np.inf,40,60,70,80,90,np.inf],
                                                  labels=["<40","40-60","60-70","70-80","80-90","90+"]))

    # Compact, non-overlapping feature vocabulary for interaction testing.
    feature_map={
        "MWPL": "mwpl_state",
        "Futures": "futures_positioning",
        "Buildup": "Buildup",
        "PCR_Change": "pcr_chg_bin",
        "Volume": "volume_confirmation"
    }
    d["pcr_chg_bin"]=pd.cut(d["pcr_chg_pct"],
                            [-np.inf,-10,-2,2,10,np.inf],
                            labels=["<-10","-10--2","-2-2","2-10","10+"])

    # Do not test duplicate aliases as separate evidence families.
    pairs=[
        ("MWPL","Futures"),
        ("MWPL","Buildup"),
        ("MWPL","PCR_Change"),
        ("MWPL","Volume"),
        ("Futures","Buildup"),
        ("Futures","PCR_Change"),
        ("Futures","Volume"),
        ("Buildup","PCR_Change"),
        ("Buildup","Volume"),
        ("PCR_Change","Volume")
    ]
    triples=[
        ("MWPL","Futures","Volume"),
        ("MWPL","Futures","PCR_Change"),
        ("MWPL","Buildup","Volume"),
        ("MWPL","Buildup","PCR_Change"),
        ("Futures","Buildup","Volume"),
        ("Futures","Buildup","PCR_Change"),
        ("Futures","PCR_Change","Volume"),
        ("Buildup","PCR_Change","Volume")
    ]

    d=add_outcomes(d,c["horizons"])
    min_obs=int(c["minimum_group_observations"])
    min_day_obs=int(c["minimum_day_observations"])

    base_rows=[]
    for h in c["horizons"]:
        x=pd.to_numeric(d[f"ret_{h}m_pct"],errors="coerce").dropna()
        base_rows.append({
            "horizon_min":h,"observations":len(x),
            "mean_pct":x.mean(),"median_pct":x.median(),
            "positive_pct":(x>0).mean()*100,
            "gt_025_pct":(x>.25).mean()*100,
            "lt_neg025_pct":(x<-.25).mean()*100
        })
    base=pd.DataFrame(base_rows)

    def interaction_rows(kind, combos):
        rows=[]
        for combo in combos:
            cols=[feature_map[x] for x in combo]
            label=" × ".join(combo)
            for state_vals,g in d.groupby(cols,dropna=False,observed=True):
                if not isinstance(state_vals,tuple):
                    state_vals=(state_vals,)
                state=" | ".join(str(v) for v in state_vals)
                if any(pd.isna(v) for v in state_vals):
                    continue
                for h in c["horizons"]:
                    x=pd.to_numeric(g[f"ret_{h}m_pct"],errors="coerce").dropna()
                    b=base.loc[base.horizon_min==h].iloc[0]
                    if len(x)<min_obs:
                        continue
                    rows.append({
                        "interaction_type":kind,
                        "features":label,
                        "state":state,
                        "horizon_min":h,
                        "observations":len(x),
                        "mean_pct":x.mean(),
                        "median_pct":x.median(),
                        "positive_pct":(x>0).mean()*100,
                        "gt_025_pct":(x>.25).mean()*100,
                        "lt_neg025_pct":(x<-.25).mean()*100,
                        "base_mean_pct":b.mean_pct,
                        "base_median_pct":b.median_pct,
                        "delta_mean_vs_base_pct":x.mean()-b.mean_pct,
                        "delta_positive_vs_base_pct":(x>0).mean()*100-b.positive_pct
                    })
        return rows

    rows=interaction_rows("2-way",pairs)+interaction_rows("3-way",triples)
    contrib=pd.DataFrame(rows)

    # Day stability: a candidate interaction is considered day-observable only
    # when it has enough usable forward observations on that day.
    day_rows=[]
    if not contrib.empty:
        for _,r in contrib.iterrows():
            combo=r["features"].split(" × ")
            cols=[feature_map[x] for x in combo]
            vals=r["state"].split(" | ")
            mask=pd.Series(True,index=d.index)
            for cc,v in zip(cols,vals):
                mask &= d[cc].astype(str).eq(v)
            for day,g in d.loc[mask].groupby("_session",sort=True):
                x=pd.to_numeric(g[f"ret_{int(r.horizon_min)}m_pct"],errors="coerce").dropna()
                if len(x)<min_day_obs:
                    continue
                day_rows.append({
                    "features":r["features"],"state":r["state"],
                    "horizon_min":int(r.horizon_min),"session":day,
                    "observations":len(x),"mean_pct":x.mean(),
                    "median_pct":x.median(),"positive_pct":(x>0).mean()*100,
                    "gt_025_pct":(x>.25).mean()*100,
                    "lt_neg025_pct":(x<-.25).mean()*100
                })
    day=pd.DataFrame(day_rows)

    stability=[]
    if not contrib.empty:
        for _,r in contrib.iterrows():
            z=day[(day.features==r.features)&(day.state==r.state)&(day.horizon_min==r.horizon_min)]
            if len(z):
                stability.append({
                    "features":r.features,"state":r.state,"horizon_min":int(r.horizon_min),
                    "pooled_observations":int(r.observations),
                    "days_with_minimum_sample":len(z),
                    "days_positive_mean":int((z.mean_pct>0).sum()),
                    "days_positive_median":int((z.median_pct>0).sum()),
                    "day_mean_min_pct":z.mean_pct.min(),
                    "day_mean_max_pct":z.mean_pct.max(),
                    "day_mean_avg_pct":z.mean_pct.mean()
                })
    stability=pd.DataFrame(stability)

    coverage=[]
    for f,colname in feature_map.items():
        coverage.append({
            "feature":f,"source_column":colname,
            "non_null":int(d[colname].notna().sum()),
            "coverage_pct":float(d[colname].notna().mean()*100),
            "distinct_states":int(d[colname].nunique(dropna=True))
        })
    coverage=pd.DataFrame(coverage)

    quality=pd.DataFrame([{
        "horizon_min":h,
        "usable_forward_observations":int(d[f"ret_{h}m_pct"].notna().sum()),
        "coverage_pct":float(d[f"ret_{h}m_pct"].notna().mean()*100)
    } for h in c["horizons"]])

    notes=pd.DataFrame([
        ["Version","V2.4 Interaction Evidence"],
        ["Input","V1.6 canonical market-state cache"],
        ["Interaction scope","Predefined 2-way and 3-way combinations; no unrestricted combinatorial search"],
        ["Duplicate-control","MWPL state/bin and price_oi_state/futures_positioning aliases are not separately scored"],
        ["Forward outcome","Same symbol + same session; first actual observation at or after requested horizon"],
        ["Minimum pooled observations",min_obs],
        ["Minimum per-day observations",min_day_obs],
        ["Interpretation","Associations only; no causal or profitability claim"],
        ["Validation status","Discovery only; later sessions must be held out for confirmation"]
    ],columns=["item","value"])

    out=Path(c["output_dir"])
    out.mkdir(parents=True,exist_ok=True)
    report=out/"evidence_fusion_V2_4_interaction.xlsx"
    with pd.ExcelWriter(report,engine="openpyxl") as w:
        contrib.to_excel(w,sheet_name="Interaction_Contribution",index=False)
        stability.to_excel(w,sheet_name="Day_Stability",index=False)
        day.to_excel(w,sheet_name="Day_Detail",index=False)
        base.to_excel(w,sheet_name="Horizon_Base_Rates",index=False)
        coverage.to_excel(w,sheet_name="Feature_Coverage",index=False)
        quality.to_excel(w,sheet_name="Forward_Data_Quality",index=False)
        notes.to_excel(w,sheet_name="Research_Notes",index=False)

    print(json.dumps({
        "status":"SUCCESS","observations":len(d),
        "symbols":int(d._symbol.nunique()),
        "snapshots":int(d._ts.nunique()),
        "two_way_definitions":len(pairs),
        "three_way_definitions":len(triples),
        "interaction_rows":len(contrib),
        "day_stability_rows":len(stability),
        "forward_observations":{f"{h}m":int(d[f"ret_{h}m_pct"].notna().sum()) for h in c["horizons"]},
        "report":str(report),
        "research_status":"PRELIMINARY - interaction evidence discovery only; no validated trading rule"
    },separators=(",",":")))

if __name__=="__main__":
    main()
