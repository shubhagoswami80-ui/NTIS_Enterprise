from __future__ import annotations
import argparse,json
from pathlib import Path
from datetime import time
import pandas as pd

DEFAULT_ROOT=Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
CUTS={"09:30":time(9,30),"09:45":time(9,45),"10:00":time(10,0),"10:15":time(10,15)}

def norm(x): return str(x).strip().lower().replace(" ","_").replace("-","_").replace("%","pct")
def col(df,names):
    m={norm(c):c for c in df.columns}
    for n in names:
        if norm(n) in m:return m[norm(n)]
    return None

def main():
    ap=argparse.ArgumentParser(description="Timestamp-aware ORB maturity evidence study; cache-only.")
    ap.add_argument("--root",default=str(DEFAULT_ROOT)); a=ap.parse_args()
    root=Path(a.root); intel=root/".sector_intelligence"; disc=intel/"smart_replay_hit_discovery"
    out=intel/"time_maturity_persistence_study_v5"; out.mkdir(parents=True,exist_ok=True)
    canon=intel/"data_strength_combination_study"/"canonical_strength_observations.csv"
    multi=disc/"multi_window_outcomes.csv"
    summary={"status":"FAILED","cache_only":True,"raw_source_scan":False,"output_dir":str(out),
             "canonical_source":str(canon),"orb_outcome_source":str(multi),
             "maturity_cutoffs":list(CUTS),"primary_outcome":"existing reached_0.5x from multi_window_outcomes.csv",
             "hard_validation_gate":0.8}
    if not canon.exists() or not multi.exists():
        summary["reason"]="Required cache missing"; (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2)); return 2

    # Load canonical timestamped evidence, only fields needed for matching and evidence availability.
    cparts=[]
    for ch in pd.read_csv(canon,low_memory=False,chunksize=200000):
        ch.columns=[norm(c) for c in ch.columns]
        ts=col(ch,["timestamp"]); sym=col(ch,["symbol"]); td=col(ch,["trade_date","trading_date","date"])
        if ts is None or sym is None: continue
        ch["_ts"]=pd.to_datetime(ch[ts],errors="coerce"); ch["_symbol"]=ch[sym].astype(str).str.strip()
        ch["_date"]=pd.to_datetime(ch[td],errors="coerce").dt.date if td else ch["_ts"].dt.date
        ch=ch[ch["_ts"].notna()&ch["_date"].notna()&ch["_symbol"].ne("")]
        keep=["_ts","_symbol","_date"]+[x for x in ["price_direction","direction_agreement","core_evidence_count","magnitude_count","strength_bucket","persistent","option_direction","fut_direction","price_chg_pct","volume_pct","ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct","fut_num","fut_pct","fut_state"] if x in ch.columns]
        cparts.append(ch[keep])
    c=pd.concat(cparts,ignore_index=True).sort_values(["_symbol","_date","_ts"]).drop_duplicates(["_symbol","_date","_ts"])
    # Existing replay outcomes are authoritative for the target. We do not recompute target.
    m=pd.read_csv(multi,low_memory=False)
    m.columns=[norm(x) for x in m.columns]
    for required in ["orb_minutes","symbol","trade_date","anchor_time","orb_direction","reached_0_5x"]:
        if required not in m.columns:
            summary["reason"]=f"Missing required outcome field: {required}"
            (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2)); return 3
    m["_symbol"]=m["symbol"].astype(str).str.strip()
    m["_date"]=pd.to_datetime(m["trade_date"],errors="coerce").dt.date
    m["_anchor"]=pd.to_datetime(m["anchor_time"],errors="coerce")
    m["reached_0_5x"]=m["reached_0_5x"].astype(str).str.strip().str.lower().isin(["true","1","yes","y"])
    # For each ORB anchor, determine the evidence state at each cutoff on the same symbol/date.
    rows=[]
    cgroups={(k[0],k[1]):g for k,g in c.groupby(["_symbol","_date"],sort=False)}
    for _,e in m.iterrows():
        key=(e["_symbol"],e["_date"]); g=cgroups.get(key)
        if g is None or pd.isna(e["_anchor"]): continue
        direction=str(e["orb_direction"]).upper()
        for label,cut in CUTS.items():
            eligible=g[g["_ts"].dt.time<=cut]
            if eligible.empty: continue
            arow=eligible.iloc[-1]
            # Only evidence available at cutoff; outcome remains the already-defined ORB outcome.
            rec={"orb_minutes":e["orb_minutes"],"symbol":e["_symbol"],"trade_date":str(e["_date"]),
                 "orb_anchor_time":str(e["_anchor"]),"orb_direction":direction,"maturity":label,
                 "evidence_timestamp":str(arow["_ts"]),"reached_0_5x":bool(e["reached_0_5x"])}
            for x in ["price_direction","direction_agreement","core_evidence_count","magnitude_count","strength_bucket","persistent","option_direction","fut_direction","price_chg_pct","volume_pct","ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct","fut_num","fut_pct","fut_state"]:
                if x in arow: rec[x]=arow[x]
            rec["direction_agreement_with_orb"] = (
                ("UP" in str(arow.get("price_direction","")).upper() and "UP" in direction) or
                ("DOWN" in str(arow.get("price_direction","")).upper() and "DOWN" in direction)
            )
            rows.append(rec)
    r=pd.DataFrame(rows)
    r.to_csv(out/"orb_maturity_evidence.csv",index=False)
    summaries=[]
    for (orb,mat),g in r.groupby(["orb_minutes","maturity"],sort=True):
        q={"orb_minutes":int(orb),"maturity":mat,"n":len(g),"symbols":g.symbol.nunique(),"dates":g.trade_date.nunique(),
           "reached_0_5x_rate":float(g.reached_0_5x.mean()) if len(g) else None,
           "direction_agreement_rate":float(g.direction_agreement_with_orb.mean()) if len(g) else None}
        if "strength_bucket" in g:
            q["strong_bucket_rate"]=float(g.strength_bucket.astype(str).str.contains("strong",case=False,na=False).mean())
        summaries.append(q)
    pd.DataFrame(summaries).to_csv(out/"maturity_window_summary.csv",index=False)
    # Descriptive evidence-state rates at each maturity; minimum 20 observations.
    ev=[]
    bools=["direction_agreement_with_orb","persistent"]
    for (orb,mat),g in r.groupby(["orb_minutes","maturity"],sort=True):
        for b in bools:
            if b in g:
                z=g[g[b].notna()]
                if len(z)>=20:
                    for val,h in z.groupby(b):
                        ev.append({"orb_minutes":int(orb),"maturity":mat,"feature":b,"state":str(val),
                                   "n":len(h),"dates":h.trade_date.nunique(),"symbols":h.symbol.nunique(),
                                   "reached_0_5x_rate":float(h.reached_0_5x.mean())})
    pd.DataFrame(ev).to_csv(out/"maturity_evidence_state_rates.csv",index=False)
    summary.update({"status":"READY","canonical_rows":len(c),"canonical_symbols":c._symbol.nunique(),
                    "canonical_dates":c._date.nunique(),"orb_outcome_rows":len(m),
                    "matched_maturity_rows":len(r),"orb_windows":sorted(r.orb_minutes.unique().tolist()) if len(r) else [],
                    "maturity_results":summaries,
                    "note":"Maturity is evidence availability only. The primary 0.5x-straddle outcome is taken unchanged from the existing ORB replay outcome cache; no target is recomputed from canonical data. This is descriptive association, not causal proof, and >=80% remains the hard validation gate."})
    (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2,allow_nan=True))
    print(json.dumps(summary,indent=2))
    return 0
if __name__=="__main__": raise SystemExit(main())
