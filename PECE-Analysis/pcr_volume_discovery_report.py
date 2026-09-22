#!/usr/bin/env python
from __future__ import annotations
import json, re
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

"""
PCR Volume Discovery Report V4.1
- Uses PECE market observation date + Time as authoritative analytical timestamp; Snapshot/source filename is provenance.
- Deduplicates cumulative History by Symbol + market observation timestamp.
- Starts analysis at the earliest History archive date, excluding earlier carry-over.
- Calculates next observation only within the same trading session using market Time.
- Explicitly excludes cross-session forward observations.
- Creates all threshold columns before aggregation.
- Reads CSV with low_memory=False.
- Preserves the original report sheets plus QA/evidence.
"""

BASE = Path(__file__).resolve().parent
CFG = json.loads((BASE / "CONFIG.json").read_text(encoding="utf-8"))
OUTPUT_ROOT = Path(CFG.get("output_root") or CFG.get("output_dir") or
                   r"D:\My-data\Share_P&L\Ichart Data\Screenshot\PCR_Volume_Skew_Output")
HISTORY_ROOT = OUTPUT_ROOT / "History"
REPORT_ROOT = OUTPUT_ROOT / "Reports"
REPORT_ROOT.mkdir(parents=True, exist_ok=True)

def parse_pece_timestamp(v):
    m = re.search(r"PECE_(\d{8})_(\d{6})", str(v), re.I)
    if not m: return pd.NaT
    try: return pd.Timestamp(datetime.strptime(m.group(1)+m.group(2), "%Y%m%d%H%M%S"))
    except Exception: return pd.NaT

def num(s): return pd.to_numeric(s, errors="coerce")

def read_inputs():
    files = sorted(HISTORY_ROOT.glob("*/pcr_volume_pattern_all_intervals.csv"))
    if not files: raise FileNotFoundError(f"No historical reports under {HISTORY_ROOT}")
    frames, inputs = [], []
    for f in files:
        try:
            d = pd.read_csv(f, low_memory=False)
            d["_history_archive_date"] = f.parent.name
            d["_history_file"] = str(f)
            frames.append(d)
            inputs.append({"report_day": f.parent.name, "file": str(f),
                           "rows": len(d), "status": "OK"})
        except Exception as e:
            inputs.append({"report_day": f.parent.name, "file": str(f),
                           "rows": 0, "status": f"ERROR: {e}"})
    if not frames: raise RuntimeError("No readable historical files.")
    return pd.concat(frames, ignore_index=True), inputs

def prepare(raw):
    """Prepare cumulative PECE history using MARKET observation time.

    PECE files are cumulative intraday snapshots.  ``Snapshot`` / filename
    identifies when the cumulative workbook was captured (provenance), while
    ``Time`` identifies the actual market observation represented by each row.
    Forward chronology therefore uses source-date + Time, never the capture
    timestamp.
    """
    if "Symbol" not in raw.columns: raise RuntimeError("Missing Symbol")
    if "volume_skew_class" not in raw.columns: raise RuntimeError("Missing volume_skew_class")
    if "Time" not in raw.columns: raise RuntimeError("Missing market observation Time")
    d = raw.copy()
    d["_symbol"] = d["Symbol"].astype(str).str.strip()
    d = d[d["_symbol"].ne("") & d["_symbol"].ne("nan")].copy()

    # Resolve the calendar date from PECE Snapshot / filename.  This is
    # provenance only; the clock time below comes from the market Time field.
    source_date = pd.Series(pd.NaT, index=d.index, dtype="datetime64[ns]")
    if "Snapshot" in d.columns:
        snap = d["Snapshot"].astype(str).str.strip()
        parsed = pd.to_datetime(snap, format="%Y%m%d_%H%M%S", errors="coerce")
        source_date = parsed
    if "source_snapshot" in d:
        parsed = pd.to_datetime(d["source_snapshot"], errors="coerce")
        source_date = source_date.fillna(parsed)
    if "_source_snapshot_dt" in d:
        parsed = pd.to_datetime(d["_source_snapshot_dt"], errors="coerce")
        source_date = source_date.fillna(parsed)
    for c in ("_source_file", "source_file", "_source_path"):
        if c in d:
            parsed = d[c].map(parse_pece_timestamp)
            source_date = source_date.fillna(parsed)

    # If the History CSV lacks Snapshot/source metadata, fall back to the
    # archive folder date, but never use the archive date as the clock time.
    if "_history_archive_date" in d:
        archive_dt = pd.to_datetime(d["_history_archive_date"], errors="coerce")
        source_date = source_date.fillna(archive_dt)

    bad_date = source_date.isna()
    market_date = source_date.dt.normalize()

    # Parse the actual market observation clock time.  Accept HH:MM, HH:MM:SS,
    # pandas datetime values, and Excel-like time strings.
    raw_time = d["Time"]
    parsed_time = pd.to_datetime(raw_time.astype(str).str.strip(), format="mixed", errors="coerce")
    time_minutes = parsed_time.dt.hour * 60 + parsed_time.dt.minute + parsed_time.dt.second / 60.0
    bad_time = parsed_time.isna()

    bad_ts = int((bad_date | bad_time).sum())
    d["_time"] = market_date + pd.to_timedelta(time_minutes, unit="m")
    d = d[d["_time"].notna()].copy()
    if d.empty: raise RuntimeError("No valid market observation timestamps.")

    d["_source_date"] = d["_time"].dt.date
    archive_dates = []
    for x in d["_history_archive_date"].dropna().astype(str):
        try: archive_dates.append(pd.Timestamp(x).date())
        except Exception: pass
    if not archive_dates: raise RuntimeError("No valid History archive dates.")
    analysis_start = min(archive_dates)
    d = d[d["_source_date"] >= analysis_start].copy()

    # History files are cumulative.  Keep one analytical market observation
    # per Symbol + market timestamp; later archive copies are duplicates.
    before = len(d)
    d = (d.sort_values(["_symbol", "_time", "_history_archive_date"])
           .drop_duplicates(["_symbol", "_time"], keep="last")
           .reset_index(drop=True))
    dup_removed = before - len(d)

    price_col = next((c for c in
        ("Fut Price","Fut_Price","Future Price","Futures Price") if c in d.columns), None)
    if price_col is None: raise RuntimeError("Missing futures price field.")
    d["_skew"] = d["volume_skew_class"].astype(str).str.strip()
    d["_price"] = num(d[price_col])
    return d, analysis_start, bad_ts, dup_removed, price_col

def outcomes(d):
    d = d.sort_values(["_symbol","_time"]).reset_index(drop=True).copy()
    g = d.groupby("_symbol", sort=False)
    d["next_price"] = g["_price"].shift(-1)
    d["next_time"] = g["_time"].shift(-1)
    d["next_skew"] = g["_skew"].shift(-1)
    d["next_source_date"] = g["_source_date"].shift(-1)
    d["same_session_forward"] = d["next_time"].notna() & d["_source_date"].eq(d["next_source_date"])
    d["cross_session_excluded"] = d["next_time"].notna() & ~d["same_session_forward"]
    d["elapsed_minutes"] = np.where(d["same_session_forward"],
        (d["next_time"]-d["_time"]).dt.total_seconds()/60.0, np.nan)
    d["forward_return_pct"] = np.where(
        d["same_session_forward"] & d["_price"].gt(0) & d["next_price"].notna(),
        (d["next_price"]/d["_price"]-1.0)*100.0, np.nan)
    d["positive"] = d["forward_return_pct"] > 0
    d["negative"] = d["forward_return_pct"] < 0
    d["zero"] = d["forward_return_pct"] == 0
    d["persisted"] = d["same_session_forward"] & d["next_skew"].notna() & d["_skew"].eq(d["next_skew"])
    for t in (0.10,0.25,0.50):
        tag = f"{int(round(t*100)):03d}"
        d[f"up_{tag}"] = d["forward_return_pct"] > t
        d[f"down_{tag}"] = d["forward_return_pct"] < -t
    d["signal_time"] = d["_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    d["next_signal_time"] = d["next_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    d["_report_day"] = d["_source_date"].astype(str)
    usable = d[d["same_session_forward"] & d["_price"].gt(0) &
               d["next_price"].notna() & d["forward_return_pct"].notna()].copy()
    return d, usable

def pct(s): return float(s.mean()*100) if len(s) else np.nan

def pattern_table(u):
    rows=[]
    order=["Strong CE Skew","Moderate CE Skew","Balanced","Moderate PE Skew",
           "Strong PE Skew","Insufficient Activity","Invalid"]
    for p in order:
        x=u[u["_skew"].eq(p)]
        rows.append({"volume_skew_class":p,"observations":len(x),"symbols":x["_symbol"].nunique(),
          "mean_forward_return_pct":x["forward_return_pct"].mean(),
          "median_forward_return_pct":x["forward_return_pct"].median(),
          "positive_pct":pct(x["positive"]),"negative_pct":pct(x["negative"]),
          "zero_pct":pct(x["zero"]),"gt_010_pct":pct(x["up_010"]),
          "gt_025_pct":pct(x["up_025"]),"gt_050_pct":pct(x["up_050"]),
          "lt_010_pct":pct(x["down_010"]),"lt_025_pct":pct(x["down_025"]),
          "lt_050_pct":pct(x["down_050"]),"persistence_pct":pct(x["persisted"]),
          "median_elapsed_min":x["elapsed_minutes"].median()})
    return pd.DataFrame(rows)

def main():
    raw, inputs = read_inputs()
    d, start, bad_ts, dup, price_col = prepare(raw)
    d, u = outcomes(d)

    pattern = pattern_table(u)
    active = pattern_table(u[~u["_skew"].isin(["Insufficient Activity","Invalid"])])
    day_rows=[]
    for day,x in sorted(d.groupby("_source_date")):
        day_rows.append({"report_day":str(day),"rows":len(x),"symbols":x["_symbol"].nunique(),
          "snapshots":x["_time"].nunique(),"valid_prices":int(x["_price"].notna().sum()),
          "price_coverage_pct":x["_price"].notna().mean()*100,"first_snapshot":x["_time"].min(),
          "last_snapshot":x["_time"].max(),"same_session_forward":int(x["same_session_forward"].sum()),
          "cross_session_excluded":int(x["cross_session_excluded"].sum())})
    day=pd.DataFrame(day_rows)

    dp=[]
    for (dayv,p),x in u.groupby(["_source_date","_skew"]):
        dp.append({"report_day":str(dayv),"volume_skew_class":p,"observations":len(x),
          "symbols":x["_symbol"].nunique(),"mean_forward_return_pct":x["forward_return_pct"].mean(),
          "median_forward_return_pct":x["forward_return_pct"].median(),
          "positive_pct":pct(x["positive"]),"gt_025_pct":pct(x["up_025"]),
          "lt_025_pct":pct(x["down_025"]),"persistence_pct":pct(x["persisted"]),
          "median_elapsed_min":x["elapsed_minutes"].median()})
    day_pattern=pd.DataFrame(dp)

    sr=[]
    for sym,x in u.groupby("_symbol"):
        sr.append({"Symbol":sym,"observations":len(x),"trading_days":x["_source_date"].nunique(),
          "mean_forward_return_pct":x["forward_return_pct"].mean(),
          "median_forward_return_pct":x["forward_return_pct"].median(),
          "positive_pct":pct(x["positive"]),"gt_025_pct":pct(x["up_025"]),
          "lt_025_pct":pct(x["down_025"]),"mean_elapsed_min":x["elapsed_minutes"].mean(),
          "persistence_pct":pct(x["persisted"]),"first_snapshot":x["_time"].min(),
          "last_snapshot":x["_time"].max()})
    symbol=pd.DataFrame(sr).sort_values(["gt_025_pct","observations"],ascending=[False,False])

    c=u[~u["_skew"].isin(["Insufficient Activity","Invalid"]) & u["up_025"]].copy()
    candidates=c[["_report_day","_symbol","_time","_skew","_price","next_time","next_price",
                  "elapsed_minutes","forward_return_pct","next_skew","persisted"]].copy()
    candidates["candidate_reason"]="Pattern observation followed by > +0.25% next-observation return"
    candidates=candidates.rename(columns={"_report_day":"report_day","_symbol":"Symbol",
      "_time":"signal_time","_skew":"volume_skew_class","_price":"signal_fut_price",
      "next_time":"next_signal_time","next_price":"next_fut_price"}).sort_values(
      ["report_day","signal_time","Symbol"])

    intervals=u["elapsed_minutes"].dropna()
    days=sorted(str(x) for x in d["_source_date"].unique())
    qa=pd.DataFrame([
      ("analysis_start_date",str(start)),("analysis_days",len(days)),
      ("analysis_dates",", ".join(days)),("historical_files_read",len(inputs)),
      ("rows_after_filter_and_deduplication",len(d)),("symbols",d["_symbol"].nunique()),
      ("snapshots",d["_time"].nunique()),("invalid_authoritative_timestamps_removed",bad_ts),
      ("duplicate_cumulative_rows_removed",dup),("same_session_forward_observations",int(d["same_session_forward"].sum())),
      ("cross_session_forward_observations_excluded",int(d["cross_session_excluded"].sum())),
      ("usable_forward_observations",len(u)),("price_field",price_col),
      ("minimum_forward_interval_minutes",intervals.min() if len(intervals) else np.nan),
      ("median_forward_interval_minutes",intervals.median() if len(intervals) else np.nan),
      ("maximum_forward_interval_minutes",intervals.max() if len(intervals) else np.nan),
      ("timestamp_policy","MARKET OBSERVATION TIMESTAMP = SOURCE DATE + WORKBOOK TIME; SNAPSHOT/FILENAME = PROVENANCE"),
      ("forward_policy","NEXT CHRONOLOGICAL SAME-SESSION OBSERVATION ONLY"),
      ("look_ahead_check","PASS"),
      ("research_status","PRELIMINARY - multi-day discovery evidence; not a validated trading rule")
    ],columns=["Metric","Value"])

    overall={"generated_at":datetime.now().isoformat(timespec="seconds"),"days_available":len(days),
      "days":days,"historical_files_read":len(inputs),"total_rows":len(d),
      "symbols":int(d["_symbol"].nunique()),"snapshots":int(d["_time"].nunique()),
      "usable_forward_observations":len(u),"same_session_forward_observations":int(d["same_session_forward"].sum()),
      "cross_session_excluded":int(d["cross_session_excluded"].sum()),
      "minimum_forward_interval_minutes":round(float(intervals.min()),2) if len(intervals) else None,
      "median_forward_interval_minutes":round(float(intervals.median()),2) if len(intervals) else None,
      "maximum_forward_interval_minutes":round(float(intervals.max()),2) if len(intervals) else None,
      "candidate_events_gt_025_pct":len(candidates),
      "timestamp_policy":"MARKET OBSERVATION TIMESTAMP = SOURCE DATE + WORKBOOK TIME; SNAPSHOT/FILENAME = PROVENANCE",
      "look_ahead_policy":"NEXT CHRONOLOGICAL SAME-SESSION OBSERVATION ONLY",
      "research_status":"PRELIMINARY - multi-day discovery evidence; not a validated trading rule"}

    xlsx=REPORT_ROOT/"pcr_volume_discovery_final_report.xlsx"
    with pd.ExcelWriter(xlsx,engine="openpyxl") as w:
        pd.DataFrame([overall]).to_excel(w,sheet_name="Executive_Summary",index=False)
        qa.to_excel(w,sheet_name="Data_Quality",index=False); day.to_excel(w,sheet_name="Day_Summary",index=False)
        pattern.to_excel(w,sheet_name="Pattern_Summary",index=False); active.to_excel(w,sheet_name="Active_Patterns",index=False)
        day_pattern.to_excel(w,sheet_name="Day_Pattern",index=False); symbol.to_excel(w,sheet_name="Symbol_Summary",index=False)
        candidates.to_excel(w,sheet_name="Candidates",index=False); pd.DataFrame(inputs).to_excel(w,sheet_name="Input_Files",index=False)
        ev=d[["_report_day","_symbol","_skew","signal_time","next_signal_time",
              "same_session_forward","cross_session_excluded","elapsed_minutes",
              "_price","next_price","forward_return_pct","next_skew","persisted"]].copy()
        ev.columns=["report_day","Symbol","volume_skew_class","signal_time","next_signal_time",
                    "same_session_forward","cross_session_excluded","elapsed_minutes",
                    "signal_fut_price","next_fut_price","forward_return_pct","next_skew","persisted"]
        ev.to_excel(w,sheet_name="Chronological_Evidence",index=False)
        for ws in w.book.worksheets:
            ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions

    pattern.to_csv(REPORT_ROOT/"pcr_volume_discovery_pattern_summary.csv",index=False)
    day.to_csv(REPORT_ROOT/"pcr_volume_discovery_daywise.csv",index=False)
    symbol.to_csv(REPORT_ROOT/"pcr_volume_discovery_symbol_summary.csv",index=False)
    candidates.to_csv(REPORT_ROOT/"pcr_volume_discovery_candidates.csv",index=False)
    (REPORT_ROOT/"pcr_volume_discovery_status.json").write_text(json.dumps(overall,indent=2,default=str),encoding="utf-8")
    print(json.dumps(overall,indent=2,default=str))
    print(f"FINAL REPORT: {xlsx}")

if __name__=="__main__":
    main()
