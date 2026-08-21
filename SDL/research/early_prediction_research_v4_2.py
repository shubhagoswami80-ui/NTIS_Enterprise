from __future__ import annotations

"""
SDL EARLY PREDICTION RESEARCH v4.2
Research only. Production SDL is NOT modified.

Purpose
-------
Chronological point-in-time research for FIRST >22% events.

Important:
- v3 baseline is imported/read-only.
- Only SDL/research is involved.
- Same Symbol + same timestamp snapshots are coalesced.
- Futures fields are retained independently:
    Fut OI
    Fut OI Chg
    Fut OI Chg %
    Fut Buildup
- No score.
- No probability.
- No trade signal.

Point-in-time rule
------------------
Feature values are taken from the coalesced FIRST >22% timestamp.
Later observations are used only for outcome calculation.
"""

import sys
from pathlib import Path

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


FUTURES_COLUMNS = [
    "futures_oi",
    "futures_oi_chg",
    "futures_oi_chg_pct",
    "futures_buildup",
]

VALUE_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "current_price",
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
    "atm_straddle_pct",
    "atm_straddle_price",
]


def first_valid(series):
    series = series.dropna()
    return series.iloc[0] if not series.empty else np.nan


def normalize_futures_columns(df):
    """
    Normalize either canonical fields or physical Futures workbook headers.
    This is intentionally defensive so the research layer works with
    Support/Resistance and FuturesOI workbook variants.
    """
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    aliases = {
        "futures_oi": [
            "futures_oi",
            "Fut OI",
            "Futures OI",
            "Future OI",
        ],
        "futures_oi_chg": [
            "futures_oi_chg",
            "Fut OI Chg",
            "Futures OI Chg",
            "Future OI Chg",
        ],
        "futures_oi_chg_pct": [
            "futures_oi_chg_pct",
            "Fut OI Chg %",
            "Fut OI Chg%",
            "Futures OI Chg %",
            "Futures OI Chg%",
        ],
        "futures_buildup": [
            "futures_buildup",
            "Fut Buildup",
            "Futures Buildup",
            "Future Buildup",
        ],
    }

    lookup = {str(c).strip().lower(): c for c in out.columns}

    for canonical, names in aliases.items():
        if canonical in out.columns:
            continue

        source = None
        for name in names:
            source = lookup.get(name.lower())
            if source is not None:
                break

        if source is not None:
            out[canonical] = out[source]

    for col in [
        "futures_oi",
        "futures_oi_chg",
        "futures_oi_chg_pct",
    ]:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")

    if "futures_buildup" not in out.columns:
        out["futures_buildup"] = np.nan

    return out


def read_research_snapshot(path, day, seq):
    """
    Read through the v3 reader first.

    If v3 did not expose Futures fields, read the physical workbook and
    recover only the four Futures fields. No source file is modified.
    """
    df = read_snapshot(path, day, seq)

    if df.empty:
        return df

    df = normalize_futures_columns(df)

    # v3 may create canonical Futures columns as NaN even when the
    # physical workbook contains the real "Fut OI" fields. Therefore
    # inspect the workbook whenever the canonical values are entirely
    # unavailable.
    missing_futures = (
        df["futures_oi"].notna().any()
        or df["futures_oi_chg"].notna().any()
        or df["futures_oi_chg_pct"].notna().any()
    )

    if missing_futures:
        return df

    try:
        raw = pd.read_excel(path)
    except Exception:
        return df

    raw.columns = [str(c).strip() for c in raw.columns]

    if "Symbol" not in raw.columns:
        return df

    raw["Symbol"] = (
        raw["Symbol"].astype(str).str.strip().str.upper()
    )

    raw = normalize_futures_columns(raw)

    keep = [
        "Symbol",
        "futures_oi",
        "futures_oi_chg",
        "futures_oi_chg_pct",
        "futures_buildup",
    ]

    raw = raw[keep].copy()

    df["Symbol"] = (
        df["Symbol"].astype(str).str.strip().str.upper()
    )

    df = df.drop(
        columns=FUTURES_COLUMNS,
        errors="ignore",
    ).merge(
        raw,
        on="Symbol",
        how="left",
    )

    return df


def coalesce_day(day):
    frames = []

    for seq, path in enumerate(files_for_day(day)):
        frame = read_research_snapshot(path, day, seq)

        if not frame.empty:
            frames.append(frame)

    if not frames:
        raise RuntimeError(f"No readable snapshots for {day}")

    raw = pd.concat(frames, ignore_index=True)

    raw["Symbol"] = (
        raw["Symbol"].astype(str).str.strip().str.upper()
    )

    raw = raw[
        raw["Symbol"].ne("")
        & raw["Symbol"].ne("NAN")
    ].copy()

    raw["_ts"] = pd.to_datetime(
        raw["_ts"],
        errors="coerce",
    )

    raw = raw.sort_values(
        ["Symbol", "_ts", "_seq"]
    )

    for col in VALUE_COLUMNS:
        if col not in raw.columns:
            raw[col] = np.nan

    grouped = (
        raw.groupby(
            ["Symbol", "_ts"],
            sort=True,
            as_index=False,
        )[VALUE_COLUMNS]
        .agg(first_valid)
    )

    source_map = (
        raw.groupby(
            ["Symbol", "_ts"],
            sort=True,
        )["_source_file"]
        .agg(
            lambda s: " | ".join(
                dict.fromkeys(map(str, s))
            )
        )
        .reset_index(name="_source_file")
    )

    out = grouped.merge(
        source_map,
        on=["Symbol", "_ts"],
        how="left",
    )

    out["_seq"] = (
        out.sort_values(
            ["Symbol", "_ts"]
        )
        .groupby("Symbol")
        .cumcount()
    )

    return out.sort_values(
        ["Symbol", "_ts", "_seq"]
    ).reset_index(drop=True)


def build_day(day):
    """
    Build FIRST >22% event per Symbol/day.

    Opening reference is taken from the first chronological observation
    available to the v3 research reader. Later observations are used only
    for outcomes.
    """
    all_df = coalesce_day(day)

    opening = (
        all_df.sort_values(
            ["Symbol", "_ts", "_seq"]
        )
        .groupby("Symbol", as_index=False)
        .first()[
            [
                "Symbol",
                "Open",
                "atm_straddle_pct",
            ]
        ]
        .rename(
            columns={
                "Open": "opening_price",
            }
        )
    )

    opening["opening_straddle_premium"] = (
        opening["opening_price"]
        * opening["atm_straddle_pct"]
        / 100.0
    )

    all_df = all_df.merge(
        opening,
        on="Symbol",
        how="left",
    )

    valid_premium = (
        all_df["opening_straddle_premium"].gt(0)
    )

    all_df["progress_pct"] = np.where(
        valid_premium,
        (
            (
                all_df["current_price"]
                - all_df["opening_price"]
            ).abs()
            / all_df["opening_straddle_premium"]
            * 100.0
        ),
        np.nan,
    )

    all_df["direction"] = np.select(
        [
            all_df["current_price"]
            > all_df["opening_price"],

            all_df["current_price"]
            < all_df["opening_price"],
        ],
        [
            "UP",
            "DOWN",
        ],
        default="",
    )

    candidates = (
        all_df[
            all_df["progress_pct"].gt(22)
        ]
        .sort_values(
            ["Symbol", "_ts", "_seq"]
        )
    )

    first22 = candidates.drop_duplicates(
        "Symbol",
        keep="first",
    )

    rows = []

    for _, event in first22.iterrows():

        later = all_df[
            (all_df["Symbol"] == event["Symbol"])
            & (all_df["_ts"] > event["_ts"])
        ].sort_values(
            ["_ts", "_seq"]
        )

        result = {
            "trading_date": day,
            "Symbol": event["Symbol"],
            "first_22_timestamp": event["_ts"],
            "first_22_progress_pct": event["progress_pct"],
            "direction": event["direction"],
            "first_22_source_file": event["_source_file"],
            "opening_price": event["opening_price"],
            "opening_straddle_premium":
                event["opening_straddle_premium"],
        }

        # All features are captured from the FIRST >22% coalesced row.
        for col in VALUE_COLUMNS:
            result[col] = event.get(
                col,
                np.nan,
            )

        for target in (
            40,
            45,
            50,
            100,
        ):
            hits = later[
                later["progress_pct"]
                >= target
            ]

            result[
                f"target_{target}_reached"
            ] = not hits.empty

            result[
                f"time_to_{target}_min"
            ] = (
                (
                    hits.iloc[0]["_ts"]
                    - event["_ts"]
                ).total_seconds()
                / 60.0
                if not hits.empty
                else np.nan
            )

        result[
            "max_progress_after_22"
        ] = (
            float(
                later["progress_pct"].max()
            )
            if not later.empty
            else np.nan
        )

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
        return (
            "SUPPORT"
            if value > 0
            else "CONTRADICT"
        )

    if direction == "DOWN":
        return (
            "SUPPORT"
            if value < 0
            else "CONTRADICT"
        )

    return "UNAVAILABLE"


def add_analysis_columns(df):
    out = df.copy()

    for col in [
        "price_chg_pct",
        "futures_oi",
        "futures_oi_chg",
        "futures_oi_chg_pct",
        "pe_minus_ce_oi_chg",
    ]:
        if col not in out.columns:
            out[col] = np.nan

        if col != "futures_buildup":
            out[col] = pd.to_numeric(
                out[col],
                errors="coerce",
            )

    out["gate_price"] = [
        gate_directional(v, d)
        for v, d in zip(
            out["price_chg_pct"],
            out["direction"],
        )
    ]

    # Primary Futures feature:
    # Futures OI change percentage.
    out["gate_futures_oi"] = [
        gate_futures(v)
        for v in out["futures_oi_chg_pct"]
    ]

    # Absolute Futures OI change is retained separately.
    out["gate_futures_oi_chg"] = [
        gate_futures(v)
        for v in out["futures_oi_chg"]
    ]

    out["gate_pe_minus_ce"] = [
        gate_directional(v, d)
        for v, d in zip(
            out["pe_minus_ce_oi_chg"],
            out["direction"],
        )
    ]

    return out


def population_effects(df):
    masks = {
        "ALL_FIRST_22":
            pd.Series(
                True,
                index=df.index,
            ),

        "PRICE_GATE":
            df["gate_price"].eq(
                "SUPPORT"
            ),

        "PRICE_PLUS_FUTURES_OI":
            (
                df["gate_price"].eq("SUPPORT")
                & df["gate_futures_oi"].eq(
                    "POSITIVE"
                )
            ),

        "PRICE_PLUS_PE_CE":
            (
                df["gate_price"].eq("SUPPORT")
                & df["gate_pe_minus_ce"].eq(
                    "SUPPORT"
                )
            ),

        "PRICE_PLUS_FUTURES_OI_PLUS_PE_CE":
            (
                df["gate_price"].eq("SUPPORT")
                & df["gate_futures_oi"].eq(
                    "POSITIVE"
                )
                & df["gate_pe_minus_ce"].eq(
                    "SUPPORT"
                )
            ),
    }

    rows = []

    for name, mask in masks.items():

        group = df.loc[mask]

        rows.append({
            "population": name,
            "n": len(group),

            "futures_oi_valid":
                int(
                    group[
                        "futures_oi"
                    ].notna().sum()
                ),

            "futures_oi_chg_valid":
                int(
                    group[
                        "futures_oi_chg"
                    ].notna().sum()
                ),

            "futures_oi_chg_pct_valid":
                int(
                    group[
                        "futures_oi_chg_pct"
                    ].notna().sum()
                ),

            "reached_40":
                int(
                    group[
                        "target_40_reached"
                    ].sum()
                ),

            "rate_40":
                (
                    float(
                        group[
                            "target_40_reached"
                        ].mean()
                    )
                    if len(group)
                    else np.nan
                ),

            "reached_45":
                int(
                    group[
                        "target_45_reached"
                    ].sum()
                ),

            "rate_45":
                (
                    float(
                        group[
                            "target_45_reached"
                        ].mean()
                    )
                    if len(group)
                    else np.nan
                ),

            "reached_50":
                int(
                    group[
                        "target_50_reached"
                    ].sum()
                ),

            "rate_50":
                (
                    float(
                        group[
                            "target_50_reached"
                        ].mean()
                    )
                    if len(group)
                    else np.nan
                ),

            "reached_100_secondary":
                int(
                    group[
                        "target_100_reached"
                    ].sum()
                ),
        })

    return pd.DataFrame(rows)


def main(days):
    if not days:
        raise SystemExit(
            "Usage: python research\\early_prediction_research_v4_2.py "
            "YYYY-MM-DD [YYYY-MM-DD ...]"
        )

    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    frames = []

    for day in days:

        events = build_day(day)

        print(
            f"{day}: FIRST >22% EVENTS {len(events)}"
        )

        frames.append(events)

    events = pd.concat(
        frames,
        ignore_index=True,
    )

    events = add_analysis_columns(
        events
    )

    events.to_csv(
        OUT
        / "first_22_point_in_time_futures_enriched.csv",
        index=False,
    )

    population = population_effects(
        events
    )

    population.to_csv(
        OUT
        / "population_futures_oi_effects.csv",
        index=False,
    )

    print()
    print(
        "SDL EARLY PREDICTION RESEARCH v4.2"
    )
    print(
        "SOURCE ROOT:",
        INTRADAY_SOURCE_ROOT,
    )
    print(
        "OUTPUTS:",
        OUT,
    )
    print(
        "POINT-IN-TIME: "
        "SAME SYMBOL + SAME TIMESTAMP COALESCED"
    )
    print(
        "FUTURES: "
        "Fut OI + Fut OI Chg + "
        "Fut OI Chg % + Fut Buildup"
    )
    print(
        "NO SCORE / NO PROBABILITY / NO TRADE SIGNAL"
    )
    print()
    print(
        population.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:])
