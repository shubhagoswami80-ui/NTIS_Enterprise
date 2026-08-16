
from __future__ import annotations

from pathlib import Path
import re
import sys
import numpy as np
import pandas as pd

# Keep these imports independent.  The previous bundle incorrectly grouped
# config + approaching_breakout imports, which could leave the loader undefined.
try:
    from config import (
        INTRADAY_SOURCE_ROOT,
        REQUIRED_EVIDENCE_DIR,
        OUTPUT_ROOT,
        TRADABLE_EVENTS_DIR,
    )
except Exception:
    INTRADAY_SOURCE_ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot")
    REQUIRED_EVIDENCE_DIR = Path(r"E:\NSE_Daily_Analysis\SDL\data\output\required_evidence")
    OUTPUT_ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\data\output")
    TRADABLE_EVENTS_DIR = OUTPUT_ROOT / "tradable_events"

try:
    from approaching_breakout import load_approaching_breakouts
except Exception as exc:
    raise RuntimeError(
        "Unable to import current SDL approaching_breakout.load_approaching_breakouts. "
        "Run from E:\\NSE_Daily_Analysis\\SDL. Original error: " + str(exc)
    ) from exc

RESEARCH_ROOT = Path(OUTPUT_ROOT) / "continuation_research"
APPROACHING_CSV = Path(TRADABLE_EVENTS_DIR) / "approaching_breakouts.csv"

PRIMARY_OUTCOME = "continued_to_100_after_50"
SAME_OBS_OUTCOME = "same_observation_100"
UNRESOLVED_OUTCOME = "unresolved_no_later_100"
MISSING_OUTCOME = "missing_replay_evidence"

ALIASES = {
    "futures_oi": ["Fut OI", "Futures OI", "Future OI", "Fut. OI"],
    "futures_oi_chg": ["Fut OI Chg", "Futures OI Chg", "Future OI Chg", "Fut. OI Chg"],
    "futures_oi_chg_pct": ["Fut OI Chg %", "Fut OI Chg%", "Futures OI Chg %", "Futures OI Chg%", "Future OI Chg %", "Future OI Chg%"],
    "futures_buildup": ["Fut Buildup", "Futures Buildup", "Future Buildup"],
    "atm_straddle_pct": ["ATM Straddle %"],
    "atm_straddle_price": ["ATM Straddle Price"],
    "price_chg_pct": ["Price Chg %"],
    "iv_chg_pct": ["IV Chg %"],
    "oi_chg_pct": ["OI Chg %"],
    "pcr_chg_pct": ["PCR Chg %"],
    "ce_oi_chg_pct": ["Tot CE OI Chg %"],
    "pe_oi_chg_pct": ["Tot PE OI Chg %"],
    "pe_minus_ce": ["Tot PE-CE OI Chg"],
    "ivr": ["IVR"],
    "ivp": ["IVP"],
    "iv_hv10": ["IV/HV10 %"],
    "iv_hv20": ["IV/HV20 %"],
    "iv_hv30": ["IV/HV30 %"],
    "volume": ["Volume", "Vol"],
    "volume_chg_pct": ["Volume Chg %", "Volume Chg (%)"],
    "strike": ["Strike", "From Strike"],
    "distance_from_strike_pct": ["Dist. From Strike %", "Distance From Strike %"],
    "support_resistance": ["Support/Resistance", "S/R", "Level Type"],
}

def norm(x):
    return re.sub(r"[^a-z0-9]+", "", str(x).lower())

def resolve(columns, aliases):
    lookup = {norm(c): c for c in columns}
    for a in aliases:
        if norm(a) in lookup:
            return lookup[norm(a)]
    return None

def discover_day_files(trading_date):
    root = Path(INTRADAY_SOURCE_ROOT)
    if not root.exists():
        return []
    return sorted(
        {p for p in root.rglob("*.xlsx")
         if trading_date in str(p) or trading_date.replace("-", "") in p.name.replace("-", "")},
        key=lambda p: p.stat().st_mtime,
    )

def schema_map(trading_date):
    rows = []
    for p in discover_day_files(trading_date):
        try:
            df = pd.read_excel(p, nrows=2)
        except Exception as exc:
            rows.append({"file": str(p), "status": f"ERROR: {exc}"})
            continue
        for feature, aliases in ALIASES.items():
            physical = resolve(df.columns, aliases)
            rows.append({"file": str(p), "feature": feature, "physical_column": physical, "available": bool(physical)})
    return pd.DataFrame(rows)

def load_approaching():
    if not APPROACHING_CSV.exists():
        raise FileNotFoundError(f"Missing authoritative approaching file: {APPROACHING_CSV}")
    # Current Git master signature requires the explicit CSV path.
    return load_approaching_breakouts(APPROACHING_CSV)

def first_50_events(trading_date=None):
    df = load_approaching()
    if df.empty:
        return df
    required = {"trading_date", "symbol", "observation_timestamp"}
    if not required.issubset(df.columns):
        raise ValueError(f"approaching_breakouts missing {required - set(df.columns)}")
    df = df.copy()
    df["trading_date"] = pd.to_datetime(df["trading_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["observation_timestamp"] = pd.to_datetime(df["observation_timestamp"], errors="coerce")
    if trading_date:
        df = df[df["trading_date"] == trading_date].copy()
    df = df.dropna(subset=["observation_timestamp"]).sort_values(["trading_date", "symbol", "observation_timestamp"])
    return df.drop_duplicates(["trading_date", "symbol"], keep="first").reset_index(drop=True)

def load_evidence(trading_date):
    path = Path(REQUIRED_EVIDENCE_DIR) / f"{trading_date}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "observation_timestamp" in df.columns:
        df["observation_timestamp"] = pd.to_datetime(df["observation_timestamp"], errors="coerce")
    if "Symbol" in df.columns:
        df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    return df

def replay(events):
    rows = []
    for event in events.itertuples(index=False):
        evidence = load_evidence(event.trading_date)
        if evidence.empty or "Symbol" not in evidence.columns:
            rows.append({**event._asdict(), "outcome": MISSING_OUTCOME, "first_later_100_timestamp": pd.NaT, "minutes_50_to_100": np.nan})
            continue

        g = evidence[
            (evidence["Symbol"] == str(event.symbol).upper())
            & evidence["observation_timestamp"].notna()
            & (evidence["observation_timestamp"] >= event.observation_timestamp)
        ].sort_values("observation_timestamp").copy()

        if g.empty:
            rows.append({**event._asdict(), "outcome": MISSING_OUTCOME, "first_later_100_timestamp": pd.NaT, "minutes_50_to_100": np.nan})
            continue

        direction = str(getattr(event, "direction", "")).upper()
        if direction == "UP" and "upside_breakout" in g.columns:
            hit = g["upside_breakout"].fillna(False).astype(bool)
        elif direction == "DOWN" and "downside_breakout" in g.columns:
            hit = g["downside_breakout"].fillna(False).astype(bool)
        elif "standard_straddle_breakout" in g.columns:
            hit = g["standard_straddle_breakout"].fillna(False).astype(bool)
        else:
            hit = pd.Series(False, index=g.index)

        same = g["observation_timestamp"].eq(event.observation_timestamp)
        later = hit & ~same
        same_hit = hit & same

        if later.any():
            ts = g.loc[later, "observation_timestamp"].iloc[0]
            outcome = PRIMARY_OUTCOME
            minutes = (ts - event.observation_timestamp).total_seconds() / 60
        elif same_hit.any():
            ts = g.loc[same_hit, "observation_timestamp"].iloc[0]
            outcome = SAME_OBS_OUTCOME
            minutes = 0.0
        else:
            ts = pd.NaT
            outcome = UNRESOLVED_OUTCOME
            minutes = np.nan

        rows.append({**event._asdict(), "outcome": outcome, "first_later_100_timestamp": ts, "minutes_50_to_100": minutes})
    return pd.DataFrame(rows)

def point_in_time_features(events):
    out = events.copy()
    if out.empty:
        return out
    p = pd.to_numeric(out.get("approach_progress_pct"), errors="coerce")
    out["distance_to_100_pct"] = 100 - p
    out["progress_band"] = pd.cut(p, bins=[-np.inf, 60, 75, 90, 100, np.inf], labels=["50-60", "60-75", "75-90", "90-100", ">=100"])
    ts = pd.to_datetime(out["observation_timestamp"], errors="coerce")
    out["minutes_from_0915"] = ts.dt.hour * 60 + ts.dt.minute - 555
    return out

def descriptive_effects(df):
    if df.empty:
        return pd.DataFrame()
    clean = df[df["outcome"].isin([PRIMARY_OUTCOME, UNRESOLVED_OUTCOME])].copy()
    if clean.empty:
        return pd.DataFrame()
    clean["continued"] = (clean["outcome"] == PRIMARY_OUTCOME).astype(int)
    rows = []
    for band, g in clean.groupby("progress_band", observed=False):
        if len(g):
            rows.append({"feature": "progress_band", "bucket": str(band), "n": len(g), "continued": int(g["continued"].sum()), "continuation_rate": float(g["continued"].mean())})
    for direction, g in clean.groupby("direction"):
        if len(g):
            rows.append({"feature": "direction", "bucket": str(direction), "n": len(g), "continued": int(g["continued"].sum()), "continuation_rate": float(g["continued"].mean())})
    return pd.DataFrame(rows)

def run(*dates):
    RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)
    dates = list(dates)
    events = pd.concat([first_50_events(d) for d in dates], ignore_index=True) if dates else first_50_events()
    events = point_in_time_features(events)
    replayed = replay(events)
    replayed.to_csv(RESEARCH_ROOT / "continuation_replay_events.csv", index=False)
    descriptive_effects(replayed).to_csv(RESEARCH_ROOT / "descriptive_feature_effects.csv", index=False)
    schema = pd.concat([schema_map(d) for d in dates], ignore_index=True) if dates else pd.DataFrame()
    schema.to_csv(RESEARCH_ROOT / "source_schema_map.csv", index=False)
    pd.DataFrame([{
        "research_events": len(replayed),
        "clean_continuations": int((replayed["outcome"] == PRIMARY_OUTCOME).sum()) if not replayed.empty else 0,
        "same_observation_100_excluded": int((replayed["outcome"] == SAME_OBS_OUTCOME).sum()) if not replayed.empty else 0,
        "unresolved": int((replayed["outcome"] == UNRESOLVED_OUTCOME).sum()) if not replayed.empty else 0,
        "missing_replay_evidence": int((replayed["outcome"] == MISSING_OUTCOME).sum()) if not replayed.empty else 0,
    }]).to_csv(RESEARCH_ROOT / "research_summary.csv", index=False)
    print("AUTH BASELINE: bda7958e4616a611c196df615c95b83e6dc6ea4a")
    print("Research events:", len(replayed))
    print("Outputs:", RESEARCH_ROOT)
    print("PRODUCTION MODIFIED: NO")

if __name__ == "__main__":
    run(*sys.argv[1:])
