
from pathlib import Path
import argparse, json
import pandas as pd
import numpy as np

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    # V4/V5 may store the cache either inside the supplied study output
    # directory or directly under its .sector_intelligence parent.
    # Search only these existing research locations; never scan raw XLSX.
    candidates=[out/"canonical_strength_observations.csv", out.parent/"canonical_strength_observations.csv"]
    candidates.extend(sorted(out.parent.rglob("canonical_strength_observations.csv")))
    cache=next((p for p in candidates if p.is_file()), None)
    if cache is None:
        raise SystemExit("CACHE_NOT_FOUND: searched study output and .sector_intelligence descendants")
    print(f"CACHE_FOUND: {cache}")
    df=pd.read_csv(cache, low_memory=False)
    for c in ["timestamp","price_chg","price_chg_pct","open","high","low","close"]:
        if c in df: df[c]=pd.to_numeric(df[c],errors="coerce") if c!="timestamp" else pd.to_datetime(df[c],errors="coerce")
    if "symbol" in df: df["symbol"]=df["symbol"].astype(str).str.strip()
    df["derived_price_direction"]=np.where(df["price_chg"]>0,"UP",np.where(df["price_chg"]<0,"DOWN","FLAT"))
    df.loc[df["price_chg"].isna(),"derived_price_direction"]=""
    df["trade_date"]=df["timestamp"].dt.date.astype(str)
    g=df.groupby(["symbol","trade_date"],dropna=False)
    stats={
      "rows":len(df),"symbols":df.symbol.nunique(),"dates":df.trade_date.nunique(),
      "timestamped":int(df.timestamp.notna().sum()),
      "price_chg_present":int(df.price_chg.notna().sum()),
      "price_chg_pct_present":int(df.price_chg_pct.notna().sum()),
      "ohlc_complete":int(df[["open","high","low","close"]].notna().all(axis=1).sum()),
      "close_present":int(df.close.notna().sum()),
      "unique_symbol_date_pairs":int(g.ngroups),
      "symbol_date_pairs_multiple_timestamps":int((g["timestamp"].nunique()>1).sum()),
      "rows_in_pairs_with_multiple_timestamps":int(g["timestamp"].transform("nunique").gt(1).sum()),
    }
    # timestamp distribution and direction availability
    ts=df.timestamp.dropna()
    if len(ts):
        stats["timestamp_min"]=str(ts.min()); stats["timestamp_max"]=str(ts.max())
    else:
        stats["timestamp_min"]=""; stats["timestamp_max"]=""
    stats["direction_up"]=int((df.derived_price_direction=="UP").sum())
    stats["direction_down"]=int((df.derived_price_direction=="DOWN").sum())
    stats["direction_flat"]=int((df.derived_price_direction=="FLAT").sum())
    stats["direction_unknown"]=int(df.derived_price_direction.eq("").sum())
    # For every row, count later timeline rows in same symbol/date with valid close.
    t=df[["symbol","trade_date","timestamp","close","high","low"]].dropna(subset=["symbol","timestamp"]).copy()
    t=t.sort_values(["symbol","trade_date","timestamp"])
    t["later_count"]=t.groupby(["symbol","trade_date"])["timestamp"].transform(lambda s: s.size-1-np.arange(len(s)))
    stats["rows_with_later_timestamp"]=int((t.later_count>0).sum())
    stats["rows_without_later_timestamp"]=int((t.later_count<=0).sum())
    # timestamp quality: identical timestamp across many rows
    dup=t.groupby(["symbol","trade_date","timestamp"]).size()
    stats["duplicate_symbol_date_timestamp_groups"]=int((dup>1).sum())
    stats["duplicate_rows_in_groups"]=int(dup[dup>1].sum()-len(dup[dup>1])) if (dup>1).any() else 0
    # samples
    cols=[c for c in ["symbol","trade_date","timestamp","family","source_file","price_chg","price_chg_pct","open","high","low","close","fut_state","fut_num","fut_pct","ce_num","pe_num","pec_num"] if c in df]
    df[cols].sort_values(["symbol","timestamp"]).head(500).to_csv(out/"sample_first_500.csv",index=False)
    # per-family quality
    fam=df.groupby("family",dropna=False).agg(rows=("symbol","size"),symbols=("symbol","nunique"),
        timestamps=("timestamp","nunique"),price_chg=("price_chg","count"),close=("close","count")).reset_index()
    fam.to_csv(out/"family_quality.csv",index=False)
    # pair-level timestamp counts distribution
    pair=g["timestamp"].nunique().value_counts().sort_index().rename_axis("timestamp_count").reset_index(name="symbol_date_pairs")
    pair.to_csv(out/"symbol_date_timestamp_count_distribution.csv",index=False)
    (out/"diagnostic_summary.json").write_text(json.dumps(stats,indent=2,default=str))
    print(json.dumps(stats,indent=2,default=str))
    print("DIAGNOSTIC_COMPLETE")

if __name__=="__main__": main()
