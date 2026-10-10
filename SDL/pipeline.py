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
    Establish and incrementally complete the frozen opening base.

    The first authoritative snapshot establishes each symbol's opening
    reference. Symbols missing an authoritative ATM Straddle Price remain
    unresolved and may be completed from the earliest later snapshot that
    supplies that value.

    Once a symbol has a valid opening straddle premium, it is frozen and
    cannot be overwritten by a later snapshot.
    """
    existing = _load_daily_base(
        state,
        trading_date,
    )

    base_map: dict = dict(existing or {})
    changed = False

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

        premium = row.get(
            "source_atm_straddle_price"
        )

        if (
            premium is None
            or pd.isna(premium)
            or float(premium) <= 0
        ):
            continue

        atm_pct = row.get(
            "atm_straddle_pct"
        )

        current = base_map.get(symbol)

        # Correct legacy BASE entries created with the obsolete
        # Open x ATM Straddle % calculation.
        if current is not None:
            current_source = str(
                current.get("opening_straddle_source", "")
            ).strip()

            if current_source == "open_x_atm_straddle_pct":
                current["opening_straddle_premium"] = float(premium)
                current["opening_straddle_source"] = (
                    "source_atm_straddle_price"
                )
                base_map[symbol] = current
                changed = True

            continue

        # Previously unresolved symbol: resolve it at the earliest
        # snapshot containing the authoritative ATM Straddle Price.
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
                "source_atm_straddle_price"
            ),

            "opening_reference_source_file": (
                str(source_path)
            ),

            "opening_reference_timestamp": (
                observed_at.isoformat()
            ),
        }

        changed = True

    if changed or not existing:
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


def process_latest_snapshot_for_today(trading_date=None):
    """
    Chronological LIVE intake for today's Daywise source repository.

    Frozen semantics:
      1. The first VALID snapshot establishes the daily frozen base.
      2. Every later VALID source observation is processed strictly in
         source-observation timestamp order.
      3. The persisted last_observation_timestamp is the LIVE checkpoint.
      4. Already-processed observations are never re-run merely because
         the dashboard is rendered again.
      5. Invalid/header-only observations are skipped and do not advance
         the checkpoint.
      6. Source workbooks remain read-only.

    This function does NOT perform dashboard candidate rendering, Futures
    evidence merging, LIVE snapshot persistence, or UI work. Those existing
    dashboard paths remain untouched.
    """
    trading_date = (pd.Timestamp(trading_date).date().isoformat() if trading_date is not None else datetime.now().date().isoformat())
    files = list(discover_historical_snapshots(trading_date))

    if not files:
        return None, None, None, "No Daywise snapshot found for today."

    ordered = sorted(
        (Path(p) for p in files),
        key=_snapshot_sort_key,
    )

    # ---------------------------------------------------------------
    # Establish the frozen BASE exactly once, from the first VALID
    # observation. This preserves the existing authoritative base rule.
    # ---------------------------------------------------------------
    state = load_state(STATE_JSON)
    daily_bases = state.get("daily_opening_straddles", {})

    if not daily_bases.get(trading_date):
        valid_base_snapshot = None
        skipped = []

        for candidate in ordered:
            observed_at = _snapshot_timestamp(candidate)
            try:
                candidate_df, _ = load_primary_snapshot(
                    candidate,
                    observed_at,
                )
                candidate_df = derive_straddle_values(
                    candidate_df,
                    breakout_multiplier=BREAKOUT_MULTIPLIER,
                    current_price_field=CURRENT_PRICE_FIELD,
                )

                required = (
                    "Symbol",
                    "daily_open_reference",
                    "current_price",
                    "atm_straddle_pct",
                )
                missing = [
                    c for c in required
                    if c not in candidate_df.columns
                ]
                if missing:
                    skipped.append(
                        f"{candidate.name}: missing {missing}"
                    )
                    continue

                valid_mask = (
                    candidate_df["Symbol"]
                    .astype(str)
                    .str.strip()
                    .ne("")
                    & candidate_df["daily_open_reference"].notna()
                    & candidate_df["current_price"].notna()
                    & candidate_df["atm_straddle_pct"].notna()
                )

                if not bool(valid_mask.any()):
                    skipped.append(
                        f"{candidate.name}: no valid observation rows"
                    )
                    continue

                valid_base_snapshot = (candidate, observed_at)
                break

            except Exception as exc:
                skipped.append(
                    f"{candidate.name}: "
                    f"{type(exc).__name__}: {exc}"
                )

        if valid_base_snapshot is None:
            return (
                None,
                None,
                None,
                "No valid opening-base snapshot is available yet.",
            )

        first, first_observed_at = valid_base_snapshot
        process_snapshot(first, first_observed_at)

    # Re-read state after BASE establishment.
    state = load_state(STATE_JSON)
    frozen_base = (
        state
        .get("daily_opening_straddles", {})
        .get(trading_date)
    )
    if not frozen_base:
        return (
            None,
            None,
            None,
            "Unable to establish today's frozen opening base.",
        )

    # ---------------------------------------------------------------
    # LIVE checkpoint.
    #
    # The BASE timestamp is the minimum safe checkpoint when state is
    # missing/stale for another trading date. This prevents reprocessing
    # the immutable BASE while still guaranteeing every later observation
    # is caught up.
    # ---------------------------------------------------------------
    checkpoint_raw = state.get("last_observation_timestamp")
    checkpoint = (
        pd.to_datetime(checkpoint_raw, errors="coerce")
        if checkpoint_raw
        else pd.NaT
    )

    base_entry = next(iter(frozen_base.values()), {})
    base_ts = pd.to_datetime(
        base_entry.get("opening_reference_timestamp"),
        errors="coerce",
    )

    if pd.isna(base_ts):
        base_reference_file = base_entry.get(
            "opening_reference_source_file"
        )
        if base_reference_file:
            try:
                base_ts = _snapshot_timestamp(
                    Path(base_reference_file)
                )
            except Exception:
                base_ts = pd.NaT

    if pd.isna(checkpoint):
        checkpoint = base_ts
    elif checkpoint.date().isoformat() != trading_date:
        checkpoint = base_ts
    elif pd.notna(base_ts) and checkpoint < base_ts:
        checkpoint = base_ts

    # ---------------------------------------------------------------
    # Build ONLY the observations newer than the persisted checkpoint.
    # They are processed strictly chronologically.
    # ---------------------------------------------------------------
    pending = []

    for candidate in ordered:
        candidate_ts = _snapshot_timestamp(candidate)
        if pd.isna(candidate_ts):
            continue

        if pd.notna(checkpoint) and candidate_ts <= checkpoint:
            continue

        # Do not advance LIVE on header-only/incomplete workbooks.
        # Reuse the same validity contract used for BASE selection.
        try:
            candidate_df, _ = load_primary_snapshot(
                candidate,
                candidate_ts,
            )
            candidate_df = derive_straddle_values(
                candidate_df,
                breakout_multiplier=BREAKOUT_MULTIPLIER,
                current_price_field=CURRENT_PRICE_FIELD,
            )

            required = (
                "Symbol",
                "daily_open_reference",
                "current_price",
                "atm_straddle_pct",
            )
            if any(c not in candidate_df.columns for c in required):
                continue

            valid_mask = (
                candidate_df["Symbol"]
                .astype(str)
                .str.strip()
                .ne("")
                & candidate_df["daily_open_reference"].notna()
                & candidate_df["current_price"].notna()
                & candidate_df["atm_straddle_pct"].notna()
            )
            if not bool(valid_mask.any()):
                continue

            pending.append((candidate_ts, candidate))

        except Exception:
            # A source point that is not yet valid must not advance the
            # checkpoint or prevent later valid points from being seen.
            continue

    if not pending:
        latest = ordered[-1]
        latest_ts = _snapshot_timestamp(latest)
        return (
            latest,
            pd.DataFrame(),
            latest_ts,
            "No new valid Daywise observation after the persisted LIVE checkpoint.",
        )

    last_path = None
    last_events = pd.DataFrame()
    last_df = pd.DataFrame()
    last_ts = pd.NaT

    for next_ts, next_path in pending:
        # process_snapshot() persists last_observation_timestamp only after
        # the complete observation has been processed. Therefore a failure
        # cannot silently advance the LIVE checkpoint.
        next_events, next_df, processed_at = process_snapshot(
            next_path,
            next_ts,
        )

        last_path = next_path
        last_events = next_events
        last_df = next_df
        last_ts = processed_at

    return (
        last_path,
        last_events,
        last_df,
        (
            f"Chronological LIVE catch-up complete: processed "
            f"{len(pending)} new valid Daywise observation(s) "
            f"from the first unprocessed point through "
            f"{last_ts.isoformat() if pd.notna(last_ts) else 'latest'}."
        ),
    )


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
