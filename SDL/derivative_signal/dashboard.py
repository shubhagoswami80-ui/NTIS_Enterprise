from __future__ import annotations

from datetime import date, datetime
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from config import INTRADAY_SOURCE_ROOT
from derivative_signal.source_loader import (
    discover_daywise_files,
    parse_observation_timestamp,
    read_source,
)
from storage import load_state, save_state
from derivative_signal.signal_engine import build_signal
from decision_evidence import merge_evidence, enrich_decision

STATE_KEY = "derivative_signal"
STATE_JSON = Path(__file__).resolve().parent / "data" / "output" / "state" / "processing_state.json"

CONFIRMED_STATES = {
    "STRONG_BULLISH",
    "STRONG_BEARISH",
    "STRONG_NEAR_LEVEL",
    "ACTIVE_BULLISH",
    "ACTIVE_BEARISH",
    "WAIT_BREAK_CONFIRMATION",
}
DEVELOPING_STATES = {"DEVELOPING_BULLISH", "DEVELOPING_BEARISH"}
QUALIFIED_STATES = CONFIRMED_STATES | DEVELOPING_STATES

# NSE regular cash-market session. LIVE auto-processing is active only while
# the session is open; after close the dashboard preserves the last complete
# processed intraday decision snapshot as the final session state.
MARKET_OPEN_TIME = (9, 15)
MARKET_CLOSE_TIME = (15, 30)

def _market_session_status(trading_date: str) -> tuple[bool, bool]:
    """Return (is_market_day, is_market_open) using the selected trading date.

    This intentionally uses the selected trading date and local machine time.
    The source discovery layer remains the authority for whether snapshots
    actually exist; this helper only controls LIVE auto-refresh behavior.
    """
    try:
        selected = datetime.strptime(trading_date, "%Y-%m-%d").date()
    except ValueError:
        return True, False
    now = datetime.now()
    if selected != now.date():
        return True, False
    current = (now.hour, now.minute)
    return True, MARKET_OPEN_TIME <= current < MARKET_CLOSE_TIME


def _live_session_key(trading_date: str) -> str:
    return f"ds_live_session::{trading_date}"


# ---------------------------------------------------------------------------
# Source / replay layer
# ---------------------------------------------------------------------------

def _discover_sources(trading_date: str, source_root: Path | None = None) -> list[Path]:
    root = Path(source_root or INTRADAY_SOURCE_ROOT).expanduser()
    files = discover_daywise_files(root, trading_date)
    return sorted(
        [Path(p) for p in files if Path(p).is_file()],
        key=lambda p: (
            parse_observation_timestamp(p),
            p.stat().st_mtime,
            p.name.lower(),
        ),
    )


def _read(path: Path) -> pd.DataFrame:
    df = read_source(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _previous(state: dict[str, Any], trading_date: str) -> dict[str, dict]:
    return (
        state.get(STATE_KEY, {})
        .get(trading_date, {})
        .get("previous_snapshot", {})
        or {}
    )


def _snapshot_rows(df: pd.DataFrame) -> dict[str, dict]:
    keep = [
        "Symbol", "symbol",
        "Open", "open", "High", "high", "Low", "low",
        "Close", "close",
        "Price Chg %", "price_chg_pct",
        "OI Chg %", "oi_chg_pct",
        "Tot PE-CE OI Chg", "pe_ce_oi_chg",
        "PCR Chg %", "pcr_chg_pct",
        "IV Chg %", "iv_chg_pct",
        "Volume Chg %", "volume_chg_pct",
        "ATM Straddle %", "atm_straddle_pct",
        "Support", "support", "Resistance", "resistance",
        "Futures Buildup", "fut_buildup",
        "Futures OI Chg %", "fut_oi_chg_pct",
    ]
    rows: dict[str, dict] = {}
    for record in df.to_dict(orient="records"):
        symbol = str(
            record.get("Symbol", record.get("symbol", ""))
        ).strip().upper()
        if symbol:
            rows[symbol] = {
                k: record.get(k)
                for k in keep
                if k in record
            }
    return rows


def _first_range_from_path(
    path: Path, trading_date: str
) -> dict[str, dict[str, Any]]:
    try:
        files = _discover_sources(trading_date, path.parent)
        if not files:
            return {}

        first = files[0]
        df = _read(first)
        symbol_col = next(
            (c for c in ("Symbol", "symbol") if c in df.columns),
            None,
        )
        high_col = next(
            (c for c in ("High", "high") if c in df.columns),
            None,
        )
        low_col = next(
            (c for c in ("Low", "low") if c in df.columns),
            None,
        )

        if not symbol_col or not high_col or not low_col:
            return {}

        result: dict[str, dict[str, Any]] = {}
        for rec in df.to_dict(orient="records"):
            symbol = str(rec.get(symbol_col, "")).strip().upper()
            if not symbol:
                continue
            try:
                high = float(rec.get(high_col))
                low = float(rec.get(low_col))
            except (TypeError, ValueError):
                continue
            if pd.isna(high) or pd.isna(low):
                continue

            result[symbol] = {
                "first_snapshot_high": high,
                "first_snapshot_low": low,
                "first_snapshot_path": str(first),
                "first_snapshot_timestamp": parse_observation_timestamp(first),
            }
        return result
    except Exception:
        return {}


def _process_snapshot(
    path: Path,
    trading_date: str,
    previous: dict[str, dict],
    first_range: dict[str, Any] | None = None,
) -> pd.DataFrame:
    df, source_map = merge_evidence(path, trading_date)
    rows = []

    for record in df.to_dict(orient="records"):
        symbol = str(
            record.get("symbol", record.get("Symbol", ""))
        ).strip().upper()
        if not symbol:
            continue

        signal = build_signal(record, previous.get(symbol))
        signal["source_evidence"] = source_map
        rows.append(
            enrich_decision(
                signal,
                record,
                context=first_range or {},
            )
        )

    return pd.DataFrame(rows)


def _attach_snapshot_metadata(result: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Attach immutable source timing/identity to the current result."""
    if result.empty:
        return result
    out = result.copy()
    observed = parse_observation_timestamp(path)
    out["observation_timestamp"] = observed.strftime("%Y-%m-%d %H:%M:%S")
    out["source_timestamp"] = observed
    out["source_file"] = path.name
    return out


def process_selected_source(path: Path, trading_date: str) -> pd.DataFrame:
    state = load_state(STATE_JSON)
    sources = _discover_sources(trading_date, path.parent)

    # The first snapshot is BASE ONLY. It establishes the opening reference
    # and must never create a decision row.
    is_first_snapshot = (
        bool(sources)
        and Path(sources[0]).resolve() == Path(path).resolve()
    )

    result = (
        pd.DataFrame()
        if is_first_snapshot
        else _process_snapshot(
            path,
            trading_date,
            _previous(state, trading_date),
            _first_range_from_path(path, trading_date),
        )
    )
    result = _attach_snapshot_metadata(result, path)

    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    decision_rows = (
        result.to_dict(orient="records")
        if not result.empty
        else []
    )
    candidate_rows = [
        row
        for row in decision_rows
        if str(row.get("decision_state", "")).upper()
        in QUALIFIED_STATES
    ]

    day["previous_snapshot"] = _snapshot_rows(_read(path))
    day["decision_snapshot"] = {
        str(row.get("symbol", "")).upper(): row
        for row in decision_rows
        if str(row.get("symbol", "")).strip()
    }
    day["candidate_snapshot"] = {
        str(row.get("symbol", "")).upper(): row
        for row in candidate_rows
        if str(row.get("symbol", "")).strip()
    }
    day["source_file"] = str(path)
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)

    return result


def process_all_sources(
    paths: list[Path],
    trading_date: str,
    capture_snapshots: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame] | None]:
    state = load_state(STATE_JSON)
    previous: dict[str, dict] = {}
    previous_state: dict[str, str] = {}
    previous_direction: dict[str, str] = {}
    timeline_rows: list[dict[str, Any]] = []
    latest_result = pd.DataFrame()
    snapshot_results: dict[str, pd.DataFrame] = {}
    latest_valid_path: Path | None = None

    ordered = sorted(
        [Path(p) for p in paths if Path(p).is_file()],
        key=lambda p: (
            parse_observation_timestamp(p),
            p.stat().st_mtime,
            p.name.lower(),
        ),
    )

    first_range = (
        _first_range_from_path(ordered[0], trading_date)
        if ordered
        else {}
    )

    for sequence, path in enumerate(ordered, start=1):
        if sequence == 1:
            previous = _snapshot_rows(_read(path))
            continue

        result = _process_snapshot(
            path,
            trading_date,
            previous,
            first_range,
        )
        result = _attach_snapshot_metadata(result, path)
        timestamp = parse_observation_timestamp(path)

        # A malformed/temporarily incomplete snapshot must not erase the
        # last valid decision result. It is still part of the chronological
        # chain, so its raw rows become the previous snapshot for the next
        # batch item.
        if result.empty:
            if capture_snapshots:
                snapshot_results[_source_key(path)] = result
            previous = _snapshot_rows(_read(path))
            continue

        for row in result.to_dict(orient="records"):
            symbol = str(row.get("symbol", "")).upper()
            state_name = str(
                row.get("decision_state", row.get("state", "WATCH"))
            ).upper()
            direction = str(
                row.get("decision_direction", row.get("direction", "NEUTRAL"))
            ).upper()

            old_state = previous_state.get(symbol)
            old_direction = previous_direction.get(symbol)

            state_changed = state_name != old_state
            direction_changed = (
                old_direction is not None
                and direction not in {"", "NEUTRAL"}
                and old_direction not in {"", "NEUTRAL"}
                and direction != old_direction
            )

            if (
                (state_changed or direction_changed)
                and state_name in QUALIFIED_STATES
            ):
                timeline_rows.append(
                    {
                        "Time": timestamp.strftime("%H:%M:%S"),
                        "Snapshot": sequence,
                        "Symbol": symbol,
                        "Decision": row.get(
                            "decision_state",
                            "NO DECISION",
                        ),
                        "Direction": direction,
                        "Previous": (
                            old_direction
                            if direction_changed
                            else old_state or "—"
                        ),
                        "Evidence": row.get(
                            "decision_score",
                            0,
                        ),
                        "Strength": row.get(
                            "decision_strength",
                            "—",
                        ),
                        "S/R": row.get(
                            "sr_status",
                            "—",
                        ),
                    }
                )

            previous_state[symbol] = state_name
            previous_direction[symbol] = direction

        previous = _snapshot_rows(_read(path))
        latest_result = result
        latest_valid_path = path
        if capture_snapshots:
            snapshot_results[_source_key(path)] = result

    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    decision_rows = (
        latest_result.to_dict(orient="records")
        if not latest_result.empty
        else []
    )
    candidate_rows = [
        row
        for row in decision_rows
        if str(row.get("decision_state", "")).upper()
        in QUALIFIED_STATES
    ]

    day["previous_snapshot"] = previous
    day["decision_snapshot"] = {
        str(row.get("symbol", "")).upper(): row
        for row in decision_rows
        if str(row.get("symbol", "")).strip()
    }
    day["candidate_snapshot"] = {
        str(row.get("symbol", "")).upper(): row
        for row in candidate_rows
        if str(row.get("symbol", "")).strip()
    }
    day["source_file"] = (
        str(latest_valid_path)
        if latest_valid_path is not None
        else ""
    )
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)

    return latest_result, pd.DataFrame(timeline_rows), (snapshot_results if capture_snapshots else None)


# ---------------------------------------------------------------------------
# Live / snapshot cache helpers
# ---------------------------------------------------------------------------

def _source_key(path: Path) -> str:
    return str(Path(path).resolve())


def _cache_key(trading_date: str) -> str:
    return f"ds_snapshot_cache::{trading_date}"


def _store_replay_cache(
    trading_date: str,
    snapshot_results: dict[str, pd.DataFrame],
    timeline: pd.DataFrame,
) -> None:
    st.session_state[_cache_key(trading_date)] = {
        "snapshots": snapshot_results,
        "timeline": timeline,
    }


def _get_replay_cache(trading_date: str) -> dict[str, Any]:
    value = st.session_state.get(_cache_key(trading_date))
    return value if isinstance(value, dict) else {}


def _process_and_cache_day(
    sources: list[Path],
    trading_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    latest, timeline, snapshots = process_all_sources(
        sources,
        trading_date,
        capture_snapshots=True,
    )
    _store_replay_cache(trading_date, snapshots, timeline)
    if latest is not None and not latest.empty and sources:
        _persist_last_complete_state(
            trading_date,
            latest,
            timeline,
            sources[-1],
        )
    return latest, timeline, snapshots


def _auto_process_new_snapshots(
    sources: list[Path],
    trading_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """Process only snapshots not already consumed by the live session/state.

    The first live load establishes the BASE + chronological chain once.
    Subsequent live updates consume only newly arrived files, preserving the
    existing previous-snapshot state and decision evidence.
    """
    cache = _get_replay_cache(trading_date)
    cached_snapshots = cache.get("snapshots", {})
    if not isinstance(cached_snapshots, dict):
        cached_snapshots = {}

    known = set(cached_snapshots.keys())
    source_keys = {_source_key(p) for p in sources}

    # If the session has no cache, initialize the complete currently available
    # chain once. This is required to establish the BASE snapshot correctly.
    if not known or not known.intersection(source_keys):
        latest, timeline, _ = _process_and_cache_day(sources, trading_date)
        return latest, timeline, True

    new_paths = [p for p in sources if _source_key(p) not in known]
    if not new_paths:
        latest_key = _source_key(sources[-1]) if sources else ""
        latest = cached_snapshots.get(latest_key, pd.DataFrame())
        return latest, cache.get("timeline", pd.DataFrame()), False

    # Process only the new tail, in chronological order. The processing-state
    # file already contains the previous raw snapshot and current decision
    # snapshot needed to continue the chain.
    state = load_state(STATE_JSON)
    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    previous = day.get("previous_snapshot", {}) or {}
    previous_state = {
        str(k).upper(): str(v.get("decision_state", "")).upper()
        for k, v in (day.get("decision_snapshot", {}) or {}).items()
        if isinstance(v, dict)
    }
    previous_direction = {
        str(k).upper(): str(
            v.get("decision_direction", v.get("direction", "NEUTRAL"))
        ).upper()
        for k, v in (day.get("decision_snapshot", {}) or {}).items()
        if isinstance(v, dict)
    }

    first_range = _first_range_from_path(sources[0], trading_date) if sources else {}
    timeline_rows = cache.get("timeline", pd.DataFrame()).to_dict(orient="records") if isinstance(cache.get("timeline"), pd.DataFrame) else []
    latest_result = pd.DataFrame()

    for path in new_paths:
        result = _process_snapshot(path, trading_date, previous, first_range)
        result = _attach_snapshot_metadata(result, path)
        timestamp = parse_observation_timestamp(path)
        if result.empty:
            previous = _snapshot_rows(_read(path))
            continue

        for row in result.to_dict(orient="records"):
            symbol = str(row.get("symbol", "")).upper()
            state_name = str(row.get("decision_state", row.get("state", "WATCH"))).upper()
            direction = str(row.get("decision_direction", row.get("direction", "NEUTRAL"))).upper()
            old_state = previous_state.get(symbol)
            old_direction = previous_direction.get(symbol)
            state_changed = state_name != old_state
            direction_changed = (
                old_direction is not None
                and direction not in {"", "NEUTRAL"}
                and old_direction not in {"", "NEUTRAL"}
                and direction != old_direction
            )
            if (state_changed or direction_changed) and state_name in QUALIFIED_STATES:
                timeline_rows.append({
                    "Time": timestamp.strftime("%H:%M:%S"),
                    "Snapshot": len(cached_snapshots) + 1,
                    "Symbol": symbol,
                    "Decision": row.get("decision_state", "NO DECISION"),
                    "Direction": direction,
                    "Previous": old_direction if direction_changed else old_state or "—",
                    "Evidence": row.get("decision_score", 0),
                    "Strength": row.get("decision_strength", "—"),
                    "S/R": row.get("sr_status", "—"),
                })
            previous_state[symbol] = state_name
            previous_direction[symbol] = direction

        previous = _snapshot_rows(_read(path))
        latest_result = result
        cached_snapshots[_source_key(path)] = result
        day["previous_snapshot"] = previous
        day["decision_snapshot"] = {
            str(row.get("symbol", "")).upper(): row
            for row in result.to_dict(orient="records")
            if str(row.get("symbol", "")).strip()
        }
        day["source_file"] = str(path)
        day["processed_at"] = datetime.now().isoformat()
        state.setdefault(STATE_KEY, {})[trading_date] = day
        save_state(state, STATE_JSON)
        _persist_last_complete_state(
            trading_date,
            latest_result,
            pd.DataFrame(timeline_rows),
            path,
        )

    timeline = pd.DataFrame(timeline_rows)
    _store_replay_cache(trading_date, cached_snapshots, timeline)
    return latest_result, timeline, True


# ---------------------------------------------------------------------------
# Candidate filtering
#
# IMPORTANT:
# The decision engine can legitimately evaluate all 217 symbols. That does
# NOT mean all 217 belong on the decision dashboard.
#
# The dashboard candidate pool is deliberately narrower:
#   1. NO DECISION is never displayed in the main decision pool.
#   2. A confirmed/active state must have passed the price gate.
#   3. WAIT_BREAK_CONFIRMATION is shown only when evidence is meaningful.
#   4. DEVELOPING is shown only when the evidence score reaches the
#      developing threshold and there is real confluence.
#   5. Conflicted rows are suppressed from the primary decision pool when
#      opposite evidence is material.
#
# This is a DISPLAY/ENTRY-SAFETY filter. It does not alter the underlying
# 217-row calculation result or stored evidence.
# ---------------------------------------------------------------------------

def _num(v: Any) -> float | None:
    try:
        if v is None or pd.isna(v) or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {
        "true", "1", "yes", "y", "passed"
    }


def _candidate_reason(row: pd.Series) -> str:
    state = str(row.get("decision_state", "")).upper()
    score = _num(row.get("decision_score")) or 0
    conflicts = int(_num(row.get("conflict_count")) or 0)
    confirmations = int(
        _num(row.get("confirmation_count")) or 0
    )

    if state in {"STRONG_BULLISH", "STRONG_BEARISH"}:
        return "Confirmed strong decision"
    if state in {"ACTIVE_BULLISH", "ACTIVE_BEARISH"}:
        return "Actionability gate passed"
    if state == "WAIT_BREAK_CONFIRMATION":
        return "Relevant S/R break setup"
    if state in DEVELOPING_STATES:
        return (
            f"Developing evidence {score:.0f}/100 "
            f"with {confirmations} confirmations"
        )
    return ""


def _candidate_mask(result: pd.DataFrame) -> pd.Series:
    """Promote only relevant post-primary-gate decision states.

    This restores the previously established state-based selection model:
      * confirmed/active: directional price gate passed
      * developing: engine already classified the row as DEVELOPING
      * wait-break: engine already classified the row as WAIT_BREAK
      * no arbitrary extra score/confirmation floor is imposed here

    The finalized +/-0.75% primary price gate remains an absolute boundary
    for every state in the live dashboard.
    """
    if result.empty:
        return pd.Series(False, index=result.index, dtype=bool)

    state = (
        result.get(
            "decision_state",
            pd.Series("", index=result.index),
        )
        .astype(str)
        .str.upper()
        .str.strip()
    )

    direction = (
        result.get(
            "decision_direction",
            result.get(
                "direction",
                pd.Series("NEUTRAL", index=result.index),
            ),
        )
        .astype(str)
        .str.upper()
        .str.strip()
    )

    price = pd.to_numeric(
        result.get(
            "price_change_pct",
            pd.Series(0, index=result.index),
        ),
        errors="coerce",
    ).fillna(0)

    conflicts = pd.to_numeric(
        result.get(
            "conflict_count",
            pd.Series(0, index=result.index),
        ),
        errors="coerce",
    ).fillna(0)

    # HARD PRIMARY GATE. No developing/wait/actionable state may bypass it.
    gate = result.get(
        "gate_passed",
        pd.Series(False, index=result.index),
    ).map(_bool).fillna(False)

    # Preserve the existing actionable rule: direction must agree with the
    # +/-0.75% move and material conflicts do not enter the primary board.
    confirmed = (
        (
            (direction == "BULLISH") & (price >= 0.75)
        )
        | (
            (direction == "BEARISH") & (price <= -0.75)
        )
    )

    actionable = state.isin({
        "STRONG_BULLISH",
        "STRONG_BEARISH",
        "ACTIVE_BULLISH",
        "ACTIVE_BEARISH",
    }) & confirmed & (conflicts == 0)

    # These states are already produced by the underlying evidence engine.
    # Their state classification is the evidence/relevance decision; do not
    # add an artificial confirmation-count floor at dashboard level.
    developing = state.isin(DEVELOPING_STATES)
    wait_break = state.eq("WAIT_BREAK_CONFIRMATION")

    relevant = actionable | developing | wait_break

    # Absolute gate is applied to ALL three branches.
    return gate & relevant & (conflicts <= 1)

def _rank(result: pd.DataFrame) -> pd.DataFrame:
    if result.empty:
        return result.copy()

    out = result.copy()
    mask = _candidate_mask(out)
    out = out.loc[mask].copy()

    if out.empty:
        return out

    decision = out.get(
        "decision_direction",
        out.get(
            "direction",
            pd.Series("NEUTRAL", index=out.index),
        ),
    ).astype(str).str.upper()

    price = pd.to_numeric(
        out.get(
            "price_change_pct",
            pd.Series(0, index=out.index),
        ),
        errors="coerce",
    ).fillna(0)

    state = out.get(
        "decision_state",
        pd.Series("", index=out.index),
    ).astype(str).str.upper()

    score = pd.to_numeric(
        out.get(
            "decision_score",
            pd.Series(0, index=out.index),
        ),
        errors="coerce",
    ).fillna(0)

    sr = out.get(
        "sr_status",
        pd.Series("", index=out.index),
    ).astype(str).str.upper()

    sr_rank = sr.map(
        {
            "RESISTANCE BROKEN": 50,
            "SUPPORT BROKEN": 50,
            "RESISTANCE TEST": 40,
            "SUPPORT TEST": 40,
            "APPROACHING RESISTANCE": 30,
            "APPROACHING SUPPORT": 30,
            "AT_RESISTANCE": 30,
            "AT_SUPPORT": 30,
        }
    ).fillna(0)

    state_rank = state.map(
        {
            "STRONG_BULLISH": 50,
            "STRONG_BEARISH": 50,
            "ACTIVE_BULLISH": 42,
            "ACTIVE_BEARISH": 42,
            "WAIT_BREAK_CONFIRMATION": 38,
            "DEVELOPING_BULLISH": 28,
            "DEVELOPING_BEARISH": 28,
        }
    ).fillna(0)

    quality_rank = (
        out.get(
            "decision_quality",
            pd.Series("", index=out.index),
        )
        .astype(str)
        .map(
            {
                "HIGH": 18,
                "MEDIUM": 10,
                "LOW": 0,
            }
        )
        .fillna(0)
    )

    confirmations = pd.to_numeric(
        out.get(
            "confirmation_count",
            pd.Series(0, index=out.index),
        ),
        errors="coerce",
    ).fillna(0)

    conflicts = pd.to_numeric(
        out.get(
            "conflict_count",
            pd.Series(0, index=out.index),
        ),
        errors="coerce",
    ).fillna(0)

    out["_decision_priority"] = (
        state_rank
        + sr_rank
        + quality_rank
        + score * 0.55
        + confirmations * 3
        - conflicts * 12
        + price.abs() * 2
    )
    out["_price_abs"] = price.abs()
    out["_candidate_reason"] = out.apply(
        _candidate_reason,
        axis=1,
    )

    return out.sort_values(
        [
            "_decision_priority",
            "_price_abs",
            "symbol",
        ],
        ascending=[False, False, True],
        na_position="last",
    )


# ---------------------------------------------------------------------------
# Dashboard UI
# ---------------------------------------------------------------------------

def _phase(row: pd.Series) -> str:
    state = str(row.get("decision_state", "")).upper()
    if state.startswith("DEVELOPING"):
        return "DEVELOPING"
    if state in {
        "STRONG_BULLISH",
        "ACTIVE_BULLISH",
        "STRONG_BEARISH",
        "ACTIVE_BEARISH",
    }:
        return "CONFIRMED"
    if state == "STRONG_NEAR_LEVEL":
        return "NEAR LEVEL"
    if state == "WAIT_BREAK_CONFIRMATION":
        return "WAIT BREAK"
    return state or "NO DECISION"


def _sr_text(row: pd.Series) -> str:
    return str(row.get("sr_status", "—")).replace("_", " ")


def _css() -> None:
    st.markdown(
        """
<style>
.block-container{max-width:1500px;padding-top:1rem;padding-bottom:2rem}
.hero{
    padding:20px 26px;
    border-radius:14px;
    background:#172554;
    color:#fff;
    margin-bottom:14px
}
.hero-title{font-size:28px;font-weight:800}
.hero-sub{font-size:12px;opacity:.86;margin-top:4px}

.metricbar{
    border:1px solid #e2e8f0;
    border-radius:12px;
    padding:12px 14px;
    background:#fff
}
.metric-label{font-size:11px;color:#64748b;text-transform:uppercase}
.metric-value{font-size:25px;font-weight:800;color:#0f172a}
.metric-green{color:#15803d}.metric-red{color:#dc2626}.metric-amber{color:#b45309}

.section{
    margin-top:18px;
    margin-bottom:8px;
    font-size:19px;
    font-weight:800
}
.section-bull{color:#15803d}
.section-bear{color:#dc2626}
.section-dev{color:#b45309}

.snapshot{
    font-size:12px;
    color:#475569;
    background:#f8fafc;
    border:1px solid #e2e8f0;
    padding:8px 12px;
    border-radius:8px;
    margin-bottom:12px
}

.badge{
    display:inline-block;
    padding:4px 8px;
    border-radius:7px;
    font-size:11px;
    font-weight:800
}
.badge-bull{color:#166534;background:#dcfce7}
.badge-bear{color:#991b1b;background:#fee2e2}
.badge-dev{color:#92400e;background:#fef3c7}
.badge-wait{color:#3730a3;background:#e0e7ff}

.note{
    font-size:11px;
    color:#64748b;
    margin-top:5px
}
</style>
""",
        unsafe_allow_html=True,
    )


def _state_badge(state: str) -> str:
    state = str(state).upper()
    if "BULLISH" in state:
        cls = "badge-bull"
    elif "BEARISH" in state:
        cls = "badge-bear"
    elif state == "WAIT_BREAK_CONFIRMATION":
        cls = "badge-wait"
    else:
        cls = "badge-dev"
    return f'<span class="badge {cls}">{state.replace("_", " ")}</span>'


def _render_summary(result: pd.DataFrame, candidates: pd.DataFrame) -> None:
    total = len(result)
    visible = len(candidates)

    bullish = int(
        candidates.get(
            "decision_direction",
            pd.Series(dtype=str),
        ).astype(str).str.upper().eq("BULLISH").sum()
    )
    bearish = int(
        candidates.get(
            "decision_direction",
            pd.Series(dtype=str),
        ).astype(str).str.upper().eq("BEARISH").sum()
    )
    developing = int(
        candidates.get(
            "decision_state",
            pd.Series(dtype=str),
        ).astype(str).str.upper().str.startswith("DEVELOPING").sum()
    )
    wait_break = int(
        candidates.get(
            "decision_state",
            pd.Series(dtype=str),
        ).astype(str).str.upper().eq("WAIT_BREAK_CONFIRMATION").sum()
    )

    cols = st.columns(6)
    values = [
        ("EVALUATED", total, ""),
        ("DECISION POOL", visible, ""),
        ("BULLISH", bullish, "metric-green"),
        ("BEARISH", bearish, "metric-red"),
        ("DEVELOPING", developing, "metric-amber"),
        ("WAIT BREAK", wait_break, "metric-amber"),
    ]

    for col, (label, value, cls) in zip(cols, values):
        with col:
            st.markdown(
                f"""
<div class="metricbar">
  <div class="metric-label">{label}</div>
  <div class="metric-value {cls}">{value}</div>
</div>
""",
                unsafe_allow_html=True,
            )


def _render_table(candidates: pd.DataFrame) -> None:
    if candidates.empty:
        st.info(
            "No stock currently meets the primary decision-visibility "
            "criteria. The underlying calculation remains available."
        )
        return

    table = pd.DataFrame(
        {
            "Rank": range(1, len(candidates) + 1),
            "Stock": candidates["symbol"].astype(str),
            "Direction": candidates.get(
                "decision_direction",
                pd.Series("NEUTRAL", index=candidates.index),
            ).astype(str),
            "State": candidates.get(
                "decision_state",
                pd.Series("", index=candidates.index),
            ).astype(str),
            "Time": candidates.get(
                "observation_timestamp",
                pd.Series("", index=candidates.index),
            ).astype(str),
            "S/R": candidates.apply(_sr_text, axis=1),
            "Evidence": pd.to_numeric(
                candidates.get(
                    "decision_score",
                    pd.Series(0, index=candidates.index),
                ),
                errors="coerce",
            ).round(0),
            "Confirm": pd.to_numeric(
                candidates.get(
                    "confirmation_count",
                    pd.Series(0, index=candidates.index),
                ),
                errors="coerce",
            ).round(0),
            "Conflict": pd.to_numeric(
                candidates.get(
                    "conflict_count",
                    pd.Series(0, index=candidates.index),
                ),
                errors="coerce",
            ).round(0),
            "Move %": pd.to_numeric(
                candidates.get(
                    "price_change_pct",
                    pd.Series(0, index=candidates.index),
                ),
                errors="coerce",
            ).round(2),
            "Reason": candidates.get(
                "decision_reason",
                pd.Series("—", index=candidates.index),
            ).astype(str),
        }
    )

    def color_state(value: Any) -> str:
        s = str(value).upper()
        if "BULLISH" in s:
            return "color:#15803d;font-weight:800"
        if "BEARISH" in s:
            return "color:#dc2626;font-weight:800"
        if "WAIT" in s:
            return "color:#3730a3;font-weight:800"
        return "color:#b45309;font-weight:800"

    styled = table.style.map(
        color_state,
        subset=["Direction", "State"],
    )
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
    )


def _render_evidence(row: pd.Series) -> None:
    st.subheader(f"Decision Evidence — {row['symbol']}")

    cols = st.columns(6)
    items = [
        ("Time", row.get("observation_timestamp", "—")),
        ("Evidence", row.get("decision_score", "—")),
        ("Strength", row.get("decision_strength", "—")),
        ("Confirm", row.get("confirmation_count", "—")),
        ("Conflict", row.get("conflict_count", "—")),
        ("S/R", _sr_text(row)),
    ]

    for col, (label, value) in zip(cols, items):
        with col:
            st.metric(label, str(value))

    with st.expander("Detailed evidence", expanded=False):
        evidence = pd.DataFrame(
            {
                "Evidence": [
                    "Decision",
                    "Price/Direction",
                    "First Range",
                    "Futures",
                    "PE-CE",
                    "PCR",
                    "IV",
                    "Volume",
                    "OI",
                    "S/R",
                    "Decision Reason",
                ],
                "Interpretation": [
                    row.get("decision_state", "—"),
                    row.get("directional_interpretation", "—"),
                    row.get("first_range_event", "—"),
                    row.get("futures_interpretation", "—"),
                    row.get("options_interpretation", "—"),
                    row.get("pcr_interpretation", "—"),
                    row.get("iv_interpretation", "—"),
                    row.get("volume_interpretation", "—"),
                    row.get("oi_interpretation", "—"),
                    row.get("sr_interpretation", "—"),
                    row.get("decision_reason", "—"),
                ],
            }
        )
        st.dataframe(
            evidence,
            use_container_width=True,
            hide_index=True,
        )


def _render_timeline(timeline: pd.DataFrame) -> None:
    """Render the replay as a focused evidence-history investigation tool.

    The replay never introduces a second stock-selection algorithm.  It uses
    the decision states already produced by the primary engine and offers:
      - Current Relevant: relevant in the latest replay observation
      - Historical Relevant: relevant at any point in the replay
      - Selected Stock: full evolution for one relevant stock
      - Raw Audit: the complete underlying replay data
    """
    if not isinstance(timeline, pd.DataFrame) or timeline.empty:
        return

    st.subheader("Decision Changes During Day Replay")

    df = timeline.copy()
    required = [
        "Time", "Snapshot", "Symbol", "Decision", "Direction",
        "Previous", "Evidence", "Strength", "S/R",
    ]
    for col in required:
        if col not in df.columns:
            df[col] = "—"

    df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
    df["Direction"] = df["Direction"].astype(str).str.upper().str.strip()
    df["Decision"] = df["Decision"].astype(str).str.upper().str.strip()
    df["Previous"] = df["Previous"].astype(str).str.upper().str.strip()

    # Existing engine relevance only.  No new score or threshold is created.
    relevant_states = {
        "DEVELOPING_BULLISH",
        "DEVELOPING_BEARISH",
        "WAIT_BREAK_CONFIRMATION",
        "ACTIVE_BULLISH",
        "ACTIVE_BEARISH",
        "STRONG_BULLISH",
        "STRONG_BEARISH",
    }
    df["_relevant"] = df["Decision"].isin(relevant_states)

    # Preserve chronological ordering while remaining tolerant of source
    # timestamp strings that are not perfectly uniform.
    if "Snapshot" in df.columns:
        df["_snapshot_num"] = pd.to_numeric(df["Snapshot"], errors="coerce")
    else:
        df["_snapshot_num"] = pd.NA
    df = df.sort_values(
        ["_snapshot_num", "Time", "Symbol"],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)

    latest_snapshot = (
        df["_snapshot_num"].dropna().max()
        if df["_snapshot_num"].notna().any()
        else None
    )
    if latest_snapshot is not None:
        latest = df.loc[df["_snapshot_num"].eq(latest_snapshot)].copy()
    else:
        latest = df.tail(1).copy()

    current_symbols = set(
        latest.loc[latest["_relevant"], "Symbol"].dropna().tolist()
    )
    historical_symbols = set(
        df.loc[df["_relevant"], "Symbol"].dropna().tolist()
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Relevant", len(current_symbols))
    c2.metric("Historical Relevant", len(historical_symbols))
    c3.metric("Replay Events", len(df))
    c4.metric("Observation Times", df["Time"].astype(str).nunique())

    scope = st.radio(
        "Replay scope",
        [
            "Current Relevant",
            "Historical Relevant",
            "Selected Stock",
            "Raw Audit",
        ],
        horizontal=True,
        key="ds_replay_scope",
    )

    if scope == "Raw Audit":
        st.caption(
            "Complete replay retained for audit/debugging. "
            "No stock-selection filtering is applied here."
        )
        st.dataframe(
            df[required],
            use_container_width=True,
            hide_index=True,
        )
        return

    if scope == "Current Relevant":
        scope_symbols = current_symbols
        scope_df = df[df["Symbol"].isin(scope_symbols)].copy()
        st.caption(
            "Only stocks relevant in the latest replay observation are shown. "
            "Relevance comes from the existing decision engine."
        )
    elif scope == "Historical Relevant":
        scope_symbols = historical_symbols
        scope_df = df[df["Symbol"].isin(scope_symbols)].copy()
        st.caption(
            "Stocks that were relevant at any point during the session are "
            "retained, including stocks that later lost relevance."
        )
    else:
        scope_symbols = historical_symbols
        scope_df = df[df["Symbol"].isin(scope_symbols)].copy()

    if not scope_symbols:
        st.info("No relevant decision stocks are present in this replay.")
        return

    symbols = sorted(scope_symbols)
    selected_symbol = st.selectbox(
        "Stock",
        symbols,
        key="ds_replay_symbol",
    )

    stock = scope_df.loc[scope_df["Symbol"].eq(selected_symbol)].copy()
    if stock.empty:
        st.info("No replay history is available for the selected stock.")
        return

    # Explicit relationship columns: state evolution and actual direction
    # reversal are different things and should not be conflated.
    stock["Decision Change"] = stock.apply(
        lambda r: (
            f'{r["Previous"]} → {r["Decision"]}'
            if r["Previous"] not in {"", "—", "NONE", "NAN"}
            else f'INITIAL → {r["Decision"]}'
        ),
        axis=1,
    )
    stock["Direction Change"] = stock.apply(
        lambda r: (
            f'{r["Previous"]} → {r["Direction"]}'
            if r["Previous"] in {"BULLISH", "BEARISH"}
            and r["Direction"] in {"BULLISH", "BEARISH"}
            and r["Previous"] != r["Direction"]
            else "—"
        ),
        axis=1,
    )
    stock["Event"] = stock.apply(
        lambda r: (
            "REVERSAL"
            if r["Direction Change"] != "—"
            else (
                "STATE CHANGE"
                if r["Previous"] not in {"", "—", "NONE", "NAN"}
                and r["Previous"] != r["Decision"]
                else "OBSERVATION"
            )
        ),
        axis=1,
    )

    reversals = int((stock["Event"] == "REVERSAL").sum())
    state_changes = int((stock["Event"] == "STATE CHANGE").sum())
    st.markdown(
        f"**{selected_symbol} — Intraday Decision Evolution**  "
        f"({len(stock)} observation(s) · {state_changes} state change(s) · "
        f"{reversals} direction reversal(s))"
    )

    display_cols = [
        "Time",
        "Snapshot",
        "Event",
        "Decision Change",
        "Direction Change",
        "Evidence",
        "Strength",
        "S/R",
    ]

    def _row_style(row):
        event = str(row.get("Event", ""))
        direction = str(row.get("Direction", "")).upper()
        if event == "REVERSAL":
            return ["background-color: #fff0f0; color: #8b0000"] * len(row)
        if direction == "BULLISH":
            return ["background-color: #eef9f0; color: #146c2e"] * len(row)
        if direction == "BEARISH":
            return ["background-color: #fff2f2; color: #9b1c1c"] * len(row)
        return ["background-color: #fff9e8; color: #7a5200"] * len(row)

    st.dataframe(
        stock[display_cols].style.apply(_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # Compact session relationship view.  This is deliberately derived from
    # the existing replay rows and does not create a new trading signal.
    st.markdown("**Decision path**")
    path_parts = []
    for _, row in stock.iterrows():
        time_value = str(row["Time"])
        decision = str(row["Decision"])
        direction = str(row["Direction"])
        path_parts.append(f"{time_value}  {direction}  {decision}")
    st.code("\n↓\n".join(path_parts), language="text")

    with st.expander("Raw replay audit data", expanded=False):
        st.dataframe(
            stock[required],
            use_container_width=True,
            hide_index=True,
        )


def _render_current_result(
    result: pd.DataFrame,
    timeline: pd.DataFrame,
    snapshot_label: str,
    widget_key_prefix: str = "",
) -> None:
    if result is None or not isinstance(result, pd.DataFrame) or result.empty:
        st.info("No decision result is available for this snapshot.")
        return

    candidates = _rank(result)
    gate_passed_count = int(
        result.get("gate_passed", pd.Series(False, index=result.index)).map(_bool).sum()
    )

    st.markdown(
        f'<div class="snapshot"><b>Current Snapshot:</b> {snapshot_label} &nbsp;|&nbsp; '
        f'<b>{len(result)}</b> evaluated &nbsp;|&nbsp; '
        f'<b>{gate_passed_count}</b> primary gate passed &nbsp;|&nbsp; '
        f'<b>{len(candidates)}</b> decision candidates</div>',
        unsafe_allow_html=True,
    )

    _render_summary(result, candidates)
    st.markdown('<div class="section">Current Decision Opportunities</div>', unsafe_allow_html=True)

    direction = candidates.get("decision_direction", pd.Series("", index=candidates.index)).astype(str).str.upper()
    state = candidates.get("decision_state", pd.Series("", index=candidates.index)).astype(str).str.upper()
    bullish_view = candidates.loc[direction.eq("BULLISH")].copy()
    bearish_view = candidates.loc[direction.eq("BEARISH")].copy()
    developing_view = candidates.loc[state.str.startswith("DEVELOPING")].copy()

    # WAIT BREAK is a state inside Bullish/Bearish. It is deliberately not a
    # separate current queue, preventing the same stock from being displayed
    # in multiple places.
    filter_value = st.radio(
        "Show",
        ["All", "Bullish", "Bearish", "Developing"],
        horizontal=True,
        key=f"{widget_key_prefix}ds_decision_filter",
    )
    if filter_value == "Bullish":
        filtered = bullish_view
    elif filter_value == "Bearish":
        filtered = bearish_view
    elif filter_value == "Developing":
        filtered = developing_view
    else:
        filtered = candidates.copy()

    _render_table(filtered)
    if not filtered.empty:
        symbol = st.selectbox(
            "Inspect one decision",
            filtered["symbol"].astype(str).tolist(),
            key=f"{widget_key_prefix}ds_inspect_stock",
        )
        selected = filtered.loc[filtered["symbol"].astype(str).eq(symbol)].iloc[0]
        _render_evidence(selected)

    no_decision_count = int(
        result.get("decision_state", pd.Series("", index=result.index)).astype(str).str.upper().eq("NO DECISION").sum()
    )
    weak_excluded = len(result) - len(candidates) - no_decision_count
    st.markdown(
        f'<div class="note">Coverage: {len(result)} evaluated. '
        f'NO DECISION hidden: {no_decision_count}. '
        f'Weak/conflicted rows hidden: {max(0, weak_excluded)}.</div>',
        unsafe_allow_html=True,
    )

    # Decision evolution is a historical change log, not a second current
    # stock queue. It is intentionally compact and timestamped.
    if isinstance(timeline, pd.DataFrame) and not timeline.empty:
        st.subheader("Decision Evolution — meaningful changes")
        evo = timeline.copy()
        evo["Time"] = evo["Time"].astype(str)
        st.dataframe(
            evo[[c for c in ["Time", "Symbol", "Decision", "Previous", "Direction", "Evidence", "S/R"] if c in evo.columns]].tail(40),
            use_container_width=True,
            hide_index=True,
        )



def _persist_last_complete_state(
    trading_date: str,
    result: pd.DataFrame,
    timeline: pd.DataFrame,
    source_path: Path,
) -> None:
    """Persist only the last complete decision-bearing dashboard state."""
    if result is None or not isinstance(result, pd.DataFrame) or result.empty:
        return

    state = load_state(STATE_JSON)
    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    day["last_complete_state"] = {
        "source_file": str(source_path),
        "source_key": _source_key(source_path),
        "observation_timestamp": parse_observation_timestamp(source_path).isoformat(),
        "saved_at": datetime.now().isoformat(),
        "result": result.to_dict(orient="records"),
        "timeline": (
            timeline.to_dict(orient="records")
            if isinstance(timeline, pd.DataFrame) and not timeline.empty
            else []
        ),
    }
    save_state(state, STATE_JSON)


def _restore_last_complete_state(
    trading_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame, str, str] | None:
    """Restore durable final state without replaying the day."""
    state = load_state(STATE_JSON)
    day = state.get(STATE_KEY, {}).get(trading_date, {}) or {}
    saved = day.get("last_complete_state")
    if not isinstance(saved, dict):
        return None

    rows = saved.get("result")
    if not isinstance(rows, list) or not rows:
        return None

    result = pd.DataFrame(rows)
    timeline_rows = saved.get("timeline", [])
    timeline = (
        pd.DataFrame(timeline_rows)
        if isinstance(timeline_rows, list)
        else pd.DataFrame()
    )
    source_file = str(saved.get("source_file", "")).strip()
    observation_timestamp = str(saved.get("observation_timestamp", "")).strip()
    return result, timeline, source_file, observation_timestamp


if hasattr(st, "fragment"):
    @st.fragment(run_every="10s")
    def _live_auto_panel(source_root: Path, trading_date: str, auto_update: bool) -> None:
        # Re-discover on every live fragment cycle so newly-arrived snapshots
        # become visible without requiring a manual full-page refresh.
        try:
            sources = _discover_sources(trading_date, source_root)
            if not sources:
                st.info("No intraday snapshots are currently available for this date.")
                return

            _, market_open = _market_session_status(trading_date)
            session_state = st.session_state.setdefault(_live_session_key(trading_date), {})
            session_state["last_source_key"] = _source_key(sources[-1])

            if market_open and auto_update:
                latest, timeline, _changed = _auto_process_new_snapshots(sources, trading_date)
                session_state["finalized"] = False
            else:
                # Outside market hours, restore durable final state first.
                # Do not replay the whole day merely because Streamlit state
                # was lost.
                restored = _restore_last_complete_state(trading_date)
                if restored is not None:
                    latest, timeline, persisted_source, persisted_timestamp = restored
                    session_state["finalized"] = True
                    session_state["final_snapshot_key"] = (
                        persisted_source or _source_key(sources[-1])
                    )
                    session_state["finalized_at"] = datetime.now().isoformat()
                else:
                    latest, timeline, _ = _load_day_for_snapshot_view(
                        sources, trading_date
                    )
                    persisted_source = ""
                    persisted_timestamp = ""
                    if latest is not None and not latest.empty:
                        session_state["finalized"] = True
                        session_state["final_snapshot_key"] = _source_key(sources[-1])
                        session_state["finalized_at"] = datetime.now().isoformat()

            if latest is None or latest.empty:
                st.info("The first snapshot is BASE ONLY. Waiting for the first decision-bearing snapshot.")
                return

            if not market_open and persisted_source:
                latest_path = Path(persisted_source)
                try:
                    latest_time = (
                        datetime.fromisoformat(persisted_timestamp)
                        if persisted_timestamp
                        else parse_observation_timestamp(latest_path)
                    )
                except (TypeError, ValueError):
                    latest_time = parse_observation_timestamp(latest_path)
            else:
                latest_path = sources[-1]
                latest_time = parse_observation_timestamp(latest_path)
            if market_open:
                status = "LIVE • market open"
                if auto_update:
                    status += " • Auto-update ON"
                else:
                    status += " • Auto-update OFF"
            else:
                status = "FINAL SESSION STATE • market closed • preserved from last complete snapshot"

            st.caption(f"{status} • {latest_time:%H:%M:%S} • {latest_path.name}")
            _render_current_result(latest, timeline, latest_time.strftime("%H:%M:%S"), "live_")
        except Exception as exc:
            st.error(f"Live processing failed: {type(exc).__name__}: {exc}")


def _load_day_for_snapshot_view(sources: list[Path], trading_date: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    cache = _get_replay_cache(trading_date)
    snapshots = cache.get("snapshots", {})
    if isinstance(snapshots, dict) and all(_source_key(p) in snapshots for p in sources):
        latest = snapshots.get(_source_key(sources[-1]), pd.DataFrame()) if sources else pd.DataFrame()
        return latest, cache.get("timeline", pd.DataFrame()), snapshots
    latest, timeline, snapshots = _process_and_cache_day(sources, trading_date)
    return latest, timeline, snapshots


def render() -> None:
    st.set_page_config(
        page_title="NTIS SDL — Intraday Decision Center",
        layout="wide",
    )
    _css()

    st.markdown(
        """
<div class="hero">
  <div class="hero-title">NTIS SDL — Intraday Decision Center</div>
  <div class="hero-sub">Current decision intelligence from the latest complete snapshot — with intraday and historical replay.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Source location is intentionally hidden behind a collapsed configuration
    # section. The production/default path remains the value from config.py,
    # while an operator can override it when the data location changes.
    default_source_root = str(Path(INTRADAY_SOURCE_ROOT).expanduser())
    if "ds_source_root_override" not in st.session_state:
        st.session_state["ds_source_root_override"] = default_source_root

    with st.expander("⚙ Advanced Configuration", expanded=False):
        configured_source_root = st.text_input(
            "Intraday source data folder",
            value=st.session_state["ds_source_root_override"],
            key="ds_source_root_input",
            help="Normally leave this unchanged. Use it only if the intraday snapshot source folder changes.",
        ).strip()
        if not configured_source_root:
            configured_source_root = default_source_root
        if configured_source_root != st.session_state["ds_source_root_override"]:
            st.session_state["ds_source_root_override"] = configured_source_root
            st.session_state.pop("ds_data_view", None)
            st.rerun()

    view_options = ["CURRENT DAY", "HISTORICAL"]
    if st.session_state.get("ds_data_view") not in view_options:
        st.session_state["ds_data_view"] = "CURRENT DAY"

    c1, c2 = st.columns([1, 1])
    with c1:
        view_mode = st.radio(
            "Data view",
            view_options,
            horizontal=True,
            key="ds_data_view",
            help="CURRENT DAY keeps LIVE and INTRADAY SNAPSHOT visible together. HISTORICAL remains a separate replay view.",
        )
    with c2:
        trading_date = st.date_input(
            "Trading date",
            value=date.today(),
            key="ds_trading_date",
        ).strftime("%Y-%m-%d")

    source_root = Path(st.session_state.get("ds_source_root_override", default_source_root)).expanduser()
    try:
        sources = _discover_sources(trading_date, source_root)
    except Exception as exc:
        st.error(f"Source discovery failed: {type(exc).__name__}: {exc}")
        return
    if not sources:
        st.warning("No Daywise snapshots found for the selected date.")
        return

    latest_path = sources[-1]
    latest_time = parse_observation_timestamp(latest_path)
    st.markdown(
        f'<div class="snapshot"><b>Snapshots:</b> {len(sources)} &nbsp;|&nbsp; '
        f'<b>First:</b> {parse_observation_timestamp(sources[0]):%H:%M:%S} &nbsp;|&nbsp; '
        f'<b>Latest:</b> {latest_time:%H:%M:%S}</div>',
        unsafe_allow_html=True,
    )

    if view_mode == "CURRENT DAY":
        # CURRENT DAY intentionally renders LIVE and INTRADAY SNAPSHOT together.
        # LIVE owns the live-processing path; the snapshot section only reads
        # the already-prepared replay cache (or explicitly prepares it when
        # needed for snapshot inspection). The two views use independent
        # Streamlit widget keys so changing the snapshot selector cannot alter
        # LIVE state.
        st.markdown(
            '<div class="section">LIVE</div>',
            unsafe_allow_html=True,
        )

        a1, a2 = st.columns([2, 1])
        with a1:
            auto_update = st.checkbox(
                "Auto-update live feed",
                value=True,
                key="ds_auto_update",
            )
        with a2:
            refresh = st.button(
                "↻ Refresh",
                use_container_width=True,
                key="ds_live_refresh",
            )

        if refresh:
            st.session_state.pop(_cache_key(trading_date), None)
            st.rerun()

        # Auto-update remains the existing live function and is not duplicated.
        if hasattr(st, "fragment"):
            _live_auto_panel(source_root, trading_date, auto_update)
        else:
            try:
                live_sources = _discover_sources(trading_date, source_root)
                _, market_open = _market_session_status(trading_date)
                if market_open and auto_update:
                    latest, timeline, _changed = _auto_process_new_snapshots(
                        live_sources, trading_date
                    )
                    persisted_source = ""
                    persisted_timestamp = ""
                else:
                    restored = _restore_last_complete_state(trading_date)
                    if restored is not None:
                        latest, timeline, persisted_source, persisted_timestamp = restored
                    else:
                        latest, timeline, _ = _load_day_for_snapshot_view(
                            live_sources, trading_date
                        )
                        persisted_source = ""
                        persisted_timestamp = ""
            except Exception as exc:
                st.error(f"Live processing failed: {type(exc).__name__}: {exc}")
                return

            if latest is None or latest.empty:
                st.info(
                    "The first snapshot is BASE ONLY. Waiting for the first "
                    "decision-bearing snapshot."
                )
            else:
                if not market_open and persisted_source:
                    live_path = Path(persisted_source)
                    try:
                        live_time = (
                            datetime.fromisoformat(persisted_timestamp)
                            if persisted_timestamp
                            else parse_observation_timestamp(live_path)
                        )
                    except (TypeError, ValueError):
                        live_time = parse_observation_timestamp(live_path)
                else:
                    live_path = live_sources[-1]
                    live_time = parse_observation_timestamp(live_path)

                if market_open:
                    status = "LIVE • market open" + (
                        " • Auto-update ON" if auto_update else " • Auto-update OFF"
                    )
                else:
                    status = (
                        "FINAL SESSION STATE • market closed • preserved from "
                        "last complete snapshot"
                    )

                st.caption(
                    f"{status} • {live_time:%H:%M:%S} • {live_path.name}"
                )
                _render_current_result(
                    latest,
                    timeline,
                    live_time.strftime("%H:%M:%S"),
                    "live_",
                )

        st.markdown(
            '<div class="section">INTRADAY SNAPSHOT</div>',
            unsafe_allow_html=True,
        )

        # Snapshot inspection is independent from LIVE. It uses the existing
        # replay cache and does not change the live session state.
        try:
            replay_cache = _get_replay_cache(trading_date)
            snapshots = replay_cache.get("snapshots", {})
            timeline = replay_cache.get("timeline", pd.DataFrame())

            if not isinstance(snapshots, dict) or not all(
                _source_key(p) in snapshots for p in sources
            ):
                _, timeline, snapshots = _load_day_for_snapshot_view(
                    sources,
                    trading_date,
                )
        except Exception as exc:
            st.error(
                f"Intraday replay preparation failed: {type(exc).__name__}: {exc}"
            )
            return

        labels = [
            parse_observation_timestamp(p).strftime("%H:%M:%S")
            for p in sources
        ]
        idx = st.selectbox(
            "Snapshot time",
            list(range(len(sources))),
            index=len(sources) - 1,
            format_func=lambda i: labels[i],
            key="ds_intraday_snapshot",
        )
        selected_path = sources[idx]
        selected_key = _source_key(selected_path)
        result = snapshots.get(selected_key, pd.DataFrame())

        if idx == 0:
            st.info(
                f"{labels[idx]} is the BASE snapshot only; it establishes "
                "the opening reference and has no decision rows."
            )
        else:
            _render_current_result(
                result,
                timeline,
                labels[idx],
                "intraday_",
            )

    else:  # HISTORICAL
        historical_date = st.date_input("Historical trading date", value=date.today(), key="ds_historical_date").strftime("%Y-%m-%d")
        try:
            historical_sources = _discover_sources(historical_date, source_root)
        except Exception as exc:
            st.error(f"Historical source discovery failed: {type(exc).__name__}: {exc}")
            return
        if not historical_sources:
            st.info("No snapshots found for the selected historical day.")
            return

        try:
            _, timeline, snapshots = _load_day_for_snapshot_view(historical_sources, historical_date)
        except Exception as exc:
            st.error(f"Historical replay preparation failed: {type(exc).__name__}: {exc}")
            return

        idx = st.selectbox(
            "Historical snapshot time",
            list(range(len(historical_sources))),
            index=len(historical_sources)-1,
            format_func=lambda i: parse_observation_timestamp(historical_sources[i]).strftime("%H:%M:%S"),
            key="ds_historical_snapshot",
        )
        selected_path = historical_sources[idx]
        if idx == 0:
            st.info("The selected historical snapshot is BASE ONLY.")
            return
        result = snapshots.get(_source_key(selected_path), pd.DataFrame())
        _render_current_result(result, timeline, parse_observation_timestamp(selected_path).strftime("%H:%M:%S"), "historical_")


if __name__ == "__main__":
    render()
