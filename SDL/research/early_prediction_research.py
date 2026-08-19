from __future__ import annotations

"""
SDL Early Prediction Research v3
Research only. Production SDL is NOT modified.

Objective:
    Evaluate the first >22% straddle movement as an EARLY intraday
    prediction point against practical continuation targets:
        40%, 45%, 50%.

100% remains a secondary outcome only.

Point-in-time rule:
    Every feature used for prediction must come from the exact first
    >22% observation. Later snapshots are used only to establish outcomes.
"""

from pathlib import Path
import re
import sys
from datetime import datetime
import numpy as np
import pandas as pd

try:
    from config import INTRADAY_SOURCE_ROOT, OUTPUT_ROOT
except Exception:
    INTRADAY_SOURCE_ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot")
    OUTPUT_ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\data\output")

ROOT = Path(OUTPUT_ROOT) / "early_prediction_research"
TARGETS = (40.0, 45.0, 50.0, 100.0)

ALIASES = {
    "price_chg_pct": ["Price Chg %"],
    "oi_chg_pct": ["OI Chg %"],
    "iv_chg_pct": ["IV Chg %"],
    "pcr_chg_pct": ["PCR Chg %"],
    "ce_oi_chg_pct": ["Tot CE OI Chg %"],
    "pe_oi_chg_pct": ["Tot PE OI Chg %"],
    "pe_minus_ce_oi_chg": ["Tot PE-CE OI Chg"],
    "futures_oi_chg_pct": ["Fut OI Chg %","Fut OI Chg%","Futures OI Chg %","Futures OI Chg%"],
    "futures_oi_chg": ["Fut OI Chg","Futures OI Chg","Future OI Chg"],
    "futures_oi": ["Fut OI","Futures OI","Future OI"],
    "futures_buildup": ["Fut Buildup","Futures Buildup","Future Buildup"],
    "volume": ["Volume","Vol"],
    "volume_chg_pct": ["Volume Chg %","Volume Chg (%)"],
    "ivr": ["IVR"], "ivp": ["IVP"],
    "iv_hv10": ["IV/HV10 %"], "iv_hv20": ["IV/HV20 %"], "iv_hv30": ["IV/HV30 %"],
    "atm_straddle_pct": ["ATM Straddle %"],
    "atm_straddle_price": ["ATM Straddle Price"],
    "support_resistance": ["Support/Resistance","S/R","Level Type"],
}

def norm(x):
    return re.sub(r"[^a-z0-9]+", "", str(x).lower())

def resolve(columns, aliases):
    lookup = {norm(c): c for c in columns}
    for a in aliases:
        if norm(a) in lookup:
            return lookup[norm(a)]
    return None

def parse_ts(p):
    m = re.search(r"_(\d{6})\.xlsx$", p.name, re.I)
    if m:
        return datetime.strptime(m.group(1), "%H%M%S")
    return datetime.fromtimestamp(p.stat().st_mtime)

def files_for_day(day):
    root = Path(INTRADAY_SOURCE_ROOT)
    compact = day.replace("-", "")
    found = []
    for p in root.rglob("*.xlsx"):
        if day in str(p) or compact in p.name.replace("-", ""):
            found.append(p)
    return sorted(set(found), key=lambda p: (parse_ts(p), p.name))

def read_snapshot(p, day, seq):
    raw = pd.read_excel(p)
    if "Symbol" not in raw.columns:
        return pd.DataFrame()
    df = raw.copy()
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    df = df[df["Symbol"].ne("") & df["Symbol"].ne("NAN")].copy()
    ts = parse_ts(p)
    ts = pd.Timestamp(datetime.strptime(day, "%Y-%m-%d").replace(
        hour=ts.hour, minute=ts.minute, second=ts.second
    ))
    df["_ts"] = ts
    df["_seq"] = seq
    df["_source_file"] = str(p)
    for key, aliases in ALIASES.items():
        col = resolve(df.columns, aliases)
        df[key] = pd.to_numeric(df[col], errors="coerce") if col else np.nan
    for c in ("Open","High","Low","Close"):
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
    df["current_price"] = df["Close"]
    return df

def build_day(day):
    fs = files_for_day(day)
    snaps = [read_snapshot(p, day, i) for i,p in enumerate(fs)]
    snaps = [x for x in snaps if not x.empty]
    if not snaps:
        raise RuntimeError(f"No readable snapshots for {day}")

    all_df = pd.concat(snaps, ignore_index=True).sort_values(
        ["Symbol","_ts","_seq"]
    )

    # Opening reference is frozen from first chronological observation.
    opening = (
        all_df.sort_values(["Symbol","_ts","_seq"])
        .groupby("Symbol", as_index=False)
        .first()[["Symbol","Open","atm_straddle_pct"]]
        .rename(columns={"Open":"opening_price"})
    )
    opening["opening_straddle_premium"] = (
        opening["opening_price"] * opening["atm_straddle_pct"] / 100.0
    )
    all_df = all_df.merge(opening, on="Symbol", how="left")

    all_df["progress_pct"] = (
        (all_df["current_price"] - all_df["opening_price"]).abs()
        / all_df["opening_straddle_premium"] * 100.0
    )
    all_df["direction"] = np.select(
        [all_df["current_price"] > all_df["opening_price"],
         all_df["current_price"] < all_df["opening_price"]],
        ["UP","DOWN"], default=""
    )

    # First >22% event.
    candidates = all_df[all_df["progress_pct"].gt(22)].copy()
    candidates = candidates.sort_values(["Symbol","_ts","_seq"])
    first22 = candidates.drop_duplicates("Symbol", keep="first").copy()

    rows = []
    for _, ev in first22.iterrows():
        later = all_df[
            (all_df["Symbol"] == ev["Symbol"]) &
            (all_df["_ts"] > ev["_ts"])
        ].sort_values(["_ts","_seq"]).copy()

        result = {
            "trading_date": day,
            "Symbol": ev["Symbol"],
            "first_22_timestamp": ev["_ts"],
            "first_22_progress_pct": ev["progress_pct"],
            "direction": ev["direction"],
            "first_22_source_file": ev["_source_file"],
        }

        for target in TARGETS:
            hits = later[later["progress_pct"] >= target]
            result[f"target_{int(target)}_reached"] = not hits.empty
            result[f"time_to_{int(target)}_min"] = (
                (hits.iloc[0]["_ts"] - ev["_ts"]).total_seconds()/60
                if not hits.empty else np.nan
            )

        # Maximum subsequent progress is an outcome, never a feature.
        result["max_progress_after_22"] = (
            float(later["progress_pct"].max()) if not later.empty else np.nan
        )

        # Primary practical target status.
        result["target_40_50_status"] = (
            "REACHED_50" if result["target_50_reached"] else
            "REACHED_45_ONLY" if result["target_45_reached"] else
            "REACHED_40_ONLY" if result["target_40_reached"] else
            "FAILED_40"
        )

        # Point-in-time evidence only.
        for c in [
            "price_chg_pct","oi_chg_pct","iv_chg_pct","pcr_chg_pct",
            "ce_oi_chg_pct","pe_oi_chg_pct","pe_minus_ce_oi_chg",
            "futures_oi_chg_pct","futures_oi_chg","futures_oi",
            "futures_buildup","volume","volume_chg_pct","ivr","ivp",
            "iv_hv10","iv_hv20","iv_hv30"
        ]:
            result[c] = ev.get(c, np.nan)

        rows.append(result)

    return pd.DataFrame(rows)

def descriptive(df):
    rows = []
    df = df.copy()
    df["progress_band"] = pd.cut(
        df["first_22_progress_pct"],
        bins=[22,30,40,50,60,75,np.inf],
        labels=["22-30","30-40","40-50","50-60","60-75",">75"],
        right=True,
    )
    for feature in ["direction","progress_band","target_40_50_status"]:
        for bucket, g in df.groupby(feature, observed=False):
            if len(g) == 0: continue
            rows.append({
                "feature":feature,
                "bucket":str(bucket),
                "n":len(g),
                "reached_40":int(g["target_40_reached"].sum()),
                "rate_40":float(g["target_40_reached"].mean()),
                "reached_45":int(g["target_45_reached"].sum()),
                "rate_45":float(g["target_45_reached"].mean()),
                "reached_50":int(g["target_50_reached"].sum()),
                "rate_50":float(g["target_50_reached"].mean()),
            })
    return pd.DataFrame(rows)

def factor_effects(df):
    # This deliberately reports distributions, not a score.
    factor_cols = [
        "price_chg_pct","oi_chg_pct","iv_chg_pct","pcr_chg_pct",
        "ce_oi_chg_pct","pe_oi_chg_pct","pe_minus_ce_oi_chg",
        "futures_oi_chg_pct","futures_oi_chg","futures_oi",
        "futures_buildup","volume","volume_chg_pct","ivr","ivp",
        "iv_hv10","iv_hv20","iv_hv30"
    ]
    rows=[]
    for c in factor_cols:
        if c not in df: continue
        x = pd.to_numeric(df[c], errors="coerce")
        valid = df.loc[x.notna()].copy()
        if valid.empty: continue
        x = pd.to_numeric(valid[c], errors="coerce")
        for target in (40,45,50):
            win = valid[valid[f"target_{target}_reached"]]
            fail = valid[~valid[f"target_{target}_reached"]]
            rows.append({
                "feature":c,"target":target,
                "n_valid":len(valid),
                "success_n":len(win),"failure_n":len(fail),
                "success_mean":float(pd.to_numeric(win[c],errors="coerce").mean()) if len(win) else np.nan,
                "failure_mean":float(pd.to_numeric(fail[c],errors="coerce").mean()) if len(fail) else np.nan,
                "success_median":float(pd.to_numeric(win[c],errors="coerce").median()) if len(win) else np.nan,
                "failure_median":float(pd.to_numeric(fail[c],errors="coerce").median()) if len(fail) else np.nan,
            })
    return pd.DataFrame(rows)

def run(*days):
    if not days:
        raise SystemExit("Usage: python research\\early_prediction_research.py YYYY-MM-DD [YYYY-MM-DD ...]")
    ROOT.mkdir(parents=True, exist_ok=True)
    frames=[build_day(d) for d in days]
    df=pd.concat(frames, ignore_index=True)
    df.to_csv(ROOT/"first_22_point_in_time.csv", index=False)

    summary=pd.DataFrame([{
        "research_events":len(df),
        "reached_40":int(df.target_40_reached.sum()),
        "rate_40":float(df.target_40_reached.mean()),
        "reached_45":int(df.target_45_reached.sum()),
        "rate_45":float(df.target_45_reached.mean()),
        "reached_50":int(df.target_50_reached.sum()),
        "rate_50":float(df.target_50_reached.mean()),
        "reached_100_secondary":int(df.target_100_reached.sum()),
    }])
    summary.to_csv(ROOT/"research_summary.csv", index=False)
    descriptive(df).to_csv(ROOT/"descriptive_target_effects.csv", index=False)
    factor_effects(df).to_csv(ROOT/"factor_target_effects.csv", index=False)

    print("SDL EARLY PREDICTION RESEARCH v3")
    print("SOURCE ROOT:",INTRADAY_SOURCE_ROOT)
    print("OUTPUTS:",ROOT)
    print("PRIMARY TARGETS: 40%, 45%, 50%")
    print("SECONDARY OUTCOME: 100%")
    print("PRODUCTION MODIFIED: NO")
    print(summary.to_string(index=False))

if __name__=="__main__":
    run(*sys.argv[1:])
