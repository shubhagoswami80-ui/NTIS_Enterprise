from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from config import (
    BREAKOUT_MULTIPLIER,
    CURRENT_PRICE_FIELD,
    EVENT_CSV,
    REQUIRED_EVIDENCE_DIR,
    STATE_JSON,
    STRATEGY_VERSION,
    EOD_SOURCE_ROOT,
    INTRADAY_SOURCE_ROOT,
    ensure_runtime_directories,
)

from source_loader import (
    load_primary_snapshot,
    discover_daywise_files,
    parse_observation_timestamp,
)

from approaching_breakout import save_approaching_breakouts

from storage import (
    load_events,
    append_events,
    load_state,
    save_state,
    save_daily_evidence,
)


# ---------------------------------------------------------------------------
# Opening-base helpers
# ---------------------------------------------------------------------------

def _opening_straddle(row) -> float:
    """
    Determine the opening straddle premium for the FIRST snapshot
    of a trading day.

    The Daywise source contract provides the opening Open and
    ATM Straddle %. The opening premium is always derived from those
    first-snapshot values.

    Any source ATM Straddle Price is optional evidence only and MUST
    NOT override this calculation.

    The returned value becomes the frozen per-stock daily opening
    straddle once the first snapshot is accepted.
    """

    pct = row.get("atm_straddle_pct")
    op = row.get("daily_open_reference")

    if pct is None or pd.isna(pct):
        return float("nan")

    if op is None or pd.isna(op):
        return float("nan")

    return float(op * pct / 100.0)


def _load_daily_base(
    state: dict,
    trading_date: str,
) -> dict:
    """
    Load the already-frozen opening base for one trading date.

    The base is indexed by trading date and then by symbol.
    """
    bases = state.get("daily_opening_straddles", {})
    return bases.get(trading_date, {})


def _save_daily_base(
    state: dict,
    trading_date: str,
    base_map: dict,
) -> None:
    """
    Persist the frozen opening base for one trading date.
    """
    bases = state.setdefault(
        "daily_opening_straddles",
        {},
    )

    bases[trading_date] = base_map


def _ensure_first_snapshot_base(
    df: pd.DataFrame,
    state: dict,
    trading_date: str,
    source_path: Path,
    observed_at,
) -> dict:
    """
    Establish the frozen opening base for a trading day.

    IMPORTANT:
        If a base already exists for the trading date, it is returned
        unchanged.

    Therefore a later intraday snapshot can NEVER overwrite the
    opening base.

    Each stock receives its own frozen:
        - opening price
        - opening ATM straddle %
        - opening straddle premium
        - source of opening straddle
        - source file
        - opening reference timestamp
    """

    existing = _load_daily_base(
        state,
        trading_date,
    )

    if existing:
        return existing

    base_map: dict = {}

    for _, row in df.iterrows():

        symbol = str(
            row.get("Symbol", "")
        ).strip().upper()

        if not symbol:
            continue

        open_price = row.get(
            "daily_open_reference"
        )

        if open_price is None or pd.isna(open_price):
            continue

        # Opening premium is derived exclusively from the first
        # snapshot's Open and ATM Straddle %.
        premium = _opening_straddle(row)
        straddle_source = "open_x_atm_straddle_pct"

        if pd.isna(premium):
            continue

        atm_pct = row.get(
            "atm_straddle_pct"
        )

        base_map[symbol] = {
            "open_price": float(
                open_price
            ),

            "opening_atm_straddle_pct": (
                float(atm_pct)
                if (
                    atm_pct is not None
                    and not pd.isna(atm_pct)
                )
                else None
            ),

            "opening_straddle_premium": float(
                premium
            ),

            "opening_straddle_source": (
                straddle_source
            ),

            "opening_reference_source_file": (
                str(source_path)
            ),

            "opening_reference_timestamp": (
                observed_at.isoformat()
            ),
        }

    _save_daily_base(
        state,
        trading_date,
        base_map,
    )

    return base_map


# ---------------------------------------------------------------------------
# Frozen-base application
# ---------------------------------------------------------------------------

def _apply_frozen_base(
    df: pd.DataFrame,
    base_map: dict,
) -> pd.DataFrame:
    """
    Apply the frozen daily opening base to a snapshot.

    The frozen base is authoritative for opening reference and opening
    straddle values. Current market fields remain snapshot-derived.

    The function is defensive about ``daily_open_reference`` because
    callers may provide a dataframe that has not yet passed through
    ``derive_straddle_values``.
    """
    out = df.copy()

    if "Symbol" not in out.columns:
        raise ValueError(
            "Snapshot dataframe does not contain required column: Symbol"
        )

    out["Symbol"] = (
        out["Symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Ensure a snapshot opening reference exists before using fillna.
    # derive_straddle_values normally creates this column, but the
    # frozen-base boundary must not depend on that implementation detail.
    if "daily_open_reference" not in out.columns:
        if "Open" in out.columns:
            out["daily_open_reference"] = pd.to_numeric(
                out["Open"],
                errors="coerce",
            )
        else:
            out["daily_open_reference"] = float("nan")

    premium_map = {
        key: value.get("opening_straddle_premium")
        for key, value in base_map.items()
    }

    open_map = {
        key: value.get("open_price")
        for key, value in base_map.items()
    }

    pct_map = {
        key: value.get("opening_atm_straddle_pct")
        for key, value in base_map.items()
    }

    source_map = {
        key: value.get("opening_straddle_source")
        for key, value in base_map.items()
    }

    out["opening_straddle_premium"] = (
        out["Symbol"]
        .map(premium_map)
    )

    out["daily_open_reference"] = (
        out["Symbol"]
        .map(open_map)
        .fillna(
            pd.to_numeric(
                out["daily_open_reference"],
                errors="coerce",
            )
        )
    )

    out["opening_atm_straddle_pct"] = (
        out["Symbol"]
        .map(pct_map)
    )

    out["opening_straddle_source"] = (
        out["Symbol"]
        .map(source_map)
    )

    out["upper_straddle_breakout_level"] = (
        out["daily_open_reference"]
        + (
            out["opening_straddle_premium"]
            * BREAKOUT_MULTIPLIER
        )
    )

    out["lower_straddle_breakout_level"] = (
        out["daily_open_reference"]
        - (
            out["opening_straddle_premium"]
            * BREAKOUT_MULTIPLIER
        )
    )

    out["expected_1x_price"] = (
        out["upper_straddle_breakout_level"]
    )

    out["expected_1x_move"] = (
        out["opening_straddle_premium"]
    )

    out["distance_to_1x"] = (
        out["current_price"]
        - out["daily_open_reference"]
    ).abs() - (
        out["opening_straddle_premium"]
        * BREAKOUT_MULTIPLIER
    )

    out["upside_level_touched"] = (
        out["current_price"]
        > out["upper_straddle_breakout_level"]
    )

    out["downside_level_touched"] = (
        out["current_price"]
        < out["lower_straddle_breakout_level"]
    )

    out["standard_straddle_breakout"] = (
        out["upside_level_touched"]
        | out["downside_level_touched"]
    )

    out["breakout_direction"] = "NONE"

    out.loc[
        out["upside_level_touched"],
        "breakout_direction",
    ] = "UP"

    out.loc[
        out["downside_level_touched"],
        "breakout_direction",
    ] = "DOWN"

    return out


# ---------------------------------------------------------------------------
# Event detection
# ---------------------------------------------------------------------------

def _new_events(
    df: pd.DataFrame,
    prior_events: pd.DataFrame,
    observed_at,
) -> pd.DataFrame:
    """
    Detect first breakout events while preserving previously recorded
    events.

    A symbol already recorded for the same trading date is not emitted
    again as a new event.
    """

    if (
        prior_events is None
        or prior_events.empty
    ):
        prior_keys = set()
    else:
        prior_keys = set(
            zip(
                prior_events.get(
                    "trading_date",
                    pd.Series(dtype=str),
                ).astype(str),

                prior_events.get(
                    "symbol",
                    pd.Series(dtype=str),
                )
                .astype(str)
                .str.upper(),
            )
        )

    records = []

    trading_date = (
        observed_at.date().isoformat()
    )

    for _, row in df.iterrows():

        symbol = str(
            row.get("Symbol", "")
        ).strip().upper()

        if not symbol:
            continue

        key = (
            trading_date,
            symbol,
        )

        if key in prior_keys:
            continue

        direction = row.get(
            "breakout_direction",
            "NONE",
        )

        if direction not in {
            "UP",
            "DOWN",
        }:
            continue

        current_price = row.get(
            "current_price"
        )

        open_price = row.get(
            "daily_open_reference"
        )

        premium = row.get(
            "opening_straddle_premium"
        )

        if (
            pd.isna(current_price)
            or pd.isna(open_price)
            or pd.isna(premium)
        ):
            continue

        if direction == "UP":
            expected_price = (
                open_price
                + premium
                * BREAKOUT_MULTIPLIER
            )

            breakout_distance = (
                current_price
                - expected_price
            )

        else:
            expected_price = (
                open_price
                - premium
                * BREAKOUT_MULTIPLIER
            )

            breakout_distance = (
                expected_price
                - current_price
            )

        records.append(
            {
                "trading_date": trading_date,

                "observation_timestamp":
                    observed_at.isoformat(),

                "symbol": symbol,

                "direction": direction,

                "status": "VALID_BREAKOUT",

                "open_price": open_price,

                "current_price": current_price,

                "expected_1x_price":
                    expected_price,

                "expected_1x_move":
                    premium,

                "breakout_distance":
                    breakout_distance,

                "price_chg_pct":
                    row.get(
                        "price_chg_pct"
                    ),

                "high":
                    row.get("High"),

                "low":
                    row.get("Low"),

                "atm_straddle_pct":
                    row.get(
                        "atm_straddle_pct"
                    ),

                "opening_straddle_premium":
                    premium,

                "source_atm_straddle_price":
                    row.get(
                        "source_atm_straddle_price"
                    ),

                "iv_chg_pct":
                    row.get(
                        "iv_chg_pct"
                    ),

                "oi_chg_pct":
                    row.get(
                        "oi_chg_pct"
                    ),

                "pcr_chg_pct":
                    row.get(
                        "pcr_chg_pct"
                    ),

                "ce_oi_chg_pct":
                    row.get(
                        "ce_oi_chg_pct"
                    ),

                "pe_oi_chg_pct":
                    row.get(
                        "pe_oi_chg_pct"
                    ),

                "pe_minus_ce_oi_chg":
                    row.get(
                        "pe_minus_ce_oi_chg"
                    ),

                "strategy_version":
                    STRATEGY_VERSION,
            }
        )

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Main snapshot processor
# ---------------------------------------------------------------------------

def derive_straddle_values(df: pd.DataFrame, breakout_multiplier: float = 1.0, current_price_field: str = 'Close') -> pd.DataFrame:
    out = df.copy()
    if 'Symbol' not in out.columns:
        raise ValueError('Primary snapshot does not contain required column: Symbol')
    out['Symbol'] = out['Symbol'].astype(str).str.strip().str.upper()
    if current_price_field not in out.columns:
        raise ValueError(f'Primary snapshot does not contain current price field: {current_price_field}')
    out['current_price'] = pd.to_numeric(out[current_price_field], errors='coerce')
    if 'Open' in out.columns:
        out['daily_open_reference'] = pd.to_numeric(out['Open'], errors='coerce')
    else:
        out['daily_open_reference'] = float('nan')
    if 'ATM Straddle %' in out.columns:
        out['atm_straddle_pct'] = pd.to_numeric(out['ATM Straddle %'], errors='coerce')
    else:
        out['atm_straddle_pct'] = float('nan')
    source_candidates = ['ATM Straddle Price','ATM Straddle','ATM Straddle Premium','ATM Straddle Price ()','ATM Straddle Price (Rs.)']
    source_column = next((c for c in source_candidates if c in out.columns), None)
    out['source_atm_straddle_price'] = pd.to_numeric(out[source_column], errors='coerce') if source_column else float('nan')
    mappings = {'Price Chg %':'price_chg_pct','IV Chg %':'iv_chg_pct','OI Chg %':'oi_chg_pct','PCR Chg %':'pcr_chg_pct','Tot CE OI Chg %':'ce_oi_chg_pct','Tot PE OI Chg %':'pe_oi_chg_pct','Tot PE-CE OI Chg':'pe_minus_ce_oi_chg','High':'High','Low':'Low'}
    for source,target in mappings.items():
        if source in out.columns:
            out[target] = pd.to_numeric(out[source], errors='coerce')
        elif target not in out.columns:
            out[target] = float('nan')
    return out

def process_snapshot(
    path: Path,
    timestamp=None,
):
    """
    Process one snapshot.

    FIRST snapshot of a trading day:
        establishes and freezes the per-stock daily base.

    LATER snapshots:
        reuse the already frozen daily base.

    Source files are read only and are never modified or copied.

    Phase-1 breakout:

        UP:
            Current Price > Open + Frozen Opening Straddle

        DOWN:
            Current Price < Open - Frozen Opening Straddle

    No SL, P&L, success/failure or target outcome is calculated.
    """

    ensure_runtime_directories()

    path = Path(path)

    df, observed_at = load_primary_snapshot(
        path,
        timestamp,
    )

    trading_date = (
        observed_at.date().isoformat()
    )

    state = load_state(
        STATE_JSON
    )

    # ------------------------------------------------------------------
    # First derive source/current snapshot fields.
    #
    # This is allowed to use the current snapshot because these values
    # are needed to construct the first-day base or to evaluate the
    # current observation.
    # ------------------------------------------------------------------

    df = derive_straddle_values(
        df,
        breakout_multiplier=BREAKOUT_MULTIPLIER,
        current_price_field=CURRENT_PRICE_FIELD,
    )

    # ------------------------------------------------------------------
    # Establish or load the immutable daily opening base.
    # ------------------------------------------------------------------

    base_map = _ensure_first_snapshot_base(
        df=df,
        state=state,
        trading_date=trading_date,
        source_path=path,
        observed_at=observed_at,
    )

    # ------------------------------------------------------------------
    # Apply the frozen base to the current observation.
    # ------------------------------------------------------------------

    df = _apply_frozen_base(
        df,
        base_map,
    )
    # ------------------------------------------------------------------
    # Approaching-breakout view: 50% of each stock's frozen opening
    # straddle. This is additive and does not alter breakout events.
    # ------------------------------------------------------------------
    save_approaching_breakouts(
        df,
        trading_date,
        observed_at,
        Path(EVENT_CSV).parent / "approaching_breakouts.csv",
    )

    # ------------------------------------------------------------------
    # Load existing events and detect only new breakouts.
    # ------------------------------------------------------------------

    prior_events = load_events(
        EVENT_CSV
    )

    events = _new_events(
        df,
        prior_events,
        observed_at,
    )

    # The frozen-base event calculation above is authoritative.
    # Do not fall back to a second event detector with different
    # opening-base semantics.

    append_events(
        events,
        EVENT_CSV,
    )

    # ------------------------------------------------------------------
    # Evidence persistence.
    # ------------------------------------------------------------------

    save_daily_evidence(
        df,
        trading_date,
        REQUIRED_EVIDENCE_DIR,
        observed_at,
    )

    # ------------------------------------------------------------------
    # State persistence.
    # ------------------------------------------------------------------

    state.update(
        {
            "last_source_file":
                str(path),

            "last_observation_timestamp":
                observed_at.isoformat(),

            "last_event_count":
                int(len(events)),

            "strategy_version":
                STRATEGY_VERSION,

            "breakout_rule":
                (
                    "current_price > "
                    "open + frozen_opening_straddle "
                    "OR current_price < "
                    "open - frozen_opening_straddle"
                ),

            "opening_straddle_formula":
                "first_snapshot_open_x_atm_straddle_pct",

            "current_price_field":
                CURRENT_PRICE_FIELD,

            "breakout_multiplier":
                BREAKOUT_MULTIPLIER,

            "daily_open_is_fixed_reference":
                True,

            "first_snapshot_freezes_daily_base":
                True,

            "historical_first_snapshot_required":
                True,

            "source_atm_straddle_price_required":
                False,

            "source_atm_straddle_price_role":
                "optional_evidence_only_not_authoritative",

            "opening_straddle_fallback":
                "open_x_atm_straddle_pct",

            "previous_events_preserved":
                True,

            "phase_1_replay_ready":
                True,

            "phase_2_pnl_enabled":
                False,

            "phase_2_sl_enabled":
                False,

            "eod_source_root":
                str(EOD_SOURCE_ROOT),

            "intraday_source_root":
                str(INTRADAY_SOURCE_ROOT),
        }
    )

    save_state(
        state,
        STATE_JSON,
    )

    return (
        events,
        df,
        observed_at,
    )


# ---------------------------------------------------------------------------
# Historical source discovery
# ---------------------------------------------------------------------------

def discover_historical_snapshots(
    trading_date: str | None = None,
):
    """
    Discover Daywise source files directly from the configured
    historical repository.

    Source files are never copied or modified.
    """

    return discover_daywise_files(
        INTRADAY_SOURCE_ROOT,
        trading_date,
    )


# ---------------------------------------------------------------------------
# Today's latest snapshot
# ---------------------------------------------------------------------------

def _snapshot_timestamp(path: Path):
    """Use the source filename timestamp when available; filesystem mtime only as fallback."""
    try:
        return parse_observation_timestamp(path)
    except Exception:
        return datetime.fromtimestamp(path.stat().st_mtime)


def _snapshot_sort_key(path: Path):
    return (_snapshot_timestamp(path), str(path).lower())


def process_latest_snapshot_for_today():
    """
    Process today's snapshots using source observation time ordering.

    The first VALID snapshot establishes the frozen daily base. Later
    snapshots reuse that base. Source files remain read-only.
    """
    trading_date = datetime.now().date().isoformat()
    files = list(discover_historical_snapshots(trading_date))

    if not files:
        return None, None, None, "No Daywise snapshot found for today."

    ordered = sorted((Path(p) for p in files), key=_snapshot_sort_key)
    state = load_state(STATE_JSON)
    daily_bases = state.get("daily_opening_straddles", {})

    if not daily_bases.get(trading_date):
        valid_base_snapshot = None
        skipped = []

        for candidate in ordered:
            observed_at = _snapshot_timestamp(candidate)
            try:
                candidate_df, _ = load_primary_snapshot(candidate, observed_at)
                candidate_df = derive_straddle_values(
                    candidate_df,
                    breakout_multiplier=BREAKOUT_MULTIPLIER,
                    current_price_field=CURRENT_PRICE_FIELD,
                )
                required = ("Symbol", "daily_open_reference", "current_price", "atm_straddle_pct")
                missing = [c for c in required if c not in candidate_df.columns]
                if missing:
                    skipped.append(f"{candidate.name}: missing {missing}")
                    continue
                valid_mask = (
                    candidate_df["Symbol"].astype(str).str.strip().ne("")
                    & candidate_df["daily_open_reference"].notna()
                    & candidate_df["current_price"].notna()
                    & candidate_df["atm_straddle_pct"].notna()
                )
                if int(valid_mask.sum()) <= 0:
                    skipped.append(f"{candidate.name}: no usable opening-base rows")
                    continue
                valid_base_snapshot = (candidate, observed_at)
                break
            except Exception as exc:
                skipped.append(f"{candidate.name}: {type(exc).__name__}: {exc}")

        if valid_base_snapshot is None:
            return None, None, None, "No valid opening-base snapshot is available yet."

        first, first_observed_at = valid_base_snapshot
        process_snapshot(first, first_observed_at)

    state = load_state(STATE_JSON)
    frozen_base = state.get("daily_opening_straddles", {}).get(trading_date)
    if not frozen_base:
        return None, None, None, "Unable to establish today's frozen opening base."

    latest = ordered[-1]
    latest_observed_at = _snapshot_timestamp(latest)
    base_reference_file = next(iter(frozen_base.values()), {}).get("opening_reference_source_file")

    if base_reference_file and str(latest) == str(base_reference_file):
        return latest, pd.DataFrame(), None, "First valid snapshot processed and opening base frozen; no later snapshot available."

    events, df, processed_at = process_snapshot(latest, latest_observed_at)
    return latest, events, df, "Opening base established from the first VALID snapshot; latest workbook processed using the frozen daily base."


def replay_trading_date(trading_date: str):
    """
    Rebuild one historical day from the configured Daywise source repository.

    This is a controlled replay: the selected day's SDL-owned event/evidence
    records are rebuilt from source files in chronological source timestamp
    order. Other trading dates are preserved. Source files are never modified.
    """
    trading_date = pd.Timestamp(trading_date).date().isoformat()
    files = sorted(
        (Path(p) for p in discover_historical_snapshots(trading_date)),
        key=_snapshot_sort_key,
    )
    if not files:
        return {"trading_date": trading_date, "files": 0, "events": 0, "first_timestamp": None, "last_timestamp": None}

    state = load_state(STATE_JSON)
    saved_runtime = {
        k: state.get(k)
        for k in ("last_source_file", "last_observation_timestamp", "last_event_count")
    }
    state.get("daily_opening_straddles", {}).pop(trading_date, None)
    save_state(state, STATE_JSON)

    if EVENT_CSV.exists() and EVENT_CSV.stat().st_size > 0:
        existing = load_events(EVENT_CSV)
        if not existing.empty and "trading_date" in existing.columns:
            keep = existing[existing["trading_date"].astype(str).str[:10] != trading_date].copy()
            if keep.empty:
                EVENT_CSV.unlink()
            else:
                keep.to_csv(EVENT_CSV, index=False)

    evidence_file = Path(REQUIRED_EVIDENCE_DIR) / f"{trading_date}.csv"
    if evidence_file.exists():
        evidence_file.unlink()

    total_events = 0
    first_ts = None
    last_ts = None
    for path in files:
        ts = _snapshot_timestamp(path)
        first_ts = ts if first_ts is None else min(first_ts, ts)
        last_ts = ts if last_ts is None else max(last_ts, ts)
        events, _, _ = process_snapshot(path, ts)
        total_events += int(len(events))

    state = load_state(STATE_JSON)
    for key, value in saved_runtime.items():
        if value is not None:
            state[key] = value
        else:
            state.pop(key, None)
    save_state(state, STATE_JSON)

    return {
        "trading_date": trading_date,
        "files": len(files),
        "events": total_events,
        "first_timestamp": first_ts.isoformat() if first_ts is not None else None,
        "last_timestamp": last_ts.isoformat() if last_ts is not None else None,
    }


def replay_all_available():
    """Replay every available trading day from the configured source root."""
    files = [Path(p) for p in discover_historical_snapshots()]
    dates = sorted({d for p in files for d in [pd.Timestamp(_snapshot_timestamp(p)).date().isoformat()]})
    results = [replay_trading_date(d) for d in dates]
    return results
