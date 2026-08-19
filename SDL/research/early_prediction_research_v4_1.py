"""
SDL Early Prediction Research v4.1
Research-only gate audit built directly on the existing v3 engine.

Purpose:
- Preserve v3 point-in-time first >22% event construction.
- Test whether additional FIRST-OBSERVATION features filter the
  >22% population into stronger 40/45/50% continuation populations.
- No score, probability, trade signal, dashboard or production changes.

Run from:
    E:/NSE_Daily_Analysis/SDL

Example:
    python research/early_prediction_research_v4_1.py 2026-08-12 2026-08-13
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Import the ACTUAL frozen v3 research implementation.
# v3 already performs the chronological snapshot replay and creates
# first_22_point_in_time.csv with point-in-time feature values.
RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from early_prediction_research import build_day, INTRADAY_SOURCE_ROOT


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output" / "early_prediction_gate_audit"


def safe_num(df, col):
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def classify_support(row, direction, feature):
    """Return SUPPORT / CONTRADICT / NEUTRAL / UNAVAILABLE.

    These are descriptive research gates only. They are deliberately
    transparent and are not a trading rule.
    """
    value = row.get(feature, np.nan)
    if pd.isna(value):
        return "UNAVAILABLE"

    if feature == "price_chg_pct":
        if direction == "UP":
            return "SUPPORT" if value > 0 else ("CONTRADICT" if value < 0 else "NEUTRAL")
        if direction == "DOWN":
            return "SUPPORT" if value < 0 else ("CONTRADICT" if value > 0 else "NEUTRAL")

    if feature == "iv_chg_pct":
        return "SUPPORT" if value > 0 else ("CONTRADICT" if value < 0 else "NEUTRAL")

    if feature == "futures_oi_chg_pct":
        return "SUPPORT" if value > 0 else ("CONTRADICT" if value < 0 else "NEUTRAL")

    if feature == "pe_minus_ce_oi_chg":
        if direction == "UP":
            return "SUPPORT" if value > 0 else ("CONTRADICT" if value < 0 else "NEUTRAL")
        if direction == "DOWN":
            return "SUPPORT" if value < 0 else ("CONTRADICT" if value > 0 else "NEUTRAL")

    if feature == "pcr_chg_pct":
        if direction == "UP":
            return "SUPPORT" if value > 0 else ("CONTRADICT" if value < 0 else "NEUTRAL")
        if direction == "DOWN":
            return "SUPPORT" if value < 0 else ("CONTRADICT" if value > 0 else "NEUTRAL")

    if feature == "ce_oi_chg_pct":
        # CE OI change alone is retained as a descriptive factor.
        return "POSITIVE" if value > 0 else ("NEGATIVE" if value < 0 else "NEUTRAL")

    if feature == "pe_oi_chg_pct":
        return "POSITIVE" if value > 0 else ("NEGATIVE" if value < 0 else "NEUTRAL")

    return "UNCLASSIFIED"


def build_events(days):
    frames = []
    for day in days:
        print(f"--- {day} ---")
        df = build_day(day)
        print(f"FIRST >22% EVENTS: {len(df)}")
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def add_gate_columns(df):
    out = df.copy()

    for col in [
        "price_chg_pct",
        "oi_chg_pct",
        "iv_chg_pct",
        "pcr_chg_pct",
        "ce_oi_chg_pct",
        "pe_oi_chg_pct",
        "pe_minus_ce_oi_chg",
        "futures_oi_chg_pct",
    ]:
        out[col] = safe_num(out, col)

    for feature in [
        "price_chg_pct",
        "futures_oi_chg_pct",
        "iv_chg_pct",
        "pcr_chg_pct",
        "pe_minus_ce_oi_chg",
        "ce_oi_chg_pct",
        "pe_oi_chg_pct",
    ]:
        name = {
            "price_chg_pct": "gate_price",
            "futures_oi_chg_pct": "gate_futures_oi",
            "iv_chg_pct": "gate_iv",
            "pcr_chg_pct": "gate_pcr",
            "pe_minus_ce_oi_chg": "gate_pe_minus_ce",
            "ce_oi_chg_pct": "gate_ce_oi",
            "pe_oi_chg_pct": "gate_pe_oi",
        }[feature]

        out[name] = out.apply(
            lambda r: classify_support(r, str(r.get("direction", "")).upper(), feature),
            axis=1,
        )

    # A deliberately conservative "directional confirmation" gate:
    # price must agree with direction AND at least two independent
    # directional/structure factors must support it.
    directional = [
        "gate_futures_oi",
        "gate_iv",
        "gate_pcr",
        "gate_pe_minus_ce",
    ]
    out["supporting_factor_count"] = sum(
        (out[c] == "SUPPORT").astype(int) for c in directional
    )
    out["price_gate_pass"] = out["gate_price"].eq("SUPPORT")
    out["price_plus_1_factor"] = (
        out["price_gate_pass"] & out["supporting_factor_count"].ge(1)
    )
    out["price_plus_2_factors"] = (
        out["price_gate_pass"] & out["supporting_factor_count"].ge(2)
    )
    out["price_plus_3_factors"] = (
        out["price_gate_pass"] & out["supporting_factor_count"].ge(3)
    )

    return out


def outcome_table(df, population_name, mask):
    g = df.loc[mask]
    n = len(g)
    return {
        "population": population_name,
        "n": n,
        "reached_40": int(g["target_40_reached"].sum()) if n else 0,
        "rate_40": float(g["target_40_reached"].mean()) if n else np.nan,
        "reached_45": int(g["target_45_reached"].sum()) if n else 0,
        "rate_45": float(g["target_45_reached"].mean()) if n else np.nan,
        "reached_50": int(g["target_50_reached"].sum()) if n else 0,
        "rate_50": float(g["target_50_reached"].mean()) if n else np.nan,
        "reached_100_secondary": int(g["target_100_reached"].sum()) if n else 0,
    }


def population_effects(df):
    masks = {
        "ALL_FIRST_22": pd.Series(True, index=df.index),
        "PRICE_GATE": df["gate_price"].eq("SUPPORT"),
        "PRICE_PLUS_1_FACTOR": df["price_plus_1_factor"],
        "PRICE_PLUS_2_FACTORS": df["price_plus_2_factors"],
        "PRICE_PLUS_3_FACTORS": df["price_plus_3_factors"],
        "PRICE_PLUS_FUTURES_OI": (
            df["gate_price"].eq("SUPPORT")
            & df["gate_futures_oi"].eq("SUPPORT")
        ),
        "PRICE_PLUS_IV": (
            df["gate_price"].eq("SUPPORT")
            & df["gate_iv"].eq("SUPPORT")
        ),
        "PRICE_PLUS_PCR": (
            df["gate_price"].eq("SUPPORT")
            & df["gate_pcr"].eq("SUPPORT")
        ),
        "PRICE_PLUS_PE_CE": (
            df["gate_price"].eq("SUPPORT")
            & df["gate_pe_minus_ce"].eq("SUPPORT")
        ),
    }

    return pd.DataFrame(
        [outcome_table(df, name, mask) for name, mask in masks.items()]
    )


def gate_state_effects(df):
    rows = []

    gate_columns = [
        "gate_price",
        "gate_futures_oi",
        "gate_iv",
        "gate_pcr",
        "gate_pe_minus_ce",
        "gate_ce_oi",
        "gate_pe_oi",
    ]

    for gate in gate_columns:
        for state, g in df.groupby(gate, dropna=False):
            n = len(g)
            rows.append({
                "gate": gate,
                "state": str(state),
                "n": n,
                "reached_40": int(g["target_40_reached"].sum()),
                "rate_40": float(g["target_40_reached"].mean()) if n else np.nan,
                "reached_45": int(g["target_45_reached"].sum()),
                "rate_45": float(g["target_45_reached"].mean()) if n else np.nan,
                "reached_50": int(g["target_50_reached"].sum()),
                "rate_50": float(g["target_50_reached"].mean()) if n else np.nan,
            })

    return pd.DataFrame(rows)


def main(days):
    if not days:
        raise SystemExit(
            "Usage: python research/early_prediction_research_v4_1.py "
            "YYYY-MM-DD [YYYY-MM-DD ...]"
        )

    OUT.mkdir(parents=True, exist_ok=True)

    events = build_events(days)
    if events.empty:
        print("No first >22% research events found.")
        return

    events = add_gate_columns(events)

    summary = pd.DataFrame([outcome_table(
        events,
        "ALL_FIRST_22",
        pd.Series(True, index=events.index),
    )])

    events.to_csv(OUT / "gate_audit_events.csv", index=False)
    summary.to_csv(OUT / "research_summary.csv", index=False)
    population_effects(events).to_csv(
        OUT / "population_effects.csv", index=False
    )
    gate_state_effects(events).to_csv(
        OUT / "gate_state_effects.csv", index=False
    )

    print()
    print("SDL EARLY PREDICTION RESEARCH v4.1")
    print("SOURCE ROOT:", INTRADAY_SOURCE_ROOT)
    print("OUTPUTS:", OUT)
    print("POINT-IN-TIME RULE: first >22% observation per symbol/day")
    print("PRIMARY TARGETS: 40%, 45%, 50%")
    print("SECONDARY OUTCOME: 100%")
    print("NO SCORE / NO PROBABILITY / NO TRADE SIGNAL")
    print("PRODUCTION MODIFIED: NO")
    print()
    print("=== POPULATION EFFECTS ===")
    print(population_effects(events).to_string(index=False))
    print()
    print("=== GATE STATE EFFECTS ===")
    print(gate_state_effects(events).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:])
