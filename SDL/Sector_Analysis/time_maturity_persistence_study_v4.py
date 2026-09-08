from __future__ import annotations
import argparse, json
from pathlib import Path
from datetime import time
import pandas as pd

DEFAULT_ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
CUTS = {"09:30": time(9,30), "09:45": time(9,45), "10:00": time(10,0), "10:15": time(10,15)}
ABS_LEVELS = [0.50, 0.75, 1.00, 1.25, 1.50]

def norm(s):
    return str(s).strip().lower().replace(" ","_").replace("-","_").replace("%","pct")

def pick(df, names):
    mp={norm(c):c for c in df.columns}
    for n in names:
        if norm(n) in mp: return mp[norm(n)]
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    a=ap.parse_args()
    root=Path(a.root); intel=root/".sector_intelligence"
    out=intel/"time_maturity_persistence_study_v4"; out.mkdir(parents=True,exist_ok=True)
    cache=None
    for p in [intel/"data_strength_combination_study"/"canonical_strength_observations.csv",
              intel/"smart_replay_hit_discovery"/"orb_anchors_5m.csv",
              intel/"smart_replay_hit_discovery"/"orb_anchors.csv"]:
        if p.exists() and p.stat().st_size: cache=p; break
    summary={"status":"FAILED","cache_only":True,"raw_source_scan":False,"output_dir":str(out),
             "hard_validation_gate":0.8,"primary_target":"0.5x opening straddle",
             "secondary_absolute_move_levels_pct":ABS_LEVELS,"maturity_cutoffs":list(CUTS)}
    if cache is None:
        summary["reason"]="No cache found"; (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2)); return 2

    chunks=[]
    for ch in pd.read_csv(cache,low_memory=False,chunksize=200000):
        ch.columns=[norm(c) for c in ch.columns]
        ts=pick(ch,["timestamp","observation_timestamp","event_timestamp","datetime","date_time"])
        sym=pick(ch,["symbol","ticker"])
        td=pick(ch,["trade_date","trading_date","date"])
        if ts is None or sym is None: continue
        ch["_ts"]=pd.to_datetime(ch[ts],errors="coerce")
        ch["_symbol"]=ch[sym].astype(str).str.strip()
        ch["_date"]=pd.to_datetime(ch[td],errors="coerce").dt.date if td else ch["_ts"].dt.date
        ch=ch[ch["_ts"].notna() & ch["_date"].notna() & ch["_symbol"].ne("")]
        if not ch.empty: chunks.append(ch)
    if not chunks:
        summary["reason"]="No timestamped symbol rows"; (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2)); return 3
    df=pd.concat(chunks,ignore_index=True).sort_values(["_symbol","_date","_ts"]).drop_duplicates(["_symbol","_date","_ts"])
    px=pick(df,["close","current_price","cmp","price"])
    if px is None:
        summary["reason"]="No price field"; (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2)); return 4
    df["_px"]=pd.to_numeric(df[px],errors="coerce")
    # Straddle field must be explicitly present; no proxy/fabrication.
    st=pick(df,["atm_straddle_pct","current_atm_straddle_pct","atm_straddle"])
    if st is None:
        summary["reason"]="No ATM straddle field in canonical cache; primary 0.5x target cannot be reconstructed from this cache."
        summary["canonical_rows"]=len(df); summary["timestamped_rows"]=int(df["_ts"].notna().sum())
        (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2)); return 5
    df["_straddle"]=pd.to_numeric(df[st],errors="coerce")
    results=[]
    for label,cut in CUTS.items():
        elig=df[df["_ts"].dt.time<=cut]
        anchors=elig.groupby(["_symbol","_date"],as_index=False).tail(1).copy()
        for _,an in anchors.iterrows():
            g=df[(df["_symbol"]==an["_symbol"])&(df["_date"]==an["_date"])&(df["_ts"]>an["_ts"])].copy()
            g=g[g["_px"].notna()]
            p0=an["_px"]; s=an["_straddle"]
            if pd.isna(p0) or p0==0 or g.empty: continue
            d=str(an.get("price_direction","")).upper()
            sign=-1 if "DOWN" in d else (1 if "UP" in d else None)
            if sign is None: continue
            moves=(g["_px"]-p0)/p0*100*sign
            fav=float(moves.max()); adv=float(moves.min()); final=float(moves.iloc[-1])
            primary=(fav >= float(s)*0.5) if pd.notna(s) and s>=0 else None
            row={"symbol":an["_symbol"],"trade_date":str(an["_date"]),"maturity":label,
                 "anchor_timestamp":str(an["_ts"]),"anchor_price":float(p0),
                 "opening_or_anchor_straddle_pct":float(s) if pd.notna(s) else None,
                 "primary_target_pct":float(s)*0.5 if pd.notna(s) else None,
                 "primary_0_5x_hit":primary,"favorable_excursion_pct":fav,
                 "adverse_excursion_pct":adv,"final_signed_move_pct":final,
                 "direction":d}
            for x in ABS_LEVELS: row[f"hit_{str(x).replace('.','_')}pct"]=fav>=x
            row["held_primary_at_end"]=(final >= float(s)*0.5) if pd.notna(s) and s>=0 else None
            results.append(row)
    r=pd.DataFrame(results)
    r.to_csv(out/"maturity_anchor_outcomes.csv",index=False)
    summ=[]
    for m,g in r.groupby("maturity",sort=False):
        valid=g[g.primary_0_5x_hit.notna()]
        q={"maturity":m,"n":len(g),"symbols":g.symbol.nunique(),"dates":g.trade_date.nunique(),
           "primary_0_5x_hit_rate":float(valid.primary_0_5x_hit.mean()) if len(valid) else None,
           "primary_0_5x_hold_rate":float(g.held_primary_at_end.dropna().mean()) if g.held_primary_at_end.notna().any() else None,
           "mean_favorable_pct":float(g.favorable_excursion_pct.mean()),
           "mean_adverse_pct":float(g.adverse_excursion_pct.mean()),
           "mean_final_pct":float(g.final_signed_move_pct.mean())}
        for x in ABS_LEVELS:
            q[f"hit_{str(x).replace('.','_')}pct_rate"]=float(g[f"hit_{str(x).replace('.','_')}pct"].mean())
        summ.append(q)
    pd.DataFrame(summ).to_csv(out/"maturity_window_summary.csv",index=False)
    summary.update({"status":"READY","timestamp_source":str(cache),"canonical_rows":len(df),
                    "symbols":df._symbol.nunique(),"dates":df._date.nunique(),
                    "timestamped_rows":int(df._ts.notna().sum()),"price_rows":int(df._px.notna().sum()),
                    "straddle_rows":int(df._straddle.notna().sum()),"maturity_results":summ,
                    "note":"Timestamp-aware descriptive replay. The primary target is 0.5x the straddle value available at the maturity anchor; absolute movement levels are secondary diagnostics. No look-ahead and no strategy acceptance. >=80% remains hard gate."})
    (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2,allow_nan=True))
    print(json.dumps(summary,indent=2))
    return 0
if __name__=="__main__": raise SystemExit(main())
