#!/usr/bin/env python
"""
PCR Volume Pattern Discovery
----------------------------
Reads every PECE_*.xlsx workbook recursively, preserves all available fields,
and creates interval-wise, symbol-wise pattern-discovery outputs.

Important:
- Workbooks are cumulative snapshots. Each workbook is treated as one source
  snapshot, and the latest Time row per Symbol is selected for that snapshot.
- All original source fields are retained in the detailed interval output.
- No price-based directional conclusion is generated.
"""

from __future__ import annotations
import json, logging, math, re
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / "CONFIG.json").read_text(encoding="utf-8"))

SOURCE_ROOT = Path(CONFIG["source_root"])
OUTPUT_ROOT = Path(CONFIG["output_root"])
SHEET = CONFIG.get("sheet_name", "Data")
REQUIRED = ["Symbol", "Time", "CE Volume", "PE Volume", "Tot CEVol (Day)",
            "Tot PEVol (Day)", "PCR-Volume", "Snapshot"]

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
(OUTPUT_ROOT / "Current").mkdir(exist_ok=True)
(OUTPUT_ROOT / "History").mkdir(exist_ok=True)
(OUTPUT_ROOT / "Logs").mkdir(exist_ok=True)

logging.basicConfig(
    filename=OUTPUT_ROOT / "Logs" / "pattern_discovery.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

def num(series):
    return pd.to_numeric(series, errors="coerce")

def parse_file_snapshot(path: Path):
    m = re.search(r"PECE_(\d{8})_(\d{6})", path.name, re.I)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")

def time_key(value):
    try:
        return datetime.strptime(str(value).strip(), "%H:%M").time()
    except Exception:
        return None

def classify(pcr_pct, combined):
    if pd.isna(pcr_pct) or pd.isna(combined):
        return "Invalid"
    if combined <= CONFIG.get("min_combined_volume", 0):
        return "Insufficient Activity"
    lo = CONFIG["balanced_pcr_low_pct"]
    hi = CONFIG["balanced_pcr_high_pct"]
    strong_lo = CONFIG["strong_skew_pcr_low_pct"]
    strong_hi = CONFIG["strong_skew_pcr_high_pct"]
    if pcr_pct < strong_lo:
        return "Strong CE Skew"
    if pcr_pct < lo:
        return "Moderate CE Skew"
    if pcr_pct <= hi:
        return "Balanced"
    if pcr_pct <= strong_hi:
        return "Moderate PE Skew"
    return "Strong PE Skew"

def read_workbook(path):
    source_dt = parse_file_snapshot(path)
    if source_dt is None:
        return None
    try:
        df = pd.read_excel(path, sheet_name=SHEET)
    except Exception as exc:
        logging.exception("Read failed: %s - %s", path, exc)
        return None
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        logging.warning("Skipped %s; missing fields: %s", path, missing)
        return None
    df["_source_file"] = path.name
    df["_source_path"] = str(path)
    df["_source_snapshot_dt"] = source_dt
    # One representative row per symbol for this cumulative workbook:
    df["_time_key"] = df["Time"].map(time_key)
    df = df.sort_values(["Symbol", "_time_key"], na_position="first")
    df = df.drop_duplicates("Symbol", keep="last").copy()
    return df

def enrich(df):
    for c in ["CE Volume", "PE Volume", "Tot CEVol (Day)", "Tot PEVol (Day)",
              "PCR-Volume", "Fut Volume", "Tot Fut OI", "Tot Fut OIChg (Day)",
              "PCR-OI", "PCR-OI Chg"]:
        if c in df:
            df[c] = num(df[c])

    # Explicit PCR calculation from daily PE/CE volumes.
    ce = num(df["Tot CEVol (Day)"])
    pe = num(df["Tot PEVol (Day)"])
    df["calc_pcr_volume_ratio"] = np.where(ce > 0, pe / ce, np.nan)
    df["calc_pcr_volume_pct"] = df["calc_pcr_volume_ratio"] * 100.0

    # Intraday CE/PE volume fields are retained and used where available.
    ce_i = num(df["CE Volume"])
    pe_i = num(df["PE Volume"])
    df["combined_option_volume"] = ce_i.fillna(0) + pe_i.fillna(0)
    df["ce_pe_volume_difference"] = pe_i - ce_i
    total = ce_i + pe_i
    df["ce_volume_share_pct"] = np.where(total > 0, ce_i / total * 100, np.nan)
    df["pe_volume_share_pct"] = np.where(total > 0, pe_i / total * 100, np.nan)

    df["pcr_source_difference"] = df["calc_pcr_volume_ratio"] - num(df["PCR-Volume"])
    df["pcr_source_validation"] = np.where(
        df["pcr_source_difference"].abs() <= 0.03, "Within tolerance", "Review"
    )
    df["volume_skew_class"] = [
        classify(x, y) for x, y in zip(df["calc_pcr_volume_pct"], df["combined_option_volume"])
    ]
    df["source_snapshot"] = df["_source_snapshot_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df

def add_history_features(all_df):
    all_df = all_df.sort_values(["Symbol", "_source_snapshot_dt", "_time_key"]).copy()
    g = all_df.groupby("Symbol", group_keys=False)
    all_df["previous_pcr_volume_pct"] = g["calc_pcr_volume_pct"].shift(1)
    all_df["pcr_change_from_previous"] = (
        all_df["calc_pcr_volume_pct"] - all_df["previous_pcr_volume_pct"]
    )
    all_df["first_pcr_volume_pct"] = g["calc_pcr_volume_pct"].transform("first")
    all_df["pcr_change_from_first"] = (
        all_df["calc_pcr_volume_pct"] - all_df["first_pcr_volume_pct"]
    )
    all_df["observations_for_symbol"] = g["Symbol"].transform("size")
    all_df["skew_persistence_count"] = (
        all_df.groupby(["Symbol", "volume_skew_class"]).cumcount() + 1
    )
    all_df["interval_number"] = all_df.groupby("_source_snapshot_dt").ngroup() + 1
    return all_df

def main():
    files = sorted(
        p for p in SOURCE_ROOT.rglob(CONFIG.get("file_glob", "PECE_*.xlsx"))
        if not p.name.startswith("~$")
    )
    if not files:
        raise FileNotFoundError(f"No PECE workbooks found under {SOURCE_ROOT}")

    frames = []
    for p in files:
        part = read_workbook(p)
        if part is not None:
            frames.append(part)
    if not frames:
        raise RuntimeError("No valid PECE workbooks could be processed")

    data = enrich(pd.concat(frames, ignore_index=True))
    data = add_history_features(data)

    latest_dt = data["_source_snapshot_dt"].max()
    latest = data[data["_source_snapshot_dt"] == latest_dt].copy()

    # Activity percentile is calculated within the latest snapshot.
    latest["activity_percentile"] = latest["combined_option_volume"].rank(pct=True) * 100
    latest["activity_band"] = pd.cut(
        latest["activity_percentile"],
        bins=[-np.inf, 50, 75, 90, np.inf],
        labels=["Low", "Normal", "High", "Very High"]
    ).astype(str)
    latest["is_relevant"] = latest["volume_skew_class"].ne("Invalid")
    latest["latest_rank_by_skew_extreme"] = (
        latest["calc_pcr_volume_pct"].sub(100).abs().rank(ascending=False, method="dense")
    )

    # Remove internal helper columns only from the compact latest report.
    internal = ["_time_key", "_source_snapshot_dt"]
    compact = latest.drop(columns=[c for c in internal if c in latest], errors="ignore")

    current = OUTPUT_ROOT / "Current"
    history_dir = OUTPUT_ROOT / "History" / latest_dt.strftime("%Y-%m-%d")
    history_dir.mkdir(parents=True, exist_ok=True)

    data.to_csv(history_dir / "pcr_volume_pattern_all_intervals.csv", index=False)
    compact.to_csv(current / "pcr_volume_skew_latest.csv", index=False)

    summary = {
        "status": "SUCCESS",
        "processed_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(SOURCE_ROOT),
        "workbook_count": len(files),
        "valid_workbook_count": len(frames),
        "interval_count": int(data["_source_snapshot_dt"].nunique()),
        "symbol_count_latest": int(latest["Symbol"].nunique()),
        "latest_source_snapshot": latest_dt.isoformat(),
        "rows_all_intervals": int(len(data)),
        "rows_latest": int(len(latest)),
        "fields_read": list(data.columns),
        "skew_counts_latest": latest["volume_skew_class"].value_counts(dropna=False).to_dict()
    }
    (current / "pcr_volume_skew_status.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    # A machine-readable pattern summary by symbol.
    profile = data.groupby("Symbol", dropna=False).agg(
        observations=("Symbol", "size"),
        avg_pcr_volume_pct=("calc_pcr_volume_pct", "mean"),
        median_pcr_volume_pct=("calc_pcr_volume_pct", "median"),
        min_pcr_volume_pct=("calc_pcr_volume_pct", "min"),
        max_pcr_volume_pct=("calc_pcr_volume_pct", "max"),
        avg_combined_option_volume=("combined_option_volume", "mean"),
        max_combined_option_volume=("combined_option_volume", "max"),
        ce_skew_observations=("volume_skew_class", lambda s: s.isin(["Strong CE Skew", "Moderate CE Skew"]).sum()),
        balanced_observations=("volume_skew_class", lambda s: (s == "Balanced").sum()),
        pe_skew_observations=("volume_skew_class", lambda s: s.isin(["Strong PE Skew", "Moderate PE Skew"]).sum()),
    ).reset_index()
    profile["ce_skew_share_pct"] = profile["ce_skew_observations"] / profile["observations"] * 100
    profile["pe_skew_share_pct"] = profile["pe_skew_observations"] / profile["observations"] * 100
    profile.to_csv(current / "pcr_volume_symbol_profiles.csv", index=False)

    logging.info("SUCCESS: %s", summary)
    print(json.dumps(summary, indent=2, default=str))

if __name__ == "__main__":
    main()
