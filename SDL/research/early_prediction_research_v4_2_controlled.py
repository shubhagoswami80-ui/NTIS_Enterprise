from __future__ import annotations

"""
SDL Early Prediction Research v4.2.1-CONTROLLED
---------------------------------------------
Research only. Production code is NOT modified.

Baseline:
    SDL/research/early_prediction_research.py (Git master / v3)

Controlled changes:
    1. Preserve v3 chronological FIRST >22% event logic.
    2. Independently scan physical workbooks for Futures/Options OI-change
       fields because the v3 reader can legitimately expose NaN canonical
       fields when a companion workbook carries the data.
    3. Coalesce same Symbol + same timestamp.
    4. Attach only point-in-time evidence from that timestamp.
    5. Keep absolute OI as context; OI CHANGE is the primary evidence.
    6. OI CHANGE is the primary sentiment evidence. Zero is preserved when
       explicitly present; missing is never converted to zero.
    7. Validate physical source availability separately from event attachment.
    8. No score, probability, or trade signal.
"""

import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from early_prediction_research import (
    INTRADAY_SOURCE_ROOT,
    files_for_day,
    read_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output" / "early_prediction_futures_oi_v4_2_controlled"

TARGETS = (40.0, 45.0, 50.0, 100.0)

# These are evidence fields. Absolute OI is retained only for reference.
EVIDENCE_COLUMNS = [
    "price_chg_pct",
    "futures_oi",
    "futures_oi_chg",
    "futures_oi_chg_pct",
    "futures_buildup",
    "ce_oi_chg",
    "pe_oi_chg",
    "ce_oi_chg_pct",
    "pe_oi_chg_pct",
    "pe_minus_ce_oi_chg",
]

NUMERIC_EVIDENCE = [
    "price_chg_pct",
    "futures_oi",
    "futures_oi_chg",
    "futures_oi_chg_pct",
    "ce_oi_chg",
    "pe_oi_chg",
    "ce_oi_chg_pct",
    "pe_oi_chg_pct",
    "pe_minus_ce_oi_chg",
]


def norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def to_numeric_evidence(values):
    """Convert numeric evidence while accepting display-formatted percentages."""
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce")
    text = values.astype(str).str.strip()
    text = text.str.replace(",", "", regex=False)
    text = text.str.replace("%", "", regex=False)
    text = text.str.replace(r"\s+", "", regex=True)
    return pd.to_numeric(text, errors="coerce")

def resolve(columns, aliases):
    lookup = {norm(c): c for c in columns}
    for alias in aliases:
        hit = lookup.get(norm(alias))
        if hit is not None:
            return hit
    return None

def _is_pct_name(value):
    text = str(value).strip().lower()
    return (
        "%" in text
        or "pct" in re.sub(r"[^a-z0-9]+", "", text)
        or "percent" in text
    )


def resolve_populated(df, aliases):
    """
    Resolve a physical source column without collapsing percentage semantics.

    Important: norm() intentionally removes punctuation, so:
        "Fut OI Chg"  -> "futoichg"
        "Fut OI Chg %" -> "futoichg"
    They therefore cannot be distinguished by norm() alone.

    Prefer an exact semantic match first, then normalized matching with a
    percentage/non-percentage compatibility check. Missing values remain
    missing; this function never manufactures zeroes.
    """
    columns = list(df.columns)
    candidates = []

    for alias in aliases:
        alias_pct = _is_pct_name(alias)

        # First prefer the physical column with the same semantic pct status.
        exact = [
            c for c in columns
            if str(c).strip().lower() == str(alias).strip().lower()
            and _is_pct_name(c) == alias_pct
        ]
        for hit in exact:
            if hit not in candidates:
                candidates.append(hit)

        # Then normalized matching, but reject pct/non-pct collisions.
        for c in columns:
            if norm(c) == norm(alias) and _is_pct_name(c) == alias_pct:
                if c not in candidates:
                    candidates.append(c)

    # Prefer populated candidates. Do not let an empty canonical column mask
    # a populated physical source column.
    for hit in candidates:
        values = pd.to_numeric(df[hit], errors="coerce")
        if values.notna().any():
            return hit

    return candidates[0] if candidates else None


ALIASES = {
    "price_chg_pct": [
        "price_chg_pct", "Price Chg %", "Price Chg%",
        "Price Change %", "Price Change%",
    ],
    "futures_oi": [
        "futures_oi", "Fut OI", "Futures OI", "Future OI",
    ],
    "futures_oi_chg": [
        "futures_oi_chg",
        "Fut OI Chg",
        "Futures OI Chg",
        "Future OI Chg",
        "OI Chg",
        "OI Chg(Value)",
        "OI Chg (Value)",
    ],
    "futures_oi_chg_pct": [
        "futures_oi_chg_pct",
        "Fut OI Chg %",
        "Fut OI Chg%",
        "Futures OI Chg %",
        "Futures OI Chg%",
        "OI Chg %",
        "OI Chg%",
    ],
    "futures_buildup": [
        "futures_buildup", "Fut Buildup", "Bldp", "Futures Buildup",
        "Future Buildup",
    ],
    "ce_oi_chg": [
        "ce_oi_chg", "CE OI Chg", "Call OI Chg", "Tot CE OI Chg",
    ],
    "pe_oi_chg": [
        "pe_oi_chg", "PE OI Chg", "Put OI Chg", "Tot PE OI Chg",
    ],
    "ce_oi_chg_pct": [
        "ce_oi_chg_pct", "CE OI Chg %", "Call OI Chg %",
        "Tot CE OI Chg %",
    ],
    "pe_oi_chg_pct": [
        "pe_oi_chg_pct", "PE OI Chg %", "Put OI Chg %",
        "Tot PE OI Chg %",
    ],
    "pe_minus_ce_oi_chg": [
        "pe_minus_ce_oi_chg", "PE-CE OI Chg", "Tot PE-CE OI Chg",
    ],
}


def parse_ts(path):
    match = re.search(r"_(\d{6})\.xlsx$", path.name, re.I)
    if match:
        return datetime.strptime(match.group(1), "%H%M%S")
    return datetime.fromtimestamp(path.stat().st_mtime)


def normalized_day_timestamp(path, day):
    ts = parse_ts(path)
    return pd.Timestamp(
        datetime.strptime(day, "%Y-%m-%d").replace(
            hour=ts.hour,
            minute=ts.minute,
            second=ts.second,
        )
    )


def extract_evidence_from_workbook(path, day):
    """
    Independently read the physical workbook.

    This is deliberately separate from the v3 canonical reader. It prevents
    a canonical all-NaN column from hiding real physical fields such as
    'Fut OI Chg', 'Fut OI Chg %', 'Call OI Chg', and 'Put OI Chg'.
    """
    try:
        raw = pd.read_excel(path)
    except Exception:
        return pd.DataFrame()

    if "Symbol" not in raw.columns:
        return pd.DataFrame()

    raw.columns = [str(c).strip() for c in raw.columns]
    raw["Symbol"] = (
        raw["Symbol"].astype(str).str.strip().str.upper()
    )
    raw = raw[
        raw["Symbol"].ne("") & raw["Symbol"].ne("NAN")
    ].copy()

    out = pd.DataFrame({
        "Symbol": raw["Symbol"],
        "_ts": normalized_day_timestamp(path, day),
        "_source_file": str(path),
    })

    found_any = False

    for canonical, aliases in ALIASES.items():
        source = resolve_populated(raw, aliases)
        if source is None:
            out[canonical] = np.nan
            continue

        # Percentage/non-percentage semantics have already been enforced by
        # resolve_populated(), which compares _is_pct_name() before normalized
        # matching. Do not run norm(source) here because norm() deliberately
        # removes "%" and would collapse "Fut OI Chg %" into "Fut OI Chg".
        out[canonical] = raw[source]
        found_any = True

        if canonical in NUMERIC_EVIDENCE:
            out[canonical] = to_numeric_evidence(out[canonical])

    if not found_any:
        return pd.DataFrame()

    # If the source supplies absolute CE/PE OI change but not the derived
    # PE-CE field, derive it without replacing a source-provided value.
    if (
        out["pe_minus_ce_oi_chg"].isna().all()
        and out["pe_oi_chg"].notna().any()
        and out["ce_oi_chg"].notna().any()
    ):
        out["pe_minus_ce_oi_chg"] = (
            out["pe_oi_chg"] - out["ce_oi_chg"]
        )

    return out


def source_validation_for_day(day):
    """
    Validate the physical source BEFORE the point-in-time join.

    This distinguishes:
      SOURCE_HAS_DATA -> ATTACHMENT_FAILED
      SOURCE_HAS_NO_DATA -> genuinely unavailable/exceptional
    """
    counts = {c: 0 for c in [
        "futures_oi_chg",
        "futures_oi_chg_pct",
        "ce_oi_chg",
        "pe_oi_chg",
        "pe_minus_ce_oi_chg",
    ]}
    nonzero = {c: 0 for c in counts}
    matched_files = 0
    futures_schema_counts = {"fut_prefixed": 0, "futuresoi": 0}

    for path in files_for_day(day):
        try:
            raw = pd.read_excel(path)
        except Exception:
            continue
        raw.columns = [str(c).strip() for c in raw.columns]
        if "Symbol" not in raw.columns:
            continue

        found = False
        for canonical in counts:
            source = resolve_populated(raw, ALIASES[canonical])
            if source is None:
                continue
            found = True
            if canonical in ("futures_oi_chg", "futures_oi_chg_pct"):
                sn = norm(source)
                if canonical == "futures_oi_chg":
                    if sn.startswith("fut"):
                        futures_schema_counts["fut_prefixed"] += 1
                    elif sn in ("oichg", "oichgvalue"):
                        futures_schema_counts["futuresoi"] += 1
                elif canonical == "futures_oi_chg_pct":
                    # resolve_populated() has already enforced percentage semantics.
                    futures_schema_counts["futuresoi"] += 1
            values = to_numeric_evidence(raw[source])
            counts[canonical] += int(values.notna().sum())
            nonzero[canonical] += int(
                (values.notna() & values.ne(0)).sum()
            )

        if found:
            matched_files += 1

    return {
        "source_files_with_evidence": matched_files,
        **{f"source_{k}_valid": v for k, v in counts.items()},
        **{f"source_{k}_nonzero": v for k, v in nonzero.items()},
        "futures_schema_fut_prefixed": futures_schema_counts["fut_prefixed"],
        "futures_schema_futuresoi": futures_schema_counts["futuresoi"],
    }



def raw_evidence_for_day(day):
    frames = []
    for path in files_for_day(day):
        frame = extract_evidence_from_workbook(path, day)
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return pd.DataFrame(
            columns=["Symbol", "_ts", "_source_file"] + EVIDENCE_COLUMNS
        )

    raw = pd.concat(frames, ignore_index=True)

    # Same Symbol + timestamp: preserve first valid value from any companion
    # workbook. Never turn missing into zero.
    agg = {}
    for col in EVIDENCE_COLUMNS:
        agg[col] = lambda s: (
            s.dropna().iloc[0] if s.dropna().shape[0] else np.nan
        )

    evidence = (
        raw.sort_values(["Symbol", "_ts"])
        .groupby(["Symbol", "_ts"], as_index=False)
        .agg(agg)
    )

    source = (
        raw.groupby(["Symbol", "_ts"], as_index=False)["_source_file"]
        .agg(lambda s: " | ".join(dict.fromkeys(map(str, s))))
    )

    return evidence.merge(
        source,
        on=["Symbol", "_ts"],
        how="left",
    )


def v3_snapshot_day(day):
    """
    Use the Git-baseline v3 reader for the actual chronological event data.
    The physical evidence scan is only an enrichment layer.
    """
    frames = []

    for seq, path in enumerate(files_for_day(day)):
        frame = read_snapshot(path, day, seq)
        if not frame.empty:
            frames.append(frame)

    if not frames:
        raise RuntimeError(f"No readable snapshots for {day}")

    raw = pd.concat(frames, ignore_index=True)
    raw = raw.sort_values(["Symbol", "_ts", "_seq"])

    value_cols = [
        "Open", "High", "Low", "Close", "current_price",
        "price_chg_pct", "oi_chg_pct", "iv_chg_pct", "pcr_chg_pct",
        "ce_oi_chg_pct", "pe_oi_chg_pct", "pe_minus_ce_oi_chg",
        "volume", "volume_chg_pct", "ivr", "ivp",
        "iv_hv10", "iv_hv20", "iv_hv30",
        "atm_straddle_pct", "atm_straddle_price",
    ]

    for col in value_cols:
        if col not in raw.columns:
            raw[col] = np.nan

    def first_valid(series):
        non_null = series.dropna()
        return non_null.iloc[0] if len(non_null) else np.nan

    grouped = (
        raw.sort_values(["Symbol", "_ts", "_seq"])
        .groupby(["Symbol", "_ts"], as_index=False)[value_cols]
        .agg(first_valid)
    )

    source = (
        raw.groupby(["Symbol", "_ts"], as_index=False)["_source_file"]
        .agg(lambda s: " | ".join(dict.fromkeys(map(str, s))))
    )

    out = grouped.merge(
        source,
        on=["Symbol", "_ts"],
        how="left",
    )

    out["_seq"] = (
        out.sort_values(["Symbol", "_ts"])
        .groupby("Symbol")
        .cumcount()
    )

    return out.sort_values(
        ["Symbol", "_ts", "_seq"]
    ).reset_index(drop=True)


def coalesce_with_evidence(day):
    base = v3_snapshot_day(day)
    evidence = raw_evidence_for_day(day)

    if evidence.empty:
        for col in EVIDENCE_COLUMNS:
            base[col] = np.nan
        base["evidence_match"] = "NO_SOURCE_EVIDENCE"
        base["evidence_source_file"] = ""
        return base

    # Remove any v3 evidence columns before controlled physical-source
    # attachment. The physical workbook is authoritative for these fields.
    base = base.drop(
        columns=EVIDENCE_COLUMNS,
        errors="ignore",
    )

    out = base.merge(
        evidence,
        on=["Symbol", "_ts"],
        how="left",
    )

    out["evidence_match"] = np.where(
        out["futures_oi_chg"].notna()
        | out["futures_oi_chg_pct"].notna()
        | out["ce_oi_chg"].notna()
        | out["pe_oi_chg"].notna()
        | out["pe_minus_ce_oi_chg"].notna(),
        "EXACT_TIMESTAMP",
        "NO_EXACT_TIMESTAMP_EVIDENCE",
    )

    out["evidence_source_file"] = out["_source_file_y"].fillna("")
    out = out.drop(
        columns=["_source_file_y"],
        errors="ignore",
    ).rename(
        columns={"_source_file_x": "_source_file"}
    )

    return out.sort_values(
        ["Symbol", "_ts", "_seq"]
    ).reset_index(drop=True)


def build_day(day):
    all_df = coalesce_with_evidence(day)

    opening = (
        all_df.sort_values(["Symbol", "_ts", "_seq"])
        .groupby("Symbol", as_index=False)
        .first()[
            ["Symbol", "Open", "atm_straddle_pct"]
        ]
        .rename(columns={"Open": "opening_price"})
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

    valid = all_df["opening_straddle_premium"].gt(0)

    all_df["progress_pct"] = np.where(
        valid,
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
        ["UP", "DOWN"],
        default="",
    )

    first22 = (
        all_df[all_df["progress_pct"].gt(22)]
        .sort_values(["Symbol", "_ts", "_seq"])
        .drop_duplicates("Symbol", keep="first")
    )

    rows = []

    for _, event in first22.iterrows():
        later = all_df[
            (all_df["Symbol"] == event["Symbol"])
            & (all_df["_ts"] > event["_ts"])
        ].sort_values(["_ts", "_seq"])

        row = {
            "trading_date": day,
            "Symbol": event["Symbol"],
            "first_22_timestamp": event["_ts"],
            "first_22_progress_pct": event["progress_pct"],
            "direction": event["direction"],
            "first_22_source_file": event["_source_file"],
            "evidence_match": event["evidence_match"],
            "evidence_source_file": event["evidence_source_file"],
        }

        for col in EVIDENCE_COLUMNS:
            row[col] = event.get(col, np.nan)

        for target in TARGETS:
            hits = later[
                later["progress_pct"] >= target
            ]
            row[f"target_{int(target)}_reached"] = not hits.empty
            row[f"time_to_{int(target)}_min"] = (
                (
                    hits.iloc[0]["_ts"]
                    - event["_ts"]
                ).total_seconds() / 60.0
                if not hits.empty
                else np.nan
            )

        row["max_progress_after_22"] = (
            float(later["progress_pct"].max())
            if not later.empty
            else np.nan
        )

        rows.append(row)

    return pd.DataFrame(rows)


def population_effects(df):
    """
    Descriptive research only.

    OI change is the primary evidence. Absolute Futures OI is NOT used
    to qualify a population.
    """
    # Defensive normalization: older/partial event frames may not carry
    # price_chg_pct. Missing means unavailable, never zero.
    if "price_chg_pct" not in df.columns:
        df = df.copy()
        df["price_chg_pct"] = np.nan
    else:
        df["price_chg_pct"] = pd.to_numeric(
            df["price_chg_pct"], errors="coerce"
        )

    price_support = (
        (df["direction"] == "UP")
        & df["price_chg_pct"].gt(0)
    ) | (
        (df["direction"] == "DOWN")
        & df["price_chg_pct"].lt(0)
    )

    futures_chg_support = (
        df["futures_oi_chg"].gt(0)
    )

    futures_pct_support = (
        df["futures_oi_chg_pct"].gt(0)
    )

    pe_ce_support = (
        ((df["direction"] == "UP")
         & df["pe_minus_ce_oi_chg"].gt(0))
        | ((df["direction"] == "DOWN")
           & df["pe_minus_ce_oi_chg"].lt(0))
    )

    masks = {
        "ALL_FIRST_22": pd.Series(True, index=df.index),
        "PRICE_GATE": price_support,
        "PRICE_PLUS_FUTURES_OI_CHG": (
            price_support & futures_chg_support
        ),
        "PRICE_PLUS_FUTURES_OI_CHG_PCT": (
            price_support & futures_pct_support
        ),
        "PRICE_PLUS_PE_CE": (
            price_support & pe_ce_support
        ),
        "PRICE_PLUS_FUTURES_OI_CHG_PLUS_PE_CE": (
            price_support
            & futures_chg_support
            & pe_ce_support
        ),
        "PRICE_PLUS_FUTURES_OI_CHG_PCT_PLUS_PE_CE": (
            price_support
            & futures_pct_support
            & pe_ce_support
        ),
    }

    # Never fail because a research field was omitted by an upstream
    # event frame. Missing research data remains NaN/False, not zero.
    required_numeric = [
        "futures_oi",
        "futures_oi_chg",
        "futures_oi_chg_pct",
        "ce_oi_chg",
        "pe_oi_chg",
        "pe_minus_ce_oi_chg",
    ]
    df = df.copy()
    for col in required_numeric:
        if col not in df.columns:
            df[col] = np.nan
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "evidence_match" not in df.columns:
        df["evidence_match"] = "NO_EXACT_TIMESTAMP_EVIDENCE"

    rows = []

    for name, mask in masks.items():
        g = df.loc[mask]

        rows.append({
            "population": name,
            "n": len(g),
            "futures_oi_valid": int(
                g["futures_oi"].notna().sum()
            ),
            "futures_oi_chg_valid": int(
                g["futures_oi_chg"].notna().sum()
            ),
            "futures_oi_chg_pct_valid": int(
                g["futures_oi_chg_pct"].notna().sum()
            ),
            "ce_oi_chg_valid": int(
                g["ce_oi_chg"].notna().sum()
            ),
            "pe_oi_chg_valid": int(
                g["pe_oi_chg"].notna().sum()
            ),
            "pe_minus_ce_oi_chg_valid": int(
                g["pe_minus_ce_oi_chg"].notna().sum()
            ),
            "exact_evidence_match": int(
                g["evidence_match"].eq("EXACT_TIMESTAMP").sum()
            ),
            "reached_40": int(
                g["target_40_reached"].sum()
            ),
            "rate_40": (
                float(g["target_40_reached"].mean())
                if len(g) else np.nan
            ),
            "reached_45": int(
                g["target_45_reached"].sum()
            ),
            "rate_45": (
                float(g["target_45_reached"].mean())
                if len(g) else np.nan
            ),
            "reached_50": int(
                g["target_50_reached"].sum()
            ),
            "rate_50": (
                float(g["target_50_reached"].mean())
                if len(g) else np.nan
            ),
            "reached_100_secondary": int(
                g["target_100_reached"].sum()
            ),
        })

    return pd.DataFrame(rows)


def run(*days):
    if not days:
        raise SystemExit(
            "Usage: python research\\early_prediction_research_v4_2_controlled.py "
            "YYYY-MM-DD [YYYY-MM-DD ...]"
        )

    OUT.mkdir(parents=True, exist_ok=True)

    frames = []
    source_diagnostics = []

    for day in days:
        sd = source_validation_for_day(day)
        source_diagnostics.append({"trading_date": day, **sd})
        print(
            f"{day}: SOURCE FUT_OI_CHG={sd['source_futures_oi_chg_valid']} "
            f"FUT_OI_CHG_PCT={sd['source_futures_oi_chg_pct_valid']} "
            f"CE_OI_CHG={sd['source_ce_oi_chg_valid']} "
            f"PE_OI_CHG={sd['source_pe_oi_chg_valid']} "
            f"PE_MINUS_CE={sd['source_pe_minus_ce_oi_chg_valid']}"
        )

        events = build_day(day)
        print(
            f"{day}: FIRST >22% EVENTS {len(events)}"
        )
        frames.append(events)

    events = pd.concat(
        frames,
        ignore_index=True,
    )

    events.to_csv(
        OUT / "first_22_point_in_time_controlled.csv",
        index=False,
    )

    population = population_effects(events)

    population.to_csv(
        OUT / "population_oi_change_effects.csv",
        index=False,
    )

    diagnostics = pd.DataFrame([{
        "events": len(events),
        "exact_timestamp_evidence": int(
            events["evidence_match"]
            .eq("EXACT_TIMESTAMP")
            .sum()
        ),
        "no_exact_timestamp_evidence": int(
            events["evidence_match"]
            .eq("NO_EXACT_TIMESTAMP_EVIDENCE")
            .sum()
        ),
        "futures_oi_chg_valid": int(
            events["futures_oi_chg"].notna().sum()
        ),
        "futures_oi_chg_pct_valid": int(
            events["futures_oi_chg_pct"].notna().sum()
        ),
        "ce_oi_chg_valid": int(
            events["ce_oi_chg"].notna().sum()
        ),
        "pe_oi_chg_valid": int(
            events["pe_oi_chg"].notna().sum()
        ),
        "pe_minus_ce_oi_chg_valid": int(
            events["pe_minus_ce_oi_chg"].notna().sum()
        ),
    }])

    diagnostics.to_csv(
        OUT / "point_in_time_attachment_diagnostics.csv",
        index=False,
    )

    pd.DataFrame(source_diagnostics).to_csv(
        OUT / "source_field_validation.csv",
        index=False,
    )

    print()
    print("SDL EARLY PREDICTION RESEARCH v4.2 CONTROLLED")
    print("BASELINE: Git master v3 reader")
    print("SOURCE ROOT:", INTRADAY_SOURCE_ROOT)
    print("OUTPUTS:", OUT)
    print("POINT-IN-TIME: SAME SYMBOL + SAME TIMESTAMP")
    print("PRIMARY EVIDENCE: OI CHANGE, NOT ABSOLUTE OI")
    print(
        "FUTURES: Fut OI Chg + Fut OI Chg % "
        "(Fut OI reference, Fut Buildup context)"
    )
    print(
        "OPTIONS: CE OI Chg + PE OI Chg + PE-CE OI Chg"
    )
    print("NO SCORE / NO PROBABILITY / NO TRADE SIGNAL")
    print()
    print("ATTACHMENT DIAGNOSTICS")
    print(diagnostics.to_string(index=False))
    print()
    print("POPULATION EFFECTS")
    print(population.to_string(index=False))


if __name__ == "__main__":
    run(*sys.argv[1:])
