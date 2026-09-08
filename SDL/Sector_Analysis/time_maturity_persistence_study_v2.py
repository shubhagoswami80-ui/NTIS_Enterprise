#!/usr/bin/env python3
"""NTIS SDL - timestamp-aware maturity/persistence descriptive study V2.

Cache-only. Uses the actual Smart Replay output filenames. It does NOT scan raw
XLSX/PDF/image sources and does not modify production/dashboard code.

Semantics: each replay anchor is assigned to a clock-time cohort using its own
recorded timestamp. Outcomes are already-forward replay outcomes attached to
that anchor. Therefore the study asks whether setups whose evidence/anchor was
available by a given clock cutoff had different subsequent outcomes. It does
NOT claim that later evidence was known at an earlier time.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

DEFAULT_ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\.sector_intelligence")
DISCOVERY = "smart_replay_hit_discovery"
OUT = "time_maturity_persistence_study_v2"
WINDOWS = (5, 10, 15)
CUTOFFS = ("09:30", "09:45", "10:00", "10:15")
RANGES = (("09:15-09:30", 555, 570), ("09:30-09:45", 570, 585), ("09:45-10:00", 585, 600), ("10:00-10:15", 600, 615), ("10:15+", 615, 1440))


def find_discovery(root: Path) -> Path:
    p = root / DISCOVERY
    if p.is_dir(): return p
    hits = list(root.rglob(DISCOVERY)) if root.exists() else []
    if hits: return hits[0]
    raise FileNotFoundError(f"Discovery directory not found under {root}")


def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def timestamp_col(df: pd.DataFrame):
    for c in ("timestamp", "observation_timestamp", "event_timestamp", "datetime", "date_time"):
        if c in df.columns: return c
    return None


def parse_ts(df: pd.DataFrame) -> pd.Series:
    c = timestamp_col(df)
    if c is None: return pd.Series(pd.NaT, index=df.index)
    return pd.to_datetime(df[c], errors="coerce")


def num(df, c):
    return pd.to_numeric(df[c], errors="coerce") if c in df.columns else pd.Series(float("nan"), index=df.index)


def rate(df, c):
    if c not in df.columns or df.empty: return None
    s = num(df, c)
    if s.notna().any(): return float(s.mean())
    # Some replay files encode boolean outcomes as strings.
    b = df[c].astype(str).str.strip().str.lower().map({"true":1,"1":1,"yes":1,"false":0,"0":0,"no":0})
    return float(b.mean()) if b.notna().any() else None


def stats(df):
    out = {"n": int(len(df))}
    for c in ("favorable", "holding", "clean_hold", "retrace"):
        out[c+"_rate"] = rate(df, c)
    for c, k in (("favorable_pct","mean_favorable_pct"),("adverse_pct","mean_adverse_pct"),("final_pct","mean_final_pct"),("mfe_pct","mean_mfe_pct"),("mae_pct","mean_mae_pct")):
        out[k] = float(num(df,c).mean()) if c in df.columns and num(df,c).notna().any() else None
    if "path_class" in df.columns and len(df):
        vc = df["path_class"].fillna("UNKNOWN").astype(str).value_counts()
        out["path_classes"] = {str(k): int(v) for k,v in vc.items()}
    return out


def clock_minutes(ts):
    return ts.dt.hour * 60 + ts.dt.minute + ts.dt.second / 60.0


def load_outcomes(d):
    frames=[]
    inventory=[]
    for w in WINDOWS:
        p=d/f"orb_evidence_outcomes_{w}m.csv"
        if not p.exists():
            inventory.append({"orb_minutes":w,"file":str(p),"exists":False,"rows":0})
            continue
        df=read(p)
        df["__ts"]=parse_ts(df)
        df["__orb_minutes"]=w
        frames.append(df)
        inventory.append({"orb_minutes":w,"file":str(p),"exists":True,"rows":int(len(df)),"timestamp_column":timestamp_col(df),"timestamp_valid":int(df["__ts"].notna().sum())})
    return frames, inventory


def run(root, top_n=100):
    d=find_discovery(root); out=root/OUT; out.mkdir(parents=True,exist_ok=True)
    frames, inventory=load_outcomes(d)
    if not frames: raise FileNotFoundError("No orb_evidence_outcomes_[5m|10m|15m].csv found")
    all_df=pd.concat(frames,ignore_index=True,sort=False)
    valid=all_df[all_df["__ts"].notna()].copy()
    valid["__clock"]=clock_minutes(valid["__ts"])
    valid["__date"]=valid["__ts"].dt.date
    valid["__symbol"]=valid["symbol"] if "symbol" in valid.columns else ""

    cohort_rows=[]
    for w in WINDOWS:
        wd=valid[valid["__orb_minutes"]==w]
        for name,lo,hi in RANGES:
            sub=wd[(wd["__clock"]>=lo)&(wd["__clock"]<hi)]
            s=stats(sub)
            cohort_rows.append({"orb_minutes":w,"clock_cohort":name,**s,"dates":int(sub["__date"].nunique()),"symbols":int(sub["__symbol"].nunique())})
        for cutoff in CUTOFFS:
            hh,mm=map(int,cutoff.split(":")); c=hh*60+mm
            sub=wd[wd["__clock"]<=c]
            s=stats(sub)
            cohort_rows.append({"orb_minutes":w,"clock_cohort":"BY_"+cutoff,**s,"dates":int(sub["__date"].nunique()),"symbols":int(sub["__symbol"].nunique())})
    cohort=pd.DataFrame(cohort_rows); cohort.to_csv(out/"maturity_window_summary.csv",index=False)

    # Per-pattern maturity comparison, using only patterns already found at >=60%.
    pat_frames=[]
    for w in WINDOWS:
        p=d/f"pattern_candidates_{w}m.csv"
        if p.exists():
            x=read(p); x["__orb_minutes"]=w; pat_frames.append(x)
    patterns=pd.concat(pat_frames,ignore_index=True,sort=False) if pat_frames else pd.DataFrame()
    if not patterns.empty and "favorable_rate" in patterns.columns:
        patterns["__rate"]=pd.to_numeric(patterns["favorable_rate"],errors="coerce")
        patterns=patterns[patterns["__rate"]>=0.60].sort_values("__rate",ascending=False).drop_duplicates(["__orb_minutes","pattern","target" ] if "target" in patterns.columns else ["__orb_minutes","pattern"]).head(top_n)

    rows=[]
    for _,p in patterns.iterrows():
        w=int(p["__orb_minutes"]); base=valid[valid["__orb_minutes"]==w]
        # Exact boolean-factor matching; no eval.
        text=str(p.get("factors",p.get("pattern","")))
        factors=[z.strip() for z in text.split("&") if z.strip()]
        mask=pd.Series(True,index=base.index)
        missing=[]
        for f in factors:
            if f not in base.columns: missing.append(f); mask &= False
            else:
                s=base[f]
                if s.dtype==bool: b=s.fillna(False)
                else: b=s.astype(str).str.strip().str.lower().isin(["true","1","yes","y","t"])
                mask &= b
        matched=base.loc[mask]
        for cutoff in CUTOFFS:
            hh,mm=map(int,cutoff.split(":")); c=hh*60+mm
            sub=matched[matched["__clock"]<=c]
            s=stats(sub)
            rows.append({"orb_minutes":w,"pattern":p.get("pattern",""),"factors":text,"target":p.get("target",""),"reported_rate":p.get("favorable_rate",""),"reported_n":p.get("n",""),"maturity_cutoff":cutoff,"matched_rows":int(len(matched)),"missing_factors":"|".join(missing),**s})
    pm=pd.DataFrame(rows); pm.to_csv(out/"maturity_by_pattern.csv",index=False)
    if not pm.empty:
        top=pm.sort_values(["holding_rate","favorable_rate","n"],ascending=False,na_position="last").head(100)
    else: top=pm
    top.to_csv(out/"maturity_persistence_top100.csv",index=False)

    # A compact file emphasizing the actual clock cohorts rather than cumulative cutoffs.
    cohort[cohort["clock_cohort"].isin([r[0] for r in RANGES])].to_csv(out/"clock_cohort_summary.csv",index=False)
    summary={"status":"READY","cache_only":True,"raw_source_scan":False,"discovery_dir":str(d),"output_dir":str(out),"input_files":inventory,"total_timestamped_rows":int(len(valid)),"orb_windows":sorted(valid["__orb_minutes"].unique().tolist()),"clock_cohorts":[x[0] for x in RANGES],"cumulative_cutoffs":list(CUTOFFS),"patterns_analyzed":int(len(patterns)),"max_existing_favorable_rate":float(pd.to_numeric(patterns["favorable_rate"],errors="coerce").max()) if not patterns.empty else None,"hard_validation_gate":0.80,"interpretation":"Anchor-timestamp cohort study. It does not use later evidence to make an earlier decision and does not claim that clock time alone is causal."}
    (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2,default=str),encoding="utf-8")
    return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,default=DEFAULT_ROOT); ap.add_argument("--top-n",type=int,default=100); args=ap.parse_args(); print(json.dumps({"TIME_MATURITY_PERSISTENCE_STUDY_V2":"READY","OUTPUT":str(run(args.root,args.top_n))},indent=2))

if __name__=="__main__": main()
