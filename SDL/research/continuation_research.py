from __future__ import annotations

"""
SDL Continuation Research V2
Research-only. Does NOT modify production pipeline/dashboard/state.

Purpose:
1. Identify the first approaching-breakout event for each symbol/day.
2. Replay later evidence to determine whether the symbol subsequently reaches
   the 100% breakout condition.
3. Join the exact/latest source Excel snapshot available at the event time.
4. Compare candidate snapshot factors between continuation and non-continuation
   events.
5. Preserve per-run and cumulative research outputs.

Run:
    python research\continuation_research.py 2026-08-12 2026-08-13 2026-08-14
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# SDL ROOT / CURRENT PRODUCTION IMPORT
# ---------------------------------------------------------------------------

SDL_ROOT = Path(__file__).resolve().parents[1]
if str(SDL_ROOT) not in sys.path:
    sys.path.insert(0, str(SDL_ROOT))

try:
    from config import (
        INTRADAY_SOURCE_ROOT,
        OUTPUT_ROOT,
        REQUIRED_EVIDENCE_DIR,
        TRADABLE_EVENTS_DIR,
    )
except Exception:
    INTRADAY_SOURCE_ROOT = Path(
        r"D:\My-data\Share_P&L\Ichart Data\Screenshot"
    )
    OUTPUT_ROOT = SDL_ROOT / "data" / "output"
    REQUIRED_EVIDENCE_DIR = OUTPUT_ROOT / "required_evidence"
    TRADABLE_EVENTS_DIR = OUTPUT_ROOT / "tradable_events"

try:
    from approaching_breakout import load_approaching_breakouts
except Exception as exc:
    raise RuntimeError(
        "Unable to import SDL root module approaching_breakout.py "
        f"from {SDL_ROOT}. Original error: {exc}"
    ) from exc


# ---------------------------------------------------------------------------
# OUTPUTS
# ---------------------------------------------------------------------------

RESEARCH_ROOT = Path(OUTPUT_ROOT) / "continuation_research"
APPROACHING_CSV = (
    Path(TRADABLE_EVENTS_DIR) / "approaching_breakouts.csv"
)

EVENT_FILE = RESEARCH_ROOT / "continuation_research_events.csv"
EFFECT_FILE = RESEARCH_ROOT / "candidate_feature_effects.csv"
SCHEMA_FILE = RESEARCH_ROOT / "source_schema_map.csv"
SUMMARY_FILE = RESEARCH_ROOT / "research_summary.csv"


# ---------------------------------------------------------------------------
# CANDIDATE FACTOR ALIASES
# ---------------------------------------------------------------------------

ALIASES = {
    "atm_straddle_price": [
        "ATM Straddle Price",
    ],
    "atm_straddle_pct": [
        "ATM Straddle %",
    ],
    "price_chg": [
        "Price Chg",
    ],
    "price_chg_pct": [
        "Price Chg %",
    ],
    "iv_chg": [
        "IV Chg",
    ],
    "iv_chg_pct": [
        "IV Chg %",
    ],
    "oi_chg": [
        "OI Chg",
    ],
    "oi_chg_pct": [
        "OI Chg %",
    ],
    "pcr_chg": [
        "PCR Chg",
    ],
    "pcr_chg_pct": [
        "PCR Chg %",
    ],
    "ce_oi_chg": [
        "Tot CE OI Chg",
    ],
    "ce_oi_chg_pct": [
        "Tot CE OI Chg %",
    ],
    "pe_oi_chg": [
        "Tot PE OI Chg",
    ],
    "pe_oi_chg_pct": [
        "Tot PE OI Chg %",
    ],
    "pe_minus_ce_oi_chg": [
        "Tot PE-CE OI Chg",
    ],
    "futures_oi": [
        "Fut OI",
        "Futures OI",
        "Future OI",
        "Fut. OI",
        "FUT OI",
    ],
    "futures_oi_chg": [
        "Fut OI Chg",
        "Futures OI Chg",
        "Future OI Chg",
        "Fut. OI Chg",
    ],
    "futures_oi_chg_pct": [
        "Fut OI Chg %",
        "Fut OI Chg%",
        "Futures OI Chg %",
        "Futures OI Chg%",
        "Future OI Chg %",
        "Future OI Chg%",
    ],
    "futures_buildup": [
        "Fut Buildup",
        "Futures Buildup",
        "Future Buildup",
        "Fut. Buildup",
    ],
    "ivr": [
        "IVR",
    ],
    "ivp": [
        "IVP",
    ],
    "iv_hv10": [
        "IV/HV10 %",
        "IV/HV10",
    ],
    "iv_hv20": [
        "IV/HV20 %",
        "IV/HV20",
    ],
    "iv_hv30": [
        "IV/HV30 %",
        "IV/HV30",
    ],
    "volume": [
        "Volume",
        "Vol",
    ],
    "volume_chg_pct": [
        "Volume Chg %",
        "Volume Chg (%)",
    ],
}


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def resolve_column(columns, aliases):
    lookup = {
        normalize(column): column
        for column in columns
    }

    for alias in aliases:
        column = lookup.get(normalize(alias))
        if column is not None:
            return column

    return None


# ---------------------------------------------------------------------------
# SOURCE FILES
# ---------------------------------------------------------------------------

def discover_day_files(trading_date: str):
    root = Path(INTRADAY_SOURCE_ROOT)

    if not root.exists():
        return []

    paths = [
        path
        for path in root.rglob("*.xlsx")
        if trading_date in str(path)
        or trading_date.replace("-", "")
        in path.name.replace("-", "")
    ]

    return sorted(
        set(paths),
        key=lambda path: path.stat().st_mtime,
    )


def load_source_snapshots(trading_date: str):
    """
    Read all source Excel files for the day.

    The file modification time is used as the snapshot timestamp because
    the existing SDL workflow already uses file mtime to order snapshots.
    """
    snapshots = []

    for path in discover_day_files(trading_date):
        try:
            frame = pd.read_excel(path)
        except Exception as exc:
            print(
                f"WARNING: unable to read {path.name}: {exc}"
            )
            continue

        if "Symbol" not in frame.columns:
            continue

        frame = frame.copy()

        frame["Symbol"] = (
            frame["Symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        frame["_source_file"] = str(path)
        frame["_source_timestamp"] = pd.Timestamp.fromtimestamp(
            path.stat().st_mtime
        )

        snapshots.append(frame)

    return snapshots


def build_schema_map(
    trading_date: str,
    snapshots,
) -> pd.DataFrame:

    rows = []

    for frame in snapshots:
        source_file = frame["_source_file"].iloc[0]

        for feature, aliases in ALIASES.items():
            physical = resolve_column(
                frame.columns,
                aliases,
            )

            rows.append(
                {
                    "trading_date": trading_date,
                    "file": source_file,
                    "feature": feature,
                    "physical_column": physical,
                    "available": bool(physical),
                }
            )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# APPROACHING EVENTS
# ---------------------------------------------------------------------------

def load_approaching():
    if not APPROACHING_CSV.exists():
        raise FileNotFoundError(
            "Authoritative approaching-breakout file not found:\n"
            f"{APPROACHING_CSV}"
        )

    return load_approaching_breakouts(
        APPROACHING_CSV
    )


def first_50_events(
    trading_date: str,
) -> pd.DataFrame:

    frame = load_approaching()

    if frame.empty:
        return frame

    required = {
        "trading_date",
        "symbol",
        "observation_timestamp",
    }

    missing = required - set(frame.columns)

    if missing:
        raise ValueError(
            "approaching_breakouts missing required columns: "
            f"{sorted(missing)}"
        )

    frame = frame.copy()

    frame["trading_date"] = (
        pd.to_datetime(
            frame["trading_date"],
            errors="coerce",
        )
        .dt.strftime("%Y-%m-%d")
    )

    frame["symbol"] = (
        frame["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    frame["observation_timestamp"] = pd.to_datetime(
        frame["observation_timestamp"],
        errors="coerce",
    )

    frame = frame[
        frame["trading_date"] == trading_date
    ].copy()

    frame = frame.dropna(
        subset=["observation_timestamp"]
    )

    frame = frame.sort_values(
        [
            "trading_date",
            "symbol",
            "observation_timestamp",
        ]
    )

    return (
        frame.drop_duplicates(
            ["trading_date", "symbol"],
            keep="first",
        )
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# EXACT/POINT-IN-TIME SNAPSHOT JOIN
# ---------------------------------------------------------------------------

def attach_snapshot_features(
    events: pd.DataFrame,
    snapshots,
) -> pd.DataFrame:

    if events.empty:
        return events

    output_rows = []

    for event in events.itertuples(index=False):
        event_ts = pd.Timestamp(
            event.observation_timestamp
        )

        symbol = str(event.symbol).upper()

        best_frame = None
        best_ts = None

        # Only use information available at or before the event.
        for frame in snapshots:
            snapshot_ts = frame[
                "_source_timestamp"
            ].iloc[0]

            if snapshot_ts > event_ts:
                continue

            if not (
                frame["Symbol"] == symbol
            ).any():
                continue

            if (
                best_ts is None
                or snapshot_ts > best_ts
            ):
                best_ts = snapshot_ts
                best_frame = frame

        row = event._asdict()

        if best_frame is None:
            row["matched_source_timestamp"] = pd.NaT
            row["matched_source_file"] = ""
            row["snapshot_lag_seconds"] = np.nan

            for feature in ALIASES:
                row[f"feature_{feature}"] = np.nan

            output_rows.append(row)
            continue

        source_row = best_frame[
            best_frame["Symbol"] == symbol
        ].iloc[0]

        row["matched_source_timestamp"] = best_ts
        row["matched_source_file"] = (
            source_row["_source_file"]
        )
        row["snapshot_lag_seconds"] = (
            event_ts - best_ts
        ).total_seconds()

        for feature, aliases in ALIASES.items():
            physical = resolve_column(
                best_frame.columns,
                aliases,
            )

            if physical is None:
                value = np.nan
            else:
                value = source_row.get(
                    physical,
                    np.nan,
                )

            row[f"feature_{feature}"] = value

        output_rows.append(row)

    return pd.DataFrame(output_rows)


# ---------------------------------------------------------------------------
# HISTORICAL REPLAY
# ---------------------------------------------------------------------------

def load_evidence(
    trading_date: str,
) -> pd.DataFrame:

    path = (
        Path(REQUIRED_EVIDENCE_DIR)
        / f"{trading_date}.csv"
    )

    if not path.exists():
        return pd.DataFrame()

    frame = pd.read_csv(path)

    if "observation_timestamp" in frame.columns:
        frame["observation_timestamp"] = pd.to_datetime(
            frame["observation_timestamp"],
            errors="coerce",
        )

    if "Symbol" in frame.columns:
        frame["Symbol"] = (
            frame["Symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    return frame


def replay_continuation(
    events: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for event in events.itertuples(index=False):
        evidence = load_evidence(
            event.trading_date
        )

        if (
            evidence.empty
            or "Symbol" not in evidence.columns
            or "observation_timestamp"
            not in evidence.columns
        ):
            rows.append(
                {
                    **event._asdict(),
                    "outcome": (
                        "missing_replay_evidence"
                    ),
                    "first_later_100_timestamp": pd.NaT,
                    "minutes_50_to_100": np.nan,
                }
            )
            continue

        symbol = str(event.symbol).upper()

        evidence = evidence[
            (evidence["Symbol"] == symbol)
            & evidence[
                "observation_timestamp"
            ].notna()
            & (
                evidence[
                    "observation_timestamp"
                ]
                >= event.observation_timestamp
            )
        ].sort_values(
            "observation_timestamp"
        )

        direction = str(
            getattr(
                event,
                "direction",
                "",
            )
        ).upper()

        if (
            direction == "UP"
            and "upside_breakout"
            in evidence.columns
        ):
            hit = (
                evidence[
                    "upside_breakout"
                ]
                .fillna(False)
                .astype(bool)
            )

        elif (
            direction == "DOWN"
            and "downside_breakout"
            in evidence.columns
        ):
            hit = (
                evidence[
                    "downside_breakout"
                ]
                .fillna(False)
                .astype(bool)
            )

        elif (
            "standard_straddle_breakout"
            in evidence.columns
        ):
            hit = (
                evidence[
                    "standard_straddle_breakout"
                ]
                .fillna(False)
                .astype(bool)
            )

        else:
            hit = pd.Series(
                False,
                index=evidence.index,
            )

        same = evidence[
            "observation_timestamp"
        ].eq(
            event.observation_timestamp
        )

        later = hit & ~same
        same_hit = hit & same

        if later.any():
            timestamp = evidence.loc[
                later,
                "observation_timestamp",
            ].iloc[0]

            outcome = (
                "continued_to_100_after_50"
            )

            minutes = (
                timestamp
                - event.observation_timestamp
            ).total_seconds() / 60

        elif same_hit.any():
            timestamp = evidence.loc[
                same_hit,
                "observation_timestamp",
            ].iloc[0]

            outcome = "same_observation_100"
            minutes = 0.0

        else:
            timestamp = pd.NaT
            outcome = (
                "unresolved_no_later_100"
            )
            minutes = np.nan

        rows.append(
            {
                **event._asdict(),
                "outcome": outcome,
                "first_later_100_timestamp": timestamp,
                "minutes_50_to_100": minutes,
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# RESEARCH ANALYSIS
# ---------------------------------------------------------------------------

def numeric_value(series):
    return pd.to_numeric(
        series,
        errors="coerce",
    )


def build_feature_effects(
    replayed: pd.DataFrame,
) -> pd.DataFrame:

    if replayed.empty:
        return pd.DataFrame()

    clean = replayed[
        replayed["outcome"].isin(
            [
                "continued_to_100_after_50",
                "unresolved_no_later_100",
            ]
        )
    ].copy()

    if clean.empty:
        return pd.DataFrame()

    clean["continued"] = (
        clean["outcome"]
        == "continued_to_100_after_50"
    ).astype(int)

    rows = []

    candidate_columns = [
        column
        for column in clean.columns
        if column.startswith("feature_")
    ]

    for column in candidate_columns:
        values = numeric_value(
            clean[column]
        )

        valid = values.notna()

        if valid.sum() < 3:
            continue

        group = clean.loc[valid].copy()
        group["_value"] = values.loc[valid]

        success = group[
            group["continued"] == 1
        ]["_value"]

        failure = group[
            group["continued"] == 0
        ]["_value"]

        if success.empty or failure.empty:
            continue

        success_mean = float(
            success.mean()
        )
        failure_mean = float(
            failure.mean()
        )

        pooled_std = float(
            group["_value"].std(
                ddof=1
            )
        )

        standardized_difference = (
            (
                success_mean
                - failure_mean
            )
            / pooled_std
            if pooled_std > 0
            else np.nan
        )

        rows.append(
            {
                "feature": column.replace(
                    "feature_",
                    "",
                    1,
                ),
                "n_valid": int(
                    valid.sum()
                ),
                "success_n": int(
                    len(success)
                ),
                "failure_n": int(
                    len(failure)
                ),
                "success_mean": success_mean,
                "failure_mean": failure_mean,
                "mean_difference": (
                    success_mean
                    - failure_mean
                ),
                "standardized_difference": (
                    standardized_difference
                ),
            }
        )

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)

    result["abs_standardized_difference"] = (
        result[
            "standardized_difference"
        ].abs()
    )

    return result.sort_values(
        "abs_standardized_difference",
        ascending=False,
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run(*dates: str):

    if not dates:
        raise SystemExit(
            "Supply one or more dates, e.g. "
            "2026-08-12 2026-08-13 2026-08-14"
        )

    RESEARCH_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_events = []
    schema_frames = []

    for date in dates:
        print(
            f"\n--- {date} ---"
        )

        snapshots = load_source_snapshots(
            date
        )

        print(
            "SOURCE SNAPSHOTS:",
            len(snapshots),
        )

        schema_frames.append(
            build_schema_map(
                date,
                snapshots,
            )
        )

        events = first_50_events(
            date
        )

        print(
            "FIRST APPROACH EVENTS:",
            len(events),
        )

        if events.empty:
            continue

        events = attach_snapshot_features(
            events,
            snapshots,
        )

        events = replay_continuation(
            events
        )

        all_events.append(events)

    if not all_events:
        raise RuntimeError(
            "No research events were produced."
        )

    result = pd.concat(
        all_events,
        ignore_index=True,
    )

    # Per-run output retains the requested date range.
    result.to_csv(
        EVENT_FILE,
        index=False,
    )

    effects = build_feature_effects(
        result
    )

    effects.to_csv(
        EFFECT_FILE,
        index=False,
    )

    if schema_frames:
        pd.concat(
            schema_frames,
            ignore_index=True,
        ).to_csv(
            SCHEMA_FILE,
            index=False,
        )

    summary = pd.DataFrame(
        [
            {
                "dates": ",".join(dates),
                "research_events": len(
                    result
                ),
                "continued_to_100": int(
                    (
                        result["outcome"]
                        == "continued_to_100_after_50"
                    ).sum()
                ),
                "same_observation_100": int(
                    (
                        result["outcome"]
                        == "same_observation_100"
                    ).sum()
                ),
                "unresolved": int(
                    (
                        result["outcome"]
                        == "unresolved_no_later_100"
                    ).sum()
                ),
                "missing_replay_evidence": int(
                    (
                        result["outcome"]
                        == "missing_replay_evidence"
                    ).sum()
                ),
                "snapshot_matched": int(
                    result[
                        "matched_source_timestamp"
                    ].notna().sum()
                ),
            }
        ]
    )

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    print(
        "\n=== RESEARCH SUMMARY ==="
    )
    print(
        summary.to_string(
            index=False
        )
    )

    print(
        "\n=== TOP CANDIDATE FACTORS ==="
    )

    if effects.empty:
        print(
            "No numeric candidate factor had enough valid observations."
        )
    else:
        print(
            effects.head(15).to_string(
                index=False
            )
        )

    print(
        "\nOUTPUT:",
        RESEARCH_ROOT,
    )
    print(
        "PRODUCTION MODIFIED: NO"
    )


if __name__ == "__main__":
    run(*sys.argv[1:])
