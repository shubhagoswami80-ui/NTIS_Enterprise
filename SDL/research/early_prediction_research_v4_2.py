from __future__ import annotations

"""
SDL Early Prediction Research v4.2
Research only. Production SDL is NOT modified.

Purpose:
Coalesce all same-Symbol/same-timestamp snapshots before selecting the
first >22% event, so Futures OI fields present in a companion
Support/Resistance snapshot are not lost.

Futures fields retained independently:
    futures_oi
    futures_oi_chg
    futures_oi_chg_pct
    futures_buildup

Point-in-time rule:
Features are taken only from the coalesced first >22% timestamp.
Later timestamps are used only for outcomes.
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd

RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from early_prediction_research import (
    files_for_day,
    read_snapshot,
    INTRADAY_SOURCE_ROOT,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output" / "early_prediction_futures_oi_v4_2"


def first_valid(series):
    series = series.dropna()
    return series.iloc[0] if not series.empty else np.nan


def coalesce_day(day):
    frames = []

    for seq, p in enumerate(files_for_day(day)):
        x = read_snapshot(p, day, seq)
        if not x.empty:
            frames.append(x)

    if not frames:
        raise RuntimeError(f"No readable snapshots for {day}")

    raw = pd.concat(frames, ignore_index=True)
    raw = raw.sort_values(["Symbol", "_ts", "_seq"])

    value_cols = [
        "Open", "High", "Low", "Close", "current_price",
        "price_chg_pct", "oi_chg_pct", "iv_chg_pct", "pcr_chg_pct",
        "ce_oi_chg_pct", "pe_oi_chg_pct", "pe_minus_ce_oi_chg",
        "futures_oi", "futures_oi_chg", "futures_oi_chg_pct",
        "futures_buildup", "volume", "volume_chg_pct",
        "ivr", "ivp", "iv_hv10", "iv_hv20", "iv_hv30",
        "atm_straddle_pct", "atm_straddle_price",
    ]

    for col in value_cols:
        if col not in raw.columns:
            raw[col] = np.nan

    grouped = (
        raw.groupby(["Symbol", "_ts"], sort=True, as_index=False)[value_cols]
        .agg(first_valid)
    )

    source_map = (
        raw.groupby(["Symbol", "_ts"], sort=True)["_source_file"]
        .agg(lambda s: " | ".join(dict.fromkeys(map(str, s))))
        .reset_index(name="_source_file")
    )

    out = grouped.merge(source_map, on=["Symbol", "_ts"], how="left")
    out["_seq"] = out.groupby("Symbol", sort=False).cumcount()

    return out.sort_values(
        ["Symbol", "_ts", "_seq"]
    ).reset_index(drop=True)


def build_day(day):
    all_df = coalesce_day(day)

    opening = (
        all_df.sort_values(["Symbol", "_ts", "_seq"])
        .groupby("Symbol", as_index=False)
        .first()[["Symbol", "Open", "atm_straddle_pct"]]
        .rename(columns={"Open": "opening_price"})
    )

    opening["opening_straddle_premium"] = (
        opening["opening_price"] * opening["atm_straddle_pct"] / 100.0
    )

    all_df = all_df.merge(opening, on="Symbol", how="left")

    valid_premium = all_df["opening_straddle_premium"].gt(0)

    all_df["progress_pct"] = np.where(
        valid_premium,
        (
            (all_df["current_price"] - all_df["opening_price"]).abs()
            / all_df["opening_straddle_premium"] * 100.0
        ),
        np.nan,
    )

    all_df["direction"] = np.select(
        [
            all_df["current_price"] > all_df["opening_price"],
            all_df["current_price"] < all_df["opening_price"],
        ],
        ["UP", "DOWN"],
        default="",
    )

    candidates = (
        all_df[all_df["progress_pct"].gt(22)]
        .sort_values(["Symbol", "_ts", "_seq"])
    )

    first22 = candidates.drop_duplicates("Symbol", keep="first")

    rows = []

    for _, ev in first22.iterrows():
        later = all_df[
            (all_df["Symbol"] == ev["Symbol"])
            & (all_df["_ts"] > ev["_ts"])
        ].sort_values(["_ts", "_seq"])

        result = {
            "trading_date": day,
            "Symbol": ev["Symbol"],
            "first_22_timestamp": ev["_ts"],
            "first_22_progress_pct": ev["progress_pct"],
            "direction": ev["direction"],
            "first_22_source_file": ev["_source_file"],
        }

        for target in (40, 45, 50, 100):
            hits = later[later["progress_pct"] >= target]
            result[f"target_{target}_reached"] = not hits.empty
            result[f"time_to_{target}_min"] = (
                (hits.iloc[0]["_ts"] - ev["_ts"]).total_seconds() / 60
                if not hits.empty else np.nan
            )

        result["max_progress_after_22"] = (
            float(later["progress_pct"].max())
            if not later.empty else np.nan
        )

        for col in [
            "price_chg_pct",
            "oi_chg_pct",
            "iv_chg_pct",
            "pcr_chg_pct",
            "ce_oi_chg_pct",
            "pe_oi_chg_pct",
            "pe_minus_ce_oi_chg",
            "futures_oi",
            "futures_oi_chg",
            "futures_oi_chg_pct",
            "futures_buildup",
            "volume",
            "volume_chg_pct",
            "ivr",
            "ivp",
            "iv_hv10",
            "iv_hv20",
            "iv_hv30",
        ]:
            result[col] = ev.get(col, np.nan)

        rows.append(result)

    return pd.DataFrame(rows)


def gate_futures(value):
    if pd.isna(value):
        return "UNAVAILABLE"
    if value > 0:
        return "POSITIVE"
    if value < 0:
        return "NEGATIVE"
    return "NEUTRAL"


def gate_directional(value, direction):
    if pd.isna(value):
        return "UNAVAILABLE"
    if value == 0:
        return "NEUTRAL"
    if direction == "UP":
        return "SUPPORT" if value > 0 else "CONTRADICT"
    if direction == "DOWN":
        return "SUPPORT" if value < 0 else "CONTRADICT"
    return "UNAVAILABLE"


def add_analysis_columns(df):
    out = df.copy()

    out["gate_price"] = [
        gate_directional(v, d)
        for v, d in zip(out["price_chg_pct"], out["direction"])
    ]

    # Futures OI change % is the primary directional Futures-OI gate.
    out["gate_futures_oi"] = [
        gate_futures(v) for v in out["futures_oi_chg_pct"]
    ]

    # Keep raw Futures OI change separately; it is NOT substituted for OI%.
    out["gate_futures_oi_chg"] = [
        gate_futures(v) for v in out["futures_oi_chg"]
    ]

    out["gate_pe_minus_ce"] = [
        gate_directional(v, d)
        for v, d in zip(out["pe_minus_ce_oi_chg"], out["direction"])
    ]

    return out


def population_effects(df):
    masks = {
        "ALL_FIRST_22": pd.Series(True, index=df.index),

        "PRICE_GATE": (
            df["gate_price"].eq("SUPPORT")
        ),

        "PRICE_PLUS_FUTURES_OI": (
            df["gate_price"].eq("SUPPORT")
            & df["gate_futures_oi"].eq("POSITIVE")
        ),

        "PRICE_PLUS_PE_CE": (
            df["gate_price"].eq("SUPPORT")
            & df["gate_pe_minus_ce"].eq("SUPPORT")
        ),

        "PRICE_PLUS_FUTURES_OI_PLUS_PE_CE": (
            df["gate_price"].eq("SUPPORT")
            & df["gate_futures_oi"].eq("POSITIVE")
            & df["gate_pe_minus_ce"].eq("SUPPORT")
        ),
    }

    rows = []

    for name, mask in masks.items():
        g = df.loc[mask]

        rows.append({
            "population": name,
            "n": len(g),
            "futures_oi_valid": int(g["futures_oi"].notna().sum()),
            "futures_oi_chg_valid": int(g["futures_oi_chg"].notna().sum()),
            "futures_oi_chg_pct_valid": int(
                g["futures_oi_chg_pct"].notna().sum()
            ),
            "reached_40": int(g["target_40_reached"].sum()),
            "rate_40": (
                float(g["target_40_reached"].mean())
                if len(g) else np.nan
            ),
            "reached_45": int(g["target_45_reached"].sum()),
            "rate_45": (
                float(g["target_45_reached"].mean())
                if len(g) else np.nan
            ),
            "reached_50": int(g["target_50_reached"].sum()),
            "rate_50": (
                float(g["target_50_reached"].mean())
                if len(g) else np.nan
            ),
            "reached_100_secondary": int(
                g["target_100_reached"].sum()
            ),
        })

    return pd.DataFrame(rows)


def main(days):
    if not days:
        raise SystemExit(
            "Usage: python research\\early_prediction_research_v4_2.py "
            "YYYY-MM-DD [YYYY-MM-DD ...]"
        )

    OUT.mkdir(parents=True, exist_ok=True)

    frames = []

    for day in days:
        events = build_day(day)
        print(f"{day}: FIRST >22% EVENTS {len(events)}")
        frames.append(events)

    events = pd.concat(frames, ignore_index=True)
    events = add_analysis_columns(events)

    events.to_csv(
        OUT / "first_22_point_in_time_futures_enriched.csv",
        index=False,
    )

    population = population_effects(events)
    population.to_csv(
        OUT / "population_futures_oi_effects.csv",
        index=False,
    )

    print()
    print("SDL EARLY PREDICTION RESEARCH v4.2")
    print("SOURCE ROOT:", INTRADAY_SOURCE_ROOT)
    print("OUTPUTS:", OUT)
    print("POINT-IN-TIME: SAME SYMBOL + SAME TIMESTAMP COALESCED")
    print("FUTURES: Fut OI + Fut OI Chg + Fut OI Chg % + Fut Buildup")
    print("NO SCORE / NO PROBABILITY / NO TRADE SIGNAL")
    print()
    print(population.to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:])
