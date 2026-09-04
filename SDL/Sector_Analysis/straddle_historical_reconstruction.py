from pathlib import Path
import pandas as pd
import json, re, hashlib
from concurrent.futures import ThreadPoolExecutor

# Research-only. Production SDL engines are never imported or modified.
# This file lives at SDL/Sector_Analysis/, therefore parents[1] is SDL.
SDL_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = SDL_ROOT / "data"
OUT = SDL_ROOT / "Sector_Analysis" / ".sector_intelligence" / "straddle_historical_research"
RAW_ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot")

ALIASES = {
    "symbol":["symbol","ticker","scrip","stock"], "date":["trading_date","trade_date","date"],
    "timestamp":["observation_timestamp","timestamp","datetime","time","date_time"],
    "open":["open"],"high":["high"],"low":["low"],"close":["close"],
    "price":["price","cmp","current price","current_price"],
    "straddle":["atm straddle","atm_straddle","atm straddle price","straddle"],
    "straddle_pct":["atm straddle %","atm_straddle_pct","atm straddle pct","straddle %"],
    "price_chg_pct":["price chg %","price_chg_pct","price change %","price_change_pct"],
    "oi_chg_pct":["oi chg %","oi_chg_pct","oi change %","oi_change_pct"],
    "pcr_chg_pct":["pcr chg %","pcr_chg_pct","pcr change %"],
    "ce_oi_chg_pct":["tot ce oi chg %","ce oi chg %","ce_oi_chg_pct","ce oi change %"],
    "pe_oi_chg_pct":["tot pe oi chg %","pe oi chg %","pe_oi_chg_pct","pe oi change %"],
    "pe_ce_oi_chg":["tot pe-ce oi chg","pe-ce oi chg","pe_ce_oi_chg","pe minus ce"],
    "volume_chg_pct":["volume chg %","volume_chg_pct","volume change %"],
    "buildup":["buildup"],
}

def norm(x): return re.sub(r"[^a-z0-9]+"," ",str(x).strip().lower()).strip()
def resolve(df, aliases):
    cols={norm(c):c for c in df.columns}
    return next((cols[norm(a)] for a in aliases if norm(a) in cols),None)

def load(path):
    try:
        if path.suffix.lower()==".csv": return pd.read_csv(path,low_memory=False)
        return pd.read_excel(path)
    except Exception: return None

def parse_ts(s):
    # Parse each source value to Python datetime independently, then build
    # one UTC-naive-compatible pandas datetime Series. This avoids pandas
    # 3.x lossless-cast failures when mixing seconds and microseconds.
    s = s.astype("string").str.strip()
    vals = []
    for v in s:
        if v is None or pd.isna(v) or not str(v).strip():
            vals.append(pd.NaT)
            continue
        text = str(v).strip()
        dt = None
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%d-%m-%Y %H:%M:%S.%f",
            "%d-%m-%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S.%f",
            "%d/%m/%Y %H:%M:%S",
        ):
            try:
                dt = pd.Timestamp.strptime(text, fmt)
                break
            except Exception:
                pass
        if dt is None:
            try:
                dt = pd.to_datetime(text, errors="coerce")
            except Exception:
                dt = pd.NaT
        vals.append(dt)
    return pd.Series(pd.array(vals, dtype="datetime64[ns]"), index=s.index)

def process(p):
    df=load(p)
    if df is None: return {"inventory":{"path":str(p),"readable":False},"table":None}
    mp={k:resolve(df,v) for k,v in ALIASES.items()}
    inv={"path":str(p),"readable":True,"rows":len(df),
         **{f"field_{k}":v for k,v in mp.items()}}
    if not mp["symbol"]: return {"inventory":inv,"table":None}
    x=pd.DataFrame({"symbol":df[mp["symbol"]].astype("string").str.strip().str.upper()})
    for k,c in mp.items():
        if k!="symbol": x[k]=df[c] if c else pd.NA
    m=re.search(r"(20\d{2}-\d{2}-\d{2})",str(p))
    x["source_date"]=m.group(1) if m else pd.NA
    x["source_file"]=str(p); x["source_name"]=p.name
    return {"inventory":inv,"table":x}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files=sorted(p for p in RAW_ROOT.rglob("*")
                 if p.is_file() and p.suffix.lower() in {".csv",".xlsx",".xls"})
    # Parallel file reads: faster on large historical repositories.
    workers=min(8,max(2,(__import__("os").cpu_count() or 4)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results=list(ex.map(process,files))
    inv=[r["inventory"] for r in results]
    tables=[r["table"] for r in results if r["table"] is not None]
    pd.DataFrame(inv).to_csv(OUT/"raw_inventory.csv",index=False)
    if not tables:
        print("NO SYMBOL-BEARING TABLES FOUND"); return

    obs=pd.concat(tables,ignore_index=True)
    obs["timestamp_parsed"]=parse_ts(obs["timestamp"])
    obs["date_parsed"]=pd.to_datetime(obs["date"],errors="coerce")
    obs["source_date_parsed"]=pd.to_datetime(obs["source_date"],errors="coerce")
    obs["event_date"]=obs["date_parsed"].fillna(obs["source_date_parsed"])
    obs=obs.sort_values(["event_date","symbol","timestamp_parsed"],na_position="last")
    obs.to_csv(OUT/"canonical_observations.csv",index=False)

    cov=[]
    for f in ALIASES:
        if f=="symbol": continue
        n=int(obs[f].notna().sum())
        cov.append({"field":f,"rows":len(obs),"non_null":n,"coverage_pct":round(n/len(obs)*100,2)})
    pd.DataFrame(cov).to_csv(OUT/"source_field_coverage.csv",index=False)

    day=obs.groupby("event_date",dropna=False).agg(
        observations=("symbol","size"),unique_symbols=("symbol","nunique"),
        timestamped=("timestamp_parsed",lambda s:int(s.notna().sum())),
        source_files=("source_file","nunique")).reset_index()
    day["day_status"]=day["timestamped"].map(lambda n:"OBSERVATIONS_AVAILABLE" if n else "PARTIAL_OR_UNTIMED")
    pd.DataFrame(day).to_csv(OUT/"day_completeness.csv",index=False)

    event_paths=[DATA_ROOT/"output"/"tradable_events"/"breakout_events.csv",
                 DATA_ROOT/"output"/"tradable_events"/"approaching_breakouts.csv"]
    events=[]
    for p in event_paths:
        if not p.exists(): continue
        d=pd.read_csv(p,low_memory=False)
        sm=resolve(d,ALIASES["symbol"]); tm=resolve(d,ALIASES["timestamp"]); dm=resolve(d,ALIASES["date"])
        if not sm: continue
        e=pd.DataFrame({"symbol":d[sm].astype("string").str.strip().str.upper(),"outcome_source":p.name})
        e["outcome_timestamp"]=parse_ts(d[tm]) if tm else pd.NaT
        e["outcome_date"]=pd.to_datetime(d[dm],errors="coerce") if dm else pd.NaT
        events.append(e)
    trace_count=0
    if events:
        ev=pd.concat(events,ignore_index=True).drop_duplicates()
        ev.to_csv(OUT/"event_reconstruction.csv",index=False)
        timed=obs.dropna(subset=["timestamp_parsed"])
        traces=[]
        for eid,e in ev.reset_index(drop=True).iterrows():
            x=timed[timed.symbol==e.symbol]
            if pd.notna(e.outcome_date): x=x[x.event_date==e.outcome_date]
            if pd.notna(e.outcome_timestamp): x=x[x.timestamp_parsed<e.outcome_timestamp]
            if x.empty: continue
            x=x.sort_values("timestamp_parsed").tail(10).copy()
            x["event_id"]=eid; x["outcome_timestamp"]=e.outcome_timestamp
            x["outcome_source"]=e.outcome_source; traces.append(x)
        if traces:
            tr=pd.concat(traces,ignore_index=True)
            tr.to_csv(OUT/"pre_breakout_trace.csv",index=False)
            trace_count=len(tr)

    summary={"raw_root":str(RAW_ROOT),"raw_files_discovered":len(files),
             "readable_tables":sum(x.get("readable",False) for x in inv),
             "symbol_bearing_tables":len(tables),"pre_breakout_trace_rows":trace_count,
             "recursive_all_months":True,"partial_days_retained":True,
             "parallel_workers":workers,"research_only":True,
             "production_modified":False,
             "lookahead_policy":"Only strictly earlier timestamps are eligible.",
             "missing_data_policy":"Missing remains missing; never zero-filled."}
    (OUT/"research_summary.json").write_text(json.dumps(summary,indent=2,default=str),encoding="utf-8")
    print("SMART MULTI-MONTH RECONSTRUCTION COMPLETE")
    print("RAW FILES:",len(files))
    print("READABLE TABLES:",summary["readable_tables"])
    print("SYMBOL-BEARING TABLES:",len(tables))
    print("PRE-BREAKOUT TRACE ROWS:",trace_count)
    print("OUTPUT:",OUT)

if __name__=="__main__": main()
