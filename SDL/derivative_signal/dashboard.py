from __future__ import annotations

from datetime import date, datetime
import html
import time
from pathlib import Path
from typing import Any
import re

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

def parse_observation_timestamp(path: Path) -> datetime:
    """Return the authoritative Windows source arrival/creation timestamp."""
    try:
        return datetime.fromtimestamp(path.stat().st_ctime)
    except (OSError, ValueError, OverflowError):
        return datetime.min


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


def _available_trading_dates(source_root: Path) -> list[str]:
    """Return dates for which the source layer has actual Daywise files."""
    root = Path(source_root).expanduser()
    if not root.exists():
        return []

    candidates: set[str] = set()
    pattern = re.compile(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)")
    for item in root.rglob("*"):
        if item.is_file():
            match = pattern.search(str(item))
            if match:
                candidates.add(match.group(1))

    valid: list[str] = []
    for day in sorted(candidates):
        try:
            if _discover_sources(day, root):
                valid.append(day)
        except Exception:
            continue
    return valid


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
        "Volume", "volume", "Total Volume", "total_volume",
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
        # The source Symbol field is the identity key used throughout the
        # intraday chain. Normalize once and carry that identity forward.
        signal["symbol"] = symbol
        signal["source_evidence"] = source_map

        enriched = enrich_decision(
            signal,
            record,
            context=first_range or {},
        )

        # Retracement needs the actual price/HL/volume observations from the
        # source snapshot. enrich_decision intentionally returns the decision
        # schema, so preserve these raw market fields alongside it for the
        # diagnostic lifecycle. This does not participate in SDL scoring,
        # candidate selection, or ranking.
        for raw_key in (
            "Open", "open",
            "High", "high",
            "Low", "low",
            "Close", "close",
            "Volume", "volume",
            "Total Volume", "total_volume",
            "Price", "price",
            "CMP", "cmp",
            "Support", "support",
            "Resistance", "resistance",
        ):
            if raw_key in record and (
                raw_key not in enriched
                or pd.isna(enriched.get(raw_key))
            ):
                enriched[raw_key] = record.get(raw_key)

        if enriched.get("reference_price") is None:
            for price_key in (
                "Close", "close", "Price", "price", "CMP", "cmp"
            ):
                price_value = pd.to_numeric(
                    record.get(price_key), errors="coerce"
                )
                if pd.notna(price_value) and float(price_value) > 0:
                    enriched["reference_price"] = float(price_value)
                    break

        rows.append(enriched)

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


def _timeline_first_alert_value(
    row: dict[str, Any],
    event_timestamp: datetime,
) -> str:
    """Return immutable First Alert provenance for every timeline event."""
    value = str(row.get("first_alert_timestamp", "")).strip()
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        return "—"


def _update_first_alerts(
    state: dict[str, Any],
    trading_date: str,
    result: pd.DataFrame,
    timestamp: datetime,
    first_alerts: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Preserve the first time a stock enters the existing decision table.

    This is provenance only.  The existing _rank() result remains the sole
    authority for which rows are visible in the decision table; no new
    decision threshold or trading rule is introduced here.
    """
    if result is None or not isinstance(result, pd.DataFrame) or result.empty:
        return result

    visible = _rank(result)
    if not visible.empty and "symbol" in visible.columns:
        for row in visible.to_dict(orient="records"):
            symbol = str(row.get("symbol", "")).strip().upper()
            if not symbol or symbol in first_alerts:
                continue
            first_alerts[symbol] = {
                "timestamp": timestamp.isoformat(),
                "source_file": str(row.get("source_file", "")),
                "decision": str(row.get("decision_state", "NO DECISION")),
                "direction": str(
                    row.get("decision_direction", row.get("direction", "NEUTRAL"))
                ),
            }

    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    day["first_alerts"] = first_alerts

    out = result.copy()
    out["first_alert_timestamp"] = out["symbol"].map(
        lambda value: str(first_alerts.get(str(value).strip().upper(), {}).get("timestamp", ""))
    )
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
    if not result.empty:
        first_alerts = day.get("first_alerts", {}) or {}
        result = _update_first_alerts(
            state, trading_date, result, parse_observation_timestamp(path), first_alerts
        )
    save_state(state, STATE_JSON)

    return result



def _update_retracement_alerts(
    state: dict[str, Any],
    trading_date: str,
    result: pd.DataFrame,
    snapshot_results: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Persist structural-break provenance and one-shot retracement alerts."""
    if result is None or result.empty:
        return result

    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    watches = day.get("retracement_watches", {}) or {}
    alerts = day.get("retracement_alerts", {}) or {}
    structural_breaks = day.get("structural_breaks", {}) or {}
    first_alerts = day.get("first_alerts", {}) or {}

    for _, row in result.iterrows():
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol:
            continue

        direction = str(
            row.get("decision_direction", row.get("direction", "NEUTRAL"))
        ).upper().strip()
        sr = _sr_text(row).upper().strip()
        current_ts = pd.to_datetime(
            row.get("source_timestamp", row.get("observation_timestamp", "")),
            errors="coerce",
        )

        is_break = (
            direction == "BULLISH" and sr == "RESISTANCE BROKEN"
        ) or (
            direction == "BEARISH" and sr == "SUPPORT BROKEN"
        )

        # Record the FIRST structural break for this direction. This is
        # separate from First Alert and is never overwritten by later snapshots.
        if is_break and pd.notna(current_ts):
            existing = structural_breaks.get(symbol)
            existing_direction = (
                str(existing.get("direction", "")).upper()
                if isinstance(existing, dict) else ""
            )
            if not isinstance(existing, dict) or existing_direction != direction:
                structural_breaks[symbol] = {
                    "date": trading_date,
                    "direction": direction,
                    "break_timestamp": current_ts.isoformat(),
                    "break_level": (
                        float(pd.to_numeric(
                            row.get("Resistance", row.get("resistance")),
                            errors="coerce"
                        ))
                        if direction == "BULLISH"
                        and pd.notna(pd.to_numeric(
                            row.get("Resistance", row.get("resistance")),
                            errors="coerce"
                        ))
                        else (
                            float(pd.to_numeric(
                                row.get("Support", row.get("support")),
                                errors="coerce"
                            ))
                            if direction == "BEARISH"
                            and pd.notna(pd.to_numeric(
                                row.get("Support", row.get("support")),
                                errors="coerce"
                            ))
                            else None
                        )
                    ),
                    "first_alert_timestamp": str(
                        first_alerts.get(symbol, {}).get("timestamp", "")
                    ),
                    "source_file": str(row.get("source_file", "")),
                }

        ctx = _retracement_context(row, snapshot_results)
        if ctx.get("status") == "INVALIDATED":
            watches.pop(symbol, None)
            continue
        if ctx.get("status") not in {"WATCH", "REENTRY ALERT"}:
            continue

        watches[symbol] = {
            "direction": ctx.get("primary_direction", ""),
            "entry_name": ctx.get("entry_name", ""),
            "entry_level": ctx.get("entry_level"),
            "status": ctx.get("status"),
            "break_timestamp": (
                ctx["break_timestamp"].isoformat()
                if ctx.get("break_timestamp") else ""
            ),
            "break_origin": ctx.get("break_origin", ""),
            "carried_break_date": ctx.get("carried_break_date", ""),
            "original_first_alert_timestamp": (
                ctx.get("carried_first_alert_timestamp", "")
                or str(first_alerts.get(symbol, {}).get("timestamp", ""))
            ),
            "updated_at": (
                current_ts.isoformat() if pd.notna(current_ts) else ""
            ),
        }

        # One-shot re-entry alert. It is deliberately stored separately from
        # the immutable original First Alert.
        if ctx.get("status") == "REENTRY ALERT" and symbol not in alerts:
            if pd.notna(current_ts):
                alerts[symbol] = {
                    "timestamp": current_ts.isoformat(),
                    "direction": ctx.get("primary_direction", ""),
                    "entry_name": ctx.get("entry_name", ""),
                    "entry_level": ctx.get("entry_level"),
                    "reason": ctx.get("reason", ""),
                    "original_first_alert_timestamp": (
                        ctx.get("carried_first_alert_timestamp", "")
                        or str(first_alerts.get(symbol, {}).get("timestamp", ""))
                    ),
                    "break_timestamp": (
                        ctx["break_timestamp"].isoformat()
                        if ctx.get("break_timestamp") else ""
                    ),
                    "break_origin": ctx.get("break_origin", ""),
                }

    day["structural_breaks"] = structural_breaks
    day["retracement_watches"] = watches
    day["retracement_alerts"] = alerts
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
    first_alerts: dict[str, dict[str, Any]] = (
        state.get(STATE_KEY, {}).get(trading_date, {}).get("first_alerts", {}) or {}
    )

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

        # Preserve the first timestamp at which each stock entered the existing
        # visible decision table BEFORE lifecycle processing records provenance.
        # This is provenance only; _rank remains the authority for visibility.
        result = _update_first_alerts(
            state, trading_date, result, timestamp, first_alerts
        )

        # Build retracement state from the chronological chain only. This
        # cannot modify the frozen candidate pool.
        if capture_snapshots:
            snapshot_results[_source_key(path)] = result
            result = _update_retracement_alerts(
                state, trading_date, result, snapshot_results
            )

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
                        "First Alert": _timeline_first_alert_value(row, timestamp),
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
    """Return LIVE at the latest successfully processed source.

    The durable state source is the authoritative processing checkpoint.
    On every live cycle, any source chronologically newer than that checkpoint
    is processed in order. This prevents a stale in-memory replay cache from
    making LIVE stop at an older snapshot after a restart/day rollover.
    """
    if not sources:
        return pd.DataFrame(), pd.DataFrame(), False

    state = load_state(STATE_JSON)
    day = state.get(STATE_KEY, {}).get(trading_date, {}) or {}
    saved = day.get("last_complete_state", {}) or {}
    checkpoint_file = str(
        day.get("source_file")
        or saved.get("source_file")
        or ""
    ).strip()

    # Establish the authoritative checkpoint index from durable state.
    checkpoint_key = _source_key(Path(checkpoint_file)) if checkpoint_file else ""
    checkpoint_idx = -1
    if checkpoint_key:
        for i, path in enumerate(sources):
            if _source_key(path) == checkpoint_key:
                checkpoint_idx = i
                break

    # If durable state is absent, restore it from the last complete record.
    if checkpoint_idx < 0 and saved.get("source_file"):
        restored_path = Path(str(saved["source_file"]))
        restored_key = _source_key(restored_path)
        for i, path in enumerate(sources):
            if _source_key(path) == restored_key:
                checkpoint_idx = i
                checkpoint_key = restored_key
                break

    cache = _get_replay_cache(trading_date)
    cached_snapshots = cache.get("snapshots", {})
    if not isinstance(cached_snapshots, dict):
        cached_snapshots = {}

    # Genuinely new day/state: process the complete chronological chain once.
    if checkpoint_idx < 0:
        latest, timeline, snapshots = _process_and_cache_day(
            sources, trading_date
        )
        return latest, timeline, True

    # Reuse the durable result at the checkpoint as the starting LIVE result.
    restored = _restore_last_complete_state(trading_date)
    if restored is not None:
        latest_result, restored_timeline, _, _ = restored
    else:
        latest_result = cached_snapshots.get(checkpoint_key, pd.DataFrame())
        restored_timeline = cache.get("timeline", pd.DataFrame())

    if not isinstance(restored_timeline, pd.DataFrame):
        restored_timeline = pd.DataFrame()

    # IMPORTANT: the durable checkpoint, not cache membership, determines what
    # still needs processing. Process only a small chronological batch per
    # fragment so the UI remains responsive while LIVE catches up.
    all_new_paths = sources[checkpoint_idx + 1 :]
    new_paths = all_new_paths[:3]

    if not new_paths:
        # Ensure the cache is synchronized to the known checkpoint.
        if isinstance(latest_result, pd.DataFrame) and not latest_result.empty:
            cached_snapshots[checkpoint_key] = latest_result
            _store_replay_cache(
                trading_date, cached_snapshots, restored_timeline
            )
        return latest_result, restored_timeline, False

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
    first_alerts = day.get("first_alerts", {}) or {}
    first_range = _first_range_from_path(sources[0], trading_date)

    timeline_rows = restored_timeline.to_dict(orient="records")
    state_changed_any = False

    for path in new_paths:
        result = _process_snapshot(path, trading_date, previous, first_range)
        result = _attach_snapshot_metadata(result, path)
        timestamp = parse_observation_timestamp(path)

        result = _update_first_alerts(
            state, trading_date, result, timestamp, first_alerts
        )

        if result.empty:
            previous = _snapshot_rows(_read(path))
            continue

        # Keep the chronological snapshot cache synchronized BEFORE evaluating
        # the retracement lifecycle. The lifecycle needs the complete chain,
        # not only the latest LIVE result.
        cached_snapshots[_source_key(path)] = result
        result = _update_retracement_alerts(
            state, trading_date, result, cached_snapshots
        )
        cached_snapshots[_source_key(path)] = result

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
                timeline_rows.append({
                    "Time": timestamp.strftime("%H:%M:%S"),
                    "First Alert": _timeline_first_alert_value(row, timestamp),
                    "Snapshot": len(cached_snapshots) + 1,
                    "Symbol": symbol,
                    "Decision": row.get("decision_state", "NO DECISION"),
                    "Direction": direction,
                    "Previous": (
                        old_direction
                        if direction_changed
                        else old_state or "—"
                    ),
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

        # Persist after EACH successfully processed snapshot. A restart can
        # therefore resume exactly at the last completed point.
        timeline_now = pd.DataFrame(timeline_rows)
        _persist_last_complete_state(
            trading_date,
            latest_result,
            timeline_now,
            path,
        )
        state_changed_any = True

    timeline = pd.DataFrame(timeline_rows)
    _store_replay_cache(trading_date, cached_snapshots, timeline)

    if latest_result is None or latest_result.empty:
        latest_result = cached_snapshots.get(
            _source_key(sources[-1]),
            latest_result if isinstance(latest_result, pd.DataFrame)
            else pd.DataFrame(),
        )

    return latest_result, timeline, state_changed_any


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

    gate = result.get(
        "gate_passed",
        pd.Series(False, index=result.index),
    ).map(_bool).fillna(False)

    # HARD PRIMARY GATE. No developing/wait/actionable state may bypass it.
    gate_mask = gate.copy()

    strong_or_active = state.isin({
        "STRONG_BULLISH",
        "STRONG_BEARISH",
        "ACTIVE_BULLISH",
        "ACTIVE_BEARISH",
    })

    confirmed = (
        (
            (direction == "BULLISH")
            & (price >= 0.75)
        )
        | (
            (direction == "BEARISH")
            & (price <= -0.75)
        )
    )

    actionable = strong_or_active & confirmed & (conflicts == 0)

    # These states are already produced by the underlying evidence engine.
    # Do not impose a new score/confirmation threshold at dashboard level.
    developing = state.isin(DEVELOPING_STATES)
    wait_break = state.eq("WAIT_BREAK_CONFIRMATION")

    relevant = actionable | developing | wait_break

    # Absolute gate is applied to every branch; material conflicts are kept
    # out of the primary decision pool.
    return gate_mask & relevant & (conflicts <= 1)

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
/* TOP deployment: hide Streamlit chrome only; dashboard background is untouched. */
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"],
#MainMenu{display:none !important}
.block-container{max-width:1500px;padding-top:.55rem;padding-bottom:2rem}
.hero{
    padding:17px 26px;
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
.top-status{
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin:2px 0 16px 0;
}
.top-status-chip{
    display:inline-flex;
    align-items:center;
    gap:7px;
    border:1px solid #e2e8f0;
    border-radius:999px;
    padding:8px 12px;
    background:#ffffff;
    color:#334155;
    font-size:11.5px;
    font-weight:700;
}
.top-status-dot{
    width:8px;
    height:8px;
    border-radius:50%;
    background:#64748b;
    flex:0 0 auto;
}
.top-status-ready .top-status-dot{background:#16a34a}
.top-status-live .top-status-dot{background:#2563eb}
.top-status-closed .top-status-dot{background:#64748b}
.top-status-armed .top-status-dot{background:#2563eb}
.top-status-active .top-status-dot{background:#16a34a}

/* SECTION 3 — Current Decision Opportunities */
.opportunity-grid{
    display:grid;
    grid-template-columns:repeat(3,minmax(0,1fr));
    gap:10px;
    margin:10px 0 12px 0;
}
.opportunity-card{padding:11px 12px 10px;border-radius:9px;min-height:0;overflow:hidden;color:var(--card-text);}
.opportunity-card .card-top{display:flex;justify-content:space-between;align-items:center;font-size:10px;line-height:1;margin-bottom:5px;}
.opportunity-card .rank{opacity:.72;letter-spacing:.4px;}
.opportunity-card .direction{font-weight:800;font-size:10px;letter-spacing:.3px;}
.opportunity-card .symbol{font-size:18px;font-weight:850;line-height:1.05;margin:2px 0 5px;letter-spacing:.2px;}
.opportunity-card .move-line{display:flex;align-items:baseline;gap:9px;margin-bottom:3px;}
.opportunity-card .move{font-size:22px;font-weight:900;line-height:1;}
.opportunity-card .strength{font-size:11px;font-weight:800;letter-spacing:.2px;}
.opportunity-card .state{font-size:10px;font-weight:800;line-height:1.15;margin-bottom:5px;opacity:.98;}
.opportunity-card .quality-row{font-size:9px;line-height:1.15;margin-top:4px;}
.opportunity-card .quality-meter{height:7px;margin:3px 0 4px;border-radius:5px;overflow:hidden;background:rgba(255,255,255,.30);}
.opportunity-card .quality-caption{font-size:9px;line-height:1.15;margin-bottom:4px;}
.opportunity-card .setup-outlook{font-size:11px;line-height:1.2;margin-top:5px;font-weight:850;}
.opportunity-card .setup-caution{font-size:10px;line-height:1.25;margin-top:2px;opacity:.95;}
.opportunity-card .data-confidence{display:flex;justify-content:space-between;align-items:center;font-size:9px;line-height:1.15;margin-top:5px;font-weight:700;}
.opportunity-card .data-confidence b{font-size:12px;font-weight:900;}
.opportunity-card .break-caption{font-size:9px;line-height:1.15;margin-top:4px;font-weight:800;}
.opportunity-card .metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-top:7px;}
.opportunity-card .metric{padding:6px 5px;border-radius:5px;background:rgba(255,255,255,.72);color:#182033;min-width:0;}
.opportunity-card .metric span{display:block;font-size:7px;font-weight:800;letter-spacing:.3px;opacity:.82;line-height:1.05;}
.opportunity-card .metric b{display:block;font-size:11px;font-weight:900;line-height:1.1;margin-top:3px;white-space:nowrap;}
.opportunity-card .metric.first-alert b{font-size:10px;letter-spacing:.1px;}
.opportunity-card .opportunity-reason{font-size:9px;line-height:1.2;margin-top:5px;opacity:.96;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.setup-outlook{font-size:11px;line-height:1.35;margin-top:5px;color:var(--card-text);}.data-confidence{font-size:10px;line-height:1.25;margin-top:4px;opacity:.96;color:var(--card-text);}.data-confidence b{font-size:11px;}.opportunity-reason{font-size:6.5px;margin-top:3px;color:#334155}
.live-queue-panel{margin-top:10px;border-radius:10px;padding:9px 10px;background:#0b1d33;border:1px solid #1d3858}.live-queue-title{font-size:12px;font-weight:900;color:#f8fafc}.live-queue-sub{font-size:8px;color:#9fb1c7;margin-top:2px}.live-queue-grid{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:6px;margin-top:7px}.live-queue-tile{min-width:0;border:1px solid var(--queue-accent,#64748b);border-radius:7px;padding:7px;background:linear-gradient(135deg,rgba(255,255,255,.04),var(--queue-bg,#172033))}.queue-head{display:flex;justify-content:space-between;gap:4px;font-size:9.5px;color:#f8fafc}.queue-head span{color:var(--queue-accent,#cbd5e1);font-weight:900;font-size:8.5px}.queue-state{font-size:8.5px;color:#cbd5e1;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.queue-move{font-size:15px;font-weight:950;color:#fbbf24;margin-top:4px}.queue-quality{height:4px;border-radius:999px;background:rgba(255,255,255,.10);overflow:hidden;margin-top:4px}.queue-quality span{display:block;height:100%;background:var(--queue-accent,#94a3b8)}.queue-foot{display:flex;justify-content:space-between;gap:3px;color:#aab9ca;font-size:8px;margin-top:4px}
@media(max-width:1200px){.compact-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.live-queue-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:900px){.compact-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.live-queue-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}

.opportunity-top{
    display:flex;
    justify-content:space-between;
    align-items:flex-start;
    gap:8px;
}
.opportunity-rank{
    font-size:9px;
    font-weight:800;
    color:#64748b;
}
.opportunity-stock{
    font-size:16px;
    font-weight:900;
    color:var(--card-text,#0f172a);
}
.opportunity-direction{
    font-size:10px;
    font-weight:900;
    color:var(--card-accent,#475569);
}
.opportunity-state{
    margin-top:4px;
    font-size:10px;
    font-weight:800;
    color:var(--card-text,#334155);
}
.opportunity-metrics{
    display:grid;
    grid-template-columns:repeat(4,minmax(0,1fr));
    gap:5px;
    margin-top:10px;
}
.opportunity-metric{
    border:1px solid rgba(100,116,139,.16);
    border-radius:7px;
    padding:5px 5px;
    background:rgba(255,255,255,.58);
}
.opportunity-metric-label{
    display:block;
    font-size:7.5px;
    color:#64748b;
    text-transform:uppercase;
}
.opportunity-metric-value{
    display:block;
    margin-top:2px;
    font-size:10.5px;
    font-weight:900;
    color:var(--card-text,#0f172a);
}
.opportunity-bottom{
    margin-top:8px;
    display:flex;
    justify-content:space-between;
    gap:8px;
    font-size:9px;
    color:#475569;
}
.opportunity-sr{
    font-weight:800;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}
.opportunity-move{
    font-weight:900;
    white-space:nowrap;
}
.opportunity-reason{
    margin-top:6px;
    font-size:9px;
    line-height:1.25;
    color:#475569;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}
@media(max-width:1050px){
    .opportunity-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:700px){
    .opportunity-grid{grid-template-columns:1fr}
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
.inspect-strip{
    border:1px solid #e2e8f0;
    border-radius:10px;
    padding:8px 10px;
    margin:8px 0 8px 0;
    background:#f8fafc
}
.inspect-title{font-size:14px;font-weight:800;color:#0f172a;display:inline-block}
.inspect-direction{font-size:11px;color:#64748b;display:inline-block;margin-left:10px}
.inspect-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:7px}
.inspect-cell{min-width:0}
.inspect-label{font-size:9px;color:#64748b;text-transform:uppercase}
.inspect-value{font-size:12px;font-weight:700;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* Deployment 28: opportunity-card renderer-aligned visual polish */
.opportunity-grid.compact-grid{
    display:grid;
    grid-template-columns:repeat(5,minmax(0,1fr));
    gap:7px;
    margin:8px 0 10px;
}
.opportunity-card.compact{
    display:block;
    box-sizing:border-box;
    min-width:0;
    min-height:158px;
    padding:9px 10px 8px;
    border:1px solid var(--card-accent,#64748b);
    border-left:5px solid var(--card-accent,#64748b);
    border-radius:8px;
    background:var(--card-bg,#f8fafc);
    color:var(--card-text,#172033);
    overflow:hidden;
}
.opportunity-card.compact .opportunity-top{
    display:flex;
    justify-content:space-between;
    align-items:flex-start;
    gap:6px;
}
.opportunity-card.compact .opportunity-rank{
    font-size:7px;
    line-height:1;
    font-weight:800;
    opacity:.72;
}
.opportunity-card.compact .opportunity-stock{
    font-size:15px;
    line-height:1.05;
    font-weight:950;
    margin-top:3px;
    color:var(--card-text,#172033);
}
.opportunity-card.compact .opportunity-direction{
    font-size:9px;
    line-height:1;
    font-weight:950;
    color:var(--card-accent,#475569);
}
.opportunity-card.compact .opportunity-state{
    margin-top:4px;
    font-size:8px;
    line-height:1.1;
    font-weight:850;
    color:var(--card-text,#172033);
}
.opportunity-card.compact .opportunity-move-large{
    margin-top:4px;
    font-size:20px;
    line-height:1;
    font-weight:950;
    color:var(--card-accent,#172033);
}
.opportunity-card.compact .opportunity-sr{
    margin-top:4px;
    font-size:8px;
    line-height:1.1;
    font-weight:850;
    color:var(--card-text,#172033);
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.opportunity-card.compact .quality-row{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-top:5px;
    font-size:7px;
    line-height:1;
    font-weight:900;
    color:var(--card-text,#334155);
}
.opportunity-card.compact .quality-meter{
    height:5px;
    margin-top:3px;
    border-radius:999px;
    background:rgba(100,116,139,.20);
    overflow:hidden;
}
.opportunity-card.compact .quality-meter span{
    display:block;
    height:100%;
    border-radius:999px;
    background:var(--card-accent,#64748b);
}
.opportunity-card.compact .quality-caption{
    margin-top:3px;
    font-size:7px;
    line-height:1.1;
    color:var(--card-text,#334155);
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.opportunity-card.compact .setup-outlook{
    margin-top:5px;
    font-size:9px;
    line-height:1.15;
    font-weight:950;
    color:var(--card-text,#172033);
}
.opportunity-card.compact .setup-caution{
    margin-top:2px;
    font-size:8px;
    line-height:1.15;
    color:var(--card-text,#172033);
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.opportunity-card.compact .data-confidence{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-top:4px;
    font-size:7px;
    line-height:1;
    font-weight:800;
    color:var(--card-text,#334155);
}
.opportunity-card.compact .data-confidence b{
    font-size:10px;
    font-weight:950;
}
.opportunity-card.compact .break-caption{
    margin-top:3px;
    font-size:7px;
    line-height:1.1;
    font-weight:850;
    color:var(--card-text,#334155);
}
.opportunity-card.compact .compact-metrics{
    display:grid;
    grid-template-columns:repeat(4,minmax(0,1fr));
    gap:3px;
    margin-top:6px;
}
.opportunity-card.compact .opportunity-metric{
    min-width:0;
    padding:4px 4px;
    border:1px solid rgba(100,116,139,.18);
    border-radius:5px;
    background:rgba(255,255,255,.72);
    color:#172033;
    box-sizing:border-box;
}
.opportunity-card.compact .opportunity-metric-label{
    display:block;
    font-size:6px;
    line-height:1;
    font-weight:900;
    letter-spacing:.2px;
    color:#475569;
}
.opportunity-card.compact .opportunity-metric-value{
    display:block;
    margin-top:3px;
    font-size:9px;
    line-height:1;
    font-weight:950;
    color:#172033;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.opportunity-card.compact .opportunity-metric:last-child .opportunity-metric-value{
    font-size:8px;
}
.opportunity-card.compact .opportunity-reason{
    margin-top:4px;
    font-size:7px;
    line-height:1.1;
    color:var(--card-text,#334155);
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
@media(max-width:1200px){
    .opportunity-grid.compact-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
}
@media(max-width:900px){
    .opportunity-grid.compact-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
}


/* Deployment 29: minimal first-look opportunity cards */
.opportunity-grid.minimal-grid{grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:10px 0 12px}
.opportunity-card.minimal-card{min-height:132px;height:132px;padding:9px 10px;border-radius:8px;display:flex;flex-direction:column;box-sizing:border-box;color:var(--card-text,#172033);overflow:hidden}
.minimal-card .minimal-top{display:flex;justify-content:space-between;align-items:center;font-size:8px;font-weight:850;line-height:1}
.minimal-card .opportunity-rank{opacity:.68;font-size:8px}
.minimal-card .opportunity-direction{font-size:9px;font-weight:950;color:var(--card-accent,#334155)}
.minimal-card .minimal-symbol{margin-top:6px;font-size:18px;line-height:1;font-weight:950;letter-spacing:.15px}
.minimal-card .minimal-move{display:flex;align-items:baseline;gap:8px;margin-top:5px}
.minimal-card .minimal-move span{font-size:21px;line-height:1;font-weight:950;color:var(--card-accent,#172033)}
.minimal-card .minimal-move b{font-size:9px;line-height:1;font-weight:900}
.minimal-card .minimal-sr{display:flex;gap:5px;align-items:baseline;margin-top:6px;font-size:8px;line-height:1.1}
.minimal-card .minimal-sr span{font-weight:800;opacity:.68}
.minimal-card .minimal-sr b{font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.minimal-card .minimal-outlook{margin-top:7px;font-size:10px;line-height:1.05;font-weight:950}
.minimal-card .minimal-caution{margin-top:3px;font-size:8px;line-height:1.15;min-height:18px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;opacity:.9}
.minimal-card .minimal-alert{margin-top:auto;padding-top:6px;border-top:1px solid rgba(100,116,139,.22);display:flex;justify-content:space-between;align-items:center;gap:5px;font-size:7px;line-height:1}
.minimal-card .minimal-alert span{font-weight:850;opacity:.72}
.minimal-card .minimal-alert b{font-size:11px;font-weight:950;letter-spacing:.15px}
@media(max-width:1200px){.opportunity-grid.minimal-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:900px){.opportunity-grid.minimal-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}

.minimal-retrace{margin-top:4px;padding:3px 5px;border-radius:4px;font-size:8px;line-height:1.1;font-weight:950;color:var(--card-accent,#475569);background:rgba(255,255,255,.62);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

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
            "First Alert": candidates.get(
                "first_alert_timestamp",
                pd.Series("", index=candidates.index),
            ).astype(str).str.replace("T", " ", regex=False).str.slice(11, 19).replace("", "—"),
            "Time": candidates.get(
                "observation_timestamp",
                pd.Series("", index=candidates.index),
            ).astype(str).str.slice(11, 19),
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
    # Compact inspection strip: keep the same evidence, but avoid the large
    # metric cards that previously consumed most of the vertical space.
    symbol = str(row.get("symbol", "—"))
    first_alert = str(row.get("first_alert_timestamp", "")).strip()
    first_alert = first_alert.replace("T", " ")[:19] if first_alert else "—"
    state = str(row.get("decision_state", "—"))
    direction = str(row.get("decision_direction", row.get("direction", "—")))
    cells = [
        ("Stock", symbol),
        ("First Alert", first_alert),
        ("State", state.replace("_", " ")),
        ("Evidence", row.get("decision_score", "—")),
        ("Confirm", row.get("confirmation_count", "—")),
        ("S/R", _sr_text(row)),
    ]
    cell_html = "".join(
        f'<div class="inspect-cell"><div class="inspect-label">{label}</div>'
        f'<div class="inspect-value">{value}</div></div>'
        for label, value in cells
    )
    st.markdown(
        f'<div class="inspect-strip"><div class="inspect-title">Decision Evidence — {symbol}</div>'
        f'<div class="inspect-direction">{direction}</div><div class="inspect-grid">{cell_html}</div></div>',
        unsafe_allow_html=True,
    )

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



def _symbol_snapshot_history(snapshot_results: dict[str, pd.DataFrame] | None, symbol: str) -> list[pd.Series]:
    'Return chronological observations for one symbol; diagnostic only.'
    if not isinstance(snapshot_results, dict):
        return []
    target = str(symbol).strip().upper()
    observations = []
    for frame in snapshot_results.values():
        if not isinstance(frame, pd.DataFrame) or frame.empty or 'symbol' not in frame.columns:
            continue
        matches = frame.loc[frame['symbol'].astype(str).str.upper().str.strip().eq(target)]
        for _, row in matches.iterrows():
            ts = pd.to_datetime(row.get('source_timestamp', row.get('observation_timestamp', '')), errors='coerce')
            if pd.notna(ts):
                observations.append((ts.to_pydatetime(), row))
    observations.sort(key=lambda item: item[0])
    return [row for _, row in observations]


def _directional_alignment(row: pd.Series) -> tuple[str, int, int]:
    'Summarise explicit directional language already produced by the engine.'
    direction = str(row.get('decision_direction', row.get('direction', 'NEUTRAL'))).upper()
    fields = ('directional_interpretation','futures_interpretation','options_interpretation','pcr_interpretation','iv_interpretation','volume_interpretation','oi_interpretation')
    supportive = contradictory = 0
    bullish_terms = ('BULLISH','POSITIVE','LONG BUILDUP','SHORT COVERING')
    bearish_terms = ('BEARISH','NEGATIVE','SHORT BUILDUP','LONG UNWINDING')
    for field in fields:
        text = str(row.get(field, '')).upper()
        if not text or text in {'NAN','NONE','—'}:
            continue
        if direction == 'BULLISH':
            supportive += int(any(token in text for token in bullish_terms))
            contradictory += int(any(token in text for token in bearish_terms))
        elif direction == 'BEARISH':
            supportive += int(any(token in text for token in bearish_terms))
            contradictory += int(any(token in text for token in bullish_terms))
    if supportive >= 5 and contradictory == 0:
        label = 'STRONG ALIGNMENT'
    elif supportive >= 3 and contradictory <= 1:
        label = 'ALIGNED'
    elif supportive > contradictory and supportive >= 1:
        label = 'PARTIAL ALIGNMENT'
    elif contradictory > supportive:
        label = 'CONFLICTING'
    else:
        label = 'INSUFFICIENT'
    return label, supportive, contradictory



def _retracement_price(row: pd.Series) -> float | None:
    for key in ("Close", "close", "CMP", "cmp", "current_price", "ltp", "price"):
        value = pd.to_numeric(row.get(key), errors="coerce")
        if pd.notna(value) and float(value) > 0:
            return float(value)
    return None


def _retracement_hl(row: pd.Series) -> tuple[float | None, float | None]:
    def num(*keys: str) -> float | None:
        for key in keys:
            value = pd.to_numeric(row.get(key), errors="coerce")
            if pd.notna(value):
                return float(value)
        return None
    return num("High", "high"), num("Low", "low")


def _retracement_volume(row: pd.Series) -> float | None:
    for key in ("Volume", "volume", "Total Volume", "total_volume"):
        value = pd.to_numeric(row.get(key), errors="coerce")
        if pd.notna(value) and float(value) >= 0:
            return float(value)
    return None


def _prior_day_structural_break(
    state: dict[str, Any],
    trading_date: str,
    symbol: str,
    direction: str,
) -> dict[str, Any] | None:
    """Return a carried structural break from the latest prior trading day.

    The exact break timestamp is used when it was durably recorded. If an
    older state has only the final broken structure and First Alert provenance,
    the break time remains unknown rather than being fabricated.
    """
    days = state.get(STATE_KEY, {}) or {}
    prior_dates = sorted(
        str(day)
        for day in days
        if str(day) < str(trading_date)
    )
    for prior_day in reversed(prior_dates):
        day = days.get(prior_day, {}) or {}
        ledger = day.get("structural_breaks", {}) or {}
        entry = ledger.get(symbol)
        if isinstance(entry, dict):
            if str(entry.get("direction", "")).upper() == direction:
                return {
                    "date": prior_day,
                    "direction": direction,
                    "break_timestamp": str(entry.get("break_timestamp", "")).strip(),
                    "break_level": entry.get("break_level"),
                    "first_alert_timestamp": str(
                        entry.get("first_alert_timestamp", "")
                    ).strip(),
                    "source": "PRIOR DAY STRUCTURAL BREAK",
                }

        # Backward-compatible fallback for states created before the
        # structural-break ledger existed.
        saved = day.get("last_complete_state", {}) or {}
        rows = saved.get("result", [])
        if isinstance(rows, list):
            for saved_row in rows:
                if not isinstance(saved_row, dict):
                    continue
                saved_symbol = str(
                    saved_row.get("symbol", saved_row.get("Symbol", ""))
                ).strip().upper()
                saved_direction = str(
                    saved_row.get(
                        "decision_direction",
                        saved_row.get("direction", "NEUTRAL"),
                    )
                ).upper().strip()
                saved_sr = _sr_text(pd.Series(saved_row)).upper().strip()
                if (
                    saved_symbol == symbol
                    and saved_direction == direction
                    and (
                        (direction == "BULLISH" and saved_sr == "RESISTANCE BROKEN")
                        or (direction == "BEARISH" and saved_sr == "SUPPORT BROKEN")
                    )
                ):
                    first_alert = str(
                        (day.get("first_alerts", {}) or {})
                        .get(symbol, {})
                        .get("timestamp", "")
                    ).strip()
                    legacy_level = (
                        saved_row.get("Resistance")
                        if direction == "BULLISH"
                        else saved_row.get("Support")
                    )
                    try:
                        legacy_level = float(legacy_level)
                    except (TypeError, ValueError):
                        legacy_level = None
                    return {
                        "date": prior_day,
                        "direction": direction,
                        "break_timestamp": "",
                        "break_level": legacy_level,
                        "first_alert_timestamp": first_alert,
                        "source": "PRIOR DAY BROKEN STRUCTURE · BREAK TIME UNKNOWN",
                    }

        # Do not search indefinitely once the latest prior day has no evidence.
        # Continue to the next prior trading day only when it has an explicit
        # durable break ledger.
    return None


def _retracement_context(
    row: pd.Series,
    snapshot_results: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """Evaluate a second-opportunity retracement without changing SDL selection.

    Primary direction and structural break remain authoritative. A retest can
    occur while the current S/R label changes from BROKEN to TEST/APPROACHING;
    requiring the label to remain BROKEN would make a real retest impossible.
    """
    symbol = str(row.get("symbol", "")).strip().upper()
    direction = str(
        row.get("decision_direction", row.get("direction", "NEUTRAL"))
    ).upper().strip()
    history = _symbol_snapshot_history(snapshot_results, symbol)
    if direction not in {"BULLISH", "BEARISH"}:
        return {"status": "UNAVAILABLE", "reason": "missing primary direction"}

    current_ts = pd.to_datetime(
        row.get("source_timestamp", row.get("observation_timestamp", "")),
        errors="coerce",
    )
    current_price = _retracement_price(row)
    high, low = _retracement_hl(row)
    if pd.isna(current_ts) or current_price is None:
        return {"status": "UNAVAILABLE", "reason": "missing price/time"}

    # Find the first qualifying break in the current-day chain.
    break_ts = None
    break_level = None
    break_origin = "CURRENT DAY"
    carried_break = None

    for obs in history:
        obs_dir = str(
            obs.get("decision_direction", obs.get("direction", "NEUTRAL"))
        ).upper().strip()
        sr = _sr_text(obs).upper().strip()
        if obs_dir != direction:
            continue

        is_break = (
            (direction == "BULLISH" and sr == "RESISTANCE BROKEN")
            or (direction == "BEARISH" and sr == "SUPPORT BROKEN")
        )
        if not is_break:
            continue

        ts = pd.to_datetime(
            obs.get("source_timestamp", obs.get("observation_timestamp", "")),
            errors="coerce",
        )
        if pd.isna(ts):
            continue

        break_ts = ts
        if direction == "BULLISH":
            break_level = pd.to_numeric(
                obs.get("Resistance", obs.get("resistance")),
                errors="coerce",
            )
        else:
            break_level = pd.to_numeric(
                obs.get("Support", obs.get("support")),
                errors="coerce",
            )
        break_level = float(break_level) if pd.notna(break_level) else None
        break
    if break_ts is None:
        carried_break = _prior_day_structural_break(
            load_state(STATE_JSON),
            str(current_ts.date()),
            symbol,
            direction,
        )
        if carried_break:
            raw_break = carried_break.get("break_timestamp", "")
            parsed = pd.to_datetime(raw_break, errors="coerce")
            if pd.notna(parsed):
                break_ts = parsed
            else:
                # Legacy state may know the day but not the exact break time.
                # Do not fabricate a historical clock time.
                break_ts = pd.Timestamp(current_ts.normalize())
            break_origin = str(
                carried_break.get("source", "PRIOR DAY STRUCTURAL BREAK")
            )
            carried_level = carried_break.get("break_level")
            try:
                break_level = float(carried_level) if carried_level not in ("", None) else None
            except (TypeError, ValueError):
                break_level = None

    if break_ts is None or current_ts <= break_ts:
        return {"status": "NOT_ACTIVE", "reason": "no completed primary break"}

    # Directional reversal after the primary break invalidates the watch.
    for obs in history:
        ts = pd.to_datetime(
            obs.get("source_timestamp", obs.get("observation_timestamp", "")),
            errors="coerce",
        )
        if pd.isna(ts) or ts <= break_ts or ts > current_ts:
            continue
        obs_dir = str(
            obs.get("decision_direction", obs.get("direction", "NEUTRAL"))
        ).upper().strip()
        if obs_dir in {"BULLISH", "BEARISH"} and obs_dir != direction:
            return {
                "status": "INVALIDATED",
                "reason": "direction changed from primary move",
                "primary_direction": direction,
            }

    # Today's observations only for 15-minute EMA20 and session VWAP.
    today = current_ts.date()
    observations = []
    for obs in history:
        ts = pd.to_datetime(
            obs.get("source_timestamp", obs.get("observation_timestamp", "")),
            errors="coerce",
        )
        price = _retracement_price(obs)
        if pd.isna(ts) or price is None or ts.date() != today or ts > current_ts:
            continue
        observations.append((ts, obs, price))

    # One close per completed 15-minute bucket, using the latest observation.
    bars: dict[pd.Timestamp, tuple[pd.Timestamp, pd.Series, float]] = {}
    for ts, obs, price in observations:
        bars[ts.floor("15min")] = (ts, obs, price)

    bar_items = sorted(bars.items(), key=lambda item: item[0])
    closes = pd.Series(
        [item[1][2] for item in bar_items],
        index=pd.DatetimeIndex([item[0] for item in bar_items]),
        dtype="float64",
    )

    ema20 = None
    ema_ready = len(closes) >= 20
    if ema_ready:
        ema20 = float(
            closes.ewm(span=20, adjust=False, min_periods=20).mean().iloc[-1]
        )

    # Session VWAP: use only today's source rows and convert cumulative volume
    # to increments when the input is cumulative.
    vwap = None
    volumes = [_retracement_volume(obs) for _, obs, _ in observations]
    if volumes and all(v is not None for v in volumes):
        vals = [float(v) for v in volumes]
        cumulative = all(vals[i] >= vals[i - 1] for i in range(1, len(vals)))
        effective = (
            [vals[0]] + [max(0.0, vals[i] - vals[i - 1]) for i in range(1, len(vals))]
            if cumulative
            else [max(0.0, v) for v in vals]
        )
        total = sum(effective)
        if total > 0:
            weighted = 0.0
            for (_, obs, price), vol in zip(observations, effective):
                h = pd.to_numeric(obs.get("High", obs.get("high")), errors="coerce")
                l = pd.to_numeric(obs.get("Low", obs.get("low")), errors="coerce")
                typical = float((h + l + price) / 3) if pd.notna(h) and pd.notna(l) else price
                weighted += typical * vol
            vwap = weighted / total

    levels: list[tuple[str, float]] = []
    if ema20 is not None:
        levels.append(("15m 20 EMA", ema20))
    if vwap is not None:
        levels.append(("VWAP", float(vwap)))
    if break_level is not None:
        levels.append(("BROKEN S/R", break_level))

    if not levels:
        return {
            "status": "UNAVAILABLE",
            "reason": (
                "no usable retracement reference yet; "
                "15m EMA20 warming up and session VWAP unavailable"
            ),
            "ema_ready": ema_ready,
            "bar_count": len(closes),
            "break_origin": break_origin,
            "break_timestamp": break_ts.to_pydatetime() if break_ts is not None else None,
            "break_level": break_level,
            "primary_direction": direction,
        }

    # Prefer the closest valid retest reference that is on the retracement side
    # of current price. This avoids selecting a level that is already behind the
    # move in the wrong direction.
    if direction == "BULLISH":
        valid = [(name, level) for name, level in levels if level <= current_price]
    else:
        valid = [(name, level) for name, level in levels if level >= current_price]
    candidate_levels = valid or levels
    entry_name, entry_level = min(
        candidate_levels, key=lambda item: abs(current_price - item[1])
    )

    touched = (
        high is not None
        and low is not None
        and low <= entry_level <= high
    )

    # For a retracement, the current S/R label may legitimately be TEST,
    # APPROACHING, or another non-broken state. What matters is that the
    # primary direction has not reversed and the historical break exists.
    status = "REENTRY ALERT" if touched else "WATCH"

    return {
        "status": status,
        "reason": (
            f"{entry_name} retest reached with {direction.lower()} bias intact"
            if touched
            else f"watch {entry_name} retest for {direction.lower()} re-entry"
        ),
        "primary_direction": direction,
        "entry_name": entry_name,
        "entry_level": float(entry_level),
        "ema20": ema20,
        "ema_ready": ema_ready,
        "bar_count": len(closes),
        "vwap": vwap,
        "touched": bool(touched),
        "current_price": current_price,
        "break_timestamp": break_ts.to_pydatetime(),
        "break_level": break_level,
        "break_origin": break_origin,
        "carried_break_date": carried_break.get("date", "") if carried_break else "",
        "carried_first_alert_timestamp": (
            carried_break.get("first_alert_timestamp", "") if carried_break else ""
        ),
    }


def _setup_readiness_diagnostic(
    row: pd.Series,
    snapshot_results: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """Timeliness-aware setup diagnostic; presentation-only.

    The critical distinction is:
      * a setup is developing BEFORE/AT a level test,
      * a break is a trigger,
      * a mature post-break move is NOT a new setup.

    This does not alter candidate selection, ranking, SDL scoring, S/R
    calculations, or any engine output.
    """
    direction = str(
        row.get("decision_direction", row.get("direction", "NEUTRAL"))
    ).upper().strip()
    sr = _sr_text(row).upper().strip()

    move = pd.to_numeric(
        row.get("price_change_pct", row.get("move_pct", 0)), errors="coerce"
    )
    move_abs = 0.0 if pd.isna(move) else abs(float(move))

    alignment, supportive, contradictory = _directional_alignment(row)
    conflict = int(_num(row.get("conflict_count")) or 0)

    # Structural state is the primary lifecycle signal. Do not infer "new
    # setup" merely because this is the first row available to the renderer.
    approaching = sr in {"APPROACHING RESISTANCE", "APPROACHING SUPPORT"}
    testing = sr in {"RESISTANCE TEST", "SUPPORT TEST"}
    bullish_break = direction == "BULLISH" and sr == "RESISTANCE BROKEN"
    bearish_break = direction == "BEARISH" and sr == "SUPPORT BROKEN"
    broken = bullish_break or bearish_break

    if approaching:
        level_points = 30
        level_label = "LEVEL APPROACHING"
    elif testing:
        level_points = 34
        level_label = "LEVEL TEST"
    elif broken:
        # A break is important, but it is no longer an early setup.
        level_points = 26
        level_label = "BREAK DETECTED"
    else:
        level_points = 0
        level_label = "NO IMMEDIATE STRUCTURAL SETUP"

    alignment_points = min(25, supportive * 4)
    alignment_points = max(0, alignment_points - contradictory * 5)

    evidence = pd.to_numeric(row.get("decision_score", 0), errors="coerce")
    evidence_points = (
        0 if pd.isna(evidence)
        else min(15, max(0.0, float(evidence)) * 0.15)
    )

    confirm = pd.to_numeric(row.get("confirmation_count", 0), errors="coerce")
    confirm_points = (
        0 if pd.isna(confirm)
        else min(10, max(0.0, float(confirm)) * 0.75)
    )

    conflict_points = 10 if conflict == 0 else 5 if conflict == 1 else 0

    # Timeliness is intentionally capped. Large price movement reduces
    # "entry readiness"; it must never make a mature move look like a fresh
    # setup.
    if move_abs <= 0.50:
        timing_points, timing_label = 12, "EARLY"
    elif move_abs <= 1.00:
        timing_points, timing_label = 10, "EARLY / ACTIVE"
    elif move_abs <= 1.50:
        timing_points, timing_label = 8, "ACTIVE"
    elif move_abs <= 2.50:
        timing_points, timing_label = 5, "LATE / ACTIVE"
    elif move_abs <= 4.00:
        timing_points, timing_label = 2, "MATURE MOVE"
    else:
        timing_points, timing_label = 0, "HIGHLY EXTENDED"

    readiness = int(max(0, min(100, round(
        level_points + alignment_points + evidence_points +
        confirm_points + conflict_points + timing_points
    ))))

    # Chronology is used only to describe the lifecycle, never to create a
    # new candidate. A broken stock with a large move is explicitly post-break.
    history = _symbol_snapshot_history(snapshot_results, str(row.get("symbol", "")))
    current_ts = pd.to_datetime(
        row.get("source_timestamp", row.get("observation_timestamp", "")),
        errors="coerce",
    )

    prior_structural = []
    if pd.notna(current_ts):
        for obs in history:
            obs_ts = pd.to_datetime(
                obs.get("source_timestamp", obs.get("observation_timestamp", "")),
                errors="coerce",
            )
            if pd.notna(obs_ts) and obs_ts < current_ts:
                prior_structural.append(_sr_text(obs).upper().strip())

    if broken:
        if move_abs > 4.0:
            stage = "POST-BREAK · HIGHLY EXTENDED"
        elif move_abs > 2.5:
            stage = "POST-BREAK · MATURE"
        elif prior_structural:
            stage = "BREAK TRIGGER · FOLLOW-UP"
        else:
            stage = "BREAK TRIGGER · FIRST OBSERVATION"
    elif testing:
        stage = "TESTING · ENTRY WINDOW"
    elif approaching:
        stage = "APPROACHING · EARLY WATCH"
    elif sr in {"RESISTANCE REJECTED", "SUPPORT REJECTED"}:
        stage = "REJECTION · RETRACE / BOUNCE WATCH"
    else:
        stage = "DIRECTIONAL · WAIT FOR LEVEL"

    if approaching or testing:
        label = (
            "HIGH READINESS" if readiness >= 80
            else "GOOD READINESS" if readiness >= 65
            else "WATCH" if readiness >= 50
            else "EARLY / INSUFFICIENT"
        )
    elif broken:
        # This is deliberately not allowed to be interpreted as fresh setup
        # quality. It describes readiness for the NEXT valid entry condition.
        label = (
            "CONFIRMATION STRONG" if readiness >= 75
            else "CONFIRMATION WATCH" if readiness >= 55
            else "LATE / CAUTION"
        )
    else:
        label = "WATCH"

    reasons = []
    if approaching:
        reasons.append("level approaching")
    elif testing:
        reasons.append("level being tested")
    elif broken:
        reasons.append("break already detected")

    if alignment == "STRONG ALIGNMENT":
        reasons.append(f"{supportive} supporting inputs aligned")
    elif alignment == "ALIGNED":
        reasons.append(f"{supportive} supporting inputs")
    elif alignment == "CONFLICTING":
        reasons.append(f"{contradictory} conflicting inputs")
    elif alignment == "INSUFFICIENT":
        reasons.append("limited directional evidence")

    if timing_label in {"EARLY", "EARLY / ACTIVE"}:
        reasons.append("move not yet mature")
    elif timing_label in {"MATURE MOVE", "HIGHLY EXTENDED"}:
        reasons.append("entry timing is late")

    if conflict:
        reasons.append(f"{conflict} conflict{'s' if conflict != 1 else ''}")

    lifecycle = _alert_lifecycle_diagnostic(row, snapshot_results)
    return {
        "readiness": readiness,
        "label": label,
        "level_label": level_label,
        "timing_label": timing_label,
        "stage": stage,
        "alignment": alignment,
        "supportive": supportive,
        "contradictory": contradictory,
        "reason": " · ".join(reasons) if reasons else "existing engine evidence only",
        "first_alert": lifecycle["first_alert"],
        "freshness": lifecycle["freshness"],
        "age_minutes": lifecycle["age_minutes"],
    }


def _alert_lifecycle_diagnostic(
    row: pd.Series,
    snapshot_results: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """Timestamp-first lifecycle diagnostic; presentation/state interpretation only.

    First Alert is the immutable timestamp of the first qualifying event.
    Current event time and retracement/re-entry times are separate events.
    This function never changes candidate selection or SDL scoring.
    """
    symbol = str(row.get("symbol", "")).strip().upper()
    current_ts = pd.to_datetime(
        row.get("source_timestamp", row.get("observation_timestamp", "")),
        errors="coerce",
    )
    first_ts = pd.to_datetime(
        row.get("first_alert_timestamp", ""),
        errors="coerce",
    )

    # Durable state is authoritative when the row does not carry First Alert.
    if pd.isna(first_ts):
        try:
            _day_raw = st.session_state.get("ds_trading_date", "")
            trading_day = (
                _day_raw.strftime("%Y-%m-%d")
                if hasattr(_day_raw, "strftime")
                else str(_day_raw).strip()[:10]
            )
            state_day = load_state(STATE_JSON).get(STATE_KEY, {}).get(trading_day, {}) or {}
            alert = (state_day.get("first_alerts", {}) or {}).get(symbol, {}) or {}
            first_ts = pd.to_datetime(alert.get("timestamp", ""), errors="coerce")
        except Exception:
            pass

    age = None
    if pd.notna(first_ts) and pd.notna(current_ts):
        age = max(0.0, (current_ts - first_ts).total_seconds() / 60.0)

    if age is None:
        freshness = "TIME UNKNOWN"
    elif age <= 10:
        freshness = "FRESH · ≤10M"
    elif age <= 30:
        freshness = "ACTIVE · ≤30M"
    elif age <= 60:
        freshness = "AGING · ≤60M"
    else:
        freshness = "ORIGINAL ENTRY PASSED"

    return {
        "first_alert": first_ts.strftime("%H:%M:%S") if pd.notna(first_ts) else "—",
        "current_event": current_ts.strftime("%H:%M:%S") if pd.notna(current_ts) else "—",
        "age_minutes": age,
        "freshness": freshness,
    }


def _setup_outlook_diagnostic(row: pd.Series) -> dict[str, Any]:
    """Trader-facing early-entry outlook; diagnostic only."""
    direction = str(
        row.get("decision_direction", row.get("direction", "NEUTRAL"))
    ).upper().strip()
    sr = _sr_text(row).upper().strip()
    move = pd.to_numeric(
        row.get("price_change_pct", row.get("move_pct", 0)), errors="coerce"
    )
    move_abs = 0.0 if pd.isna(move) else abs(float(move))

    alignment, supportive, contradictory = _directional_alignment(row)
    conflict_count = int(_num(row.get("conflict_count")) or 0)

    # Evidence-basis confidence remains about evidence quality, not movement
    # probability.
    evidence_fields = (
        "directional_interpretation",
        "futures_interpretation",
        "options_interpretation",
        "pcr_interpretation",
        "iv_interpretation",
        "volume_interpretation",
        "oi_interpretation",
    )
    populated = sum(
        1 for field in evidence_fields
        if str(row.get(field, "")).strip().upper() not in {"", "NAN", "NONE", "—"}
    )
    completeness = round((populated / len(evidence_fields)) * 35)

    if supportive >= 5 and contradictory == 0:
        agreement = 40
    elif supportive >= 3 and contradictory <= 1:
        agreement = 32
    elif supportive >= 2 and contradictory <= 2:
        agreement = 22
    elif supportive > contradictory:
        agreement = 14
    else:
        agreement = 5

    conflict_quality = 20 if conflict_count == 0 else 10 if conflict_count == 1 else 0
    data_confidence = max(0, min(100, completeness + agreement + conflict_quality))

    # Timing gate for interpretation only: large moves are explicitly late.
    extended = move_abs > 2.50
    highly_extended = move_abs > 4.00

    if direction == "BULLISH" and sr == "APPROACHING RESISTANCE":
        if highly_extended:
            outlook = "RETRACE RISK"
            caution = "resistance overhead · move already highly extended"
        elif supportive >= 4 and contradictory <= 1:
            outlook = "BREAKOUT WATCH"
            caution = "resistance overhead · evidence supports a break attempt"
        else:
            outlook = "RETRACE RISK"
            caution = "resistance overhead · evidence not strong enough yet"

    elif direction == "BULLISH" and sr == "RESISTANCE TEST":
        if extended:
            outlook = "BREAKOUT CAUTION"
            caution = "resistance test · move is already extended; avoid chasing"
        elif supportive >= 4 and contradictory <= 1:
            outlook = "BREAKOUT SETUP"
            caution = "resistance test · evidence aligned"
        else:
            outlook = "RETRACE RISK"
            caution = "resistance test · mixed evidence"

    elif direction == "BEARISH" and sr == "APPROACHING SUPPORT":
        if highly_extended:
            outlook = "BOUNCE RISK"
            caution = "support below · move already highly extended"
        elif supportive >= 4 and contradictory <= 1:
            outlook = "BREAKDOWN WATCH"
            caution = "support below · evidence supports a break attempt"
        else:
            outlook = "BOUNCE RISK"
            caution = "support below · evidence not strong enough yet"

    elif direction == "BEARISH" and sr == "SUPPORT TEST":
        if extended:
            outlook = "BREAKDOWN CAUTION"
            caution = "support test · move is already extended; avoid chasing"
        elif supportive >= 4 and contradictory <= 1:
            outlook = "BREAKDOWN SETUP"
            caution = "support test · evidence aligned"
        else:
            outlook = "BOUNCE RISK"
            caution = "support test · mixed evidence"

    elif direction == "BULLISH" and sr == "RESISTANCE BROKEN":
        if highly_extended:
            outlook = "BREAKOUT — LATE"
            caution = "resistance broken · move highly extended; wait for retest/hold"
        elif extended:
            outlook = "BREAKOUT — CAUTION"
            caution = "resistance broken · move extended; confirmation preferred"
        else:
            outlook = "BREAKOUT CONFIRMATION"
            caution = "resistance broken · wait for subsequent hold"

    elif direction == "BEARISH" and sr == "SUPPORT BROKEN":
        if highly_extended:
            outlook = "BREAKDOWN — LATE"
            caution = "support broken · move highly extended; wait for retest/hold"
        elif extended:
            outlook = "BREAKDOWN — CAUTION"
            caution = "support broken · move extended; confirmation preferred"
        else:
            outlook = "BREAKDOWN CONFIRMATION"
            caution = "support broken · wait for subsequent hold"

    elif direction == "BULLISH":
        outlook = "BULLISH · WAIT FOR LEVEL"
        caution = "direction positive · no immediate structural trigger"

    elif direction == "BEARISH":
        outlook = "BEARISH · WAIT FOR LEVEL"
        caution = "direction negative · no immediate structural trigger"

    else:
        outlook = "WAIT FOR STRUCTURE"
        caution = "direction or level evidence is insufficient"

    data_label = (
        "HIGH DATA CONFIDENCE" if data_confidence >= 80
        else "GOOD DATA CONFIDENCE" if data_confidence >= 65
        else "MODERATE DATA CONFIDENCE" if data_confidence >= 50
        else "LOW DATA CONFIDENCE"
    )

    return {
        "outlook": outlook,
        "caution": caution,
        "data_confidence": data_confidence,
        "data_label": data_label,
        "supportive": supportive,
        "contradictory": contradictory,
        "alignment": alignment,
    }


def _break_quality_diagnostic(row: pd.Series, snapshot_results: dict[str, pd.DataFrame] | None = None) -> dict[str, Any]:
    'Diagnostic break-quality view; never feeds candidate selection or score.'
    sr = _sr_text(row).upper()
    direction = str(row.get('decision_direction', row.get('direction', 'NEUTRAL'))).upper()
    symbol = str(row.get('symbol', '')).upper().strip()
    history = _symbol_snapshot_history(snapshot_results, symbol)
    broken_status = 'RESISTANCE BROKEN' if direction == 'BULLISH' else 'SUPPORT BROKEN' if direction == 'BEARISH' else ''
    sustain_label = 'NOT A STRUCTURAL BREAK'
    sustain_points = 0
    if broken_status and sr == broken_status:
        first_idx = next((i for i, obs in enumerate(history) if _sr_text(obs).upper() == broken_status), None)
        if first_idx is None:
            sustain_label, sustain_points = 'BREAK PRESENT · HISTORY UNAVAILABLE', 8
        else:
            tail = history[first_idx:]
            checks_after = max(0, len(tail) - 1)
            statuses = [_sr_text(obs).upper() for obs in tail]
            if checks_after == 0:
                sustain_label, sustain_points = 'NEW BREAK · NOT YET TESTED', 10
            elif all(value == broken_status for value in statuses):
                sustain_label, sustain_points = f'SUSTAINED · {checks_after} FOLLOW-UP CHECKS', (25 if checks_after >= 2 else 18)
            elif statuses[-1] == broken_status:
                sustain_label, sustain_points = 'RECLAIMED · BREAK RE-ESTABLISHED', 15
            else:
                sustain_label, sustain_points = 'BREAK WEAKENED / RETESTED', 5
    alignment, supportive, contradictory = _directional_alignment(row)
    conflict = int(_num(row.get('conflict_count')) or 0)
    structural_points = 30 if sr == broken_status and broken_status else 0
    alignment_points = min(25, supportive * 4) if alignment != 'INSUFFICIENT' else 0
    conflict_points = 20 if conflict == 0 else 10 if conflict == 1 else 0
    quality = max(0, min(100, structural_points + sustain_points + alignment_points + conflict_points))
    if quality >= 80 and alignment in {'STRONG ALIGNMENT','ALIGNED'}:
        quality_label = 'STRONG DATA'
    elif quality >= 60:
        quality_label = 'GOOD DATA'
    elif quality >= 40:
        quality_label = 'MIXED DATA'
    else:
        quality_label = 'INSUFFICIENT DATA'
    reasons = []
    if broken_status and sr == broken_status:
        reasons.append('level break detected')
    if sustain_label.startswith('SUSTAINED'):
        reasons.append(sustain_label.lower())
    elif sustain_label.startswith('NEW BREAK'):
        reasons.append('sustainability not yet proven')
    elif 'RETESTED' in sustain_label:
        reasons.append('break has been retested')
    elif 'RECLAIMED' in sustain_label:
        reasons.append('break re-established after a pullback')
    if alignment == 'STRONG ALIGNMENT': reasons.append(f'{supportive} derivative/participation inputs aligned')
    elif alignment == 'ALIGNED': reasons.append(f'{supportive} supporting inputs aligned')
    elif alignment == 'CONFLICTING': reasons.append(f'{contradictory} conflicting inputs')
    elif alignment == 'INSUFFICIENT': reasons.append('limited supporting data')
    if conflict == 0: reasons.append('no recorded conflicts')
    elif conflict > 0: reasons.append(f'{conflict} conflict{"s" if conflict != 1 else ""}')
    return {'quality': quality, 'quality_label': quality_label, 'sustain_label': sustain_label, 'alignment': alignment, 'supportive': supportive, 'contradictory': contradictory, 'reason': ' · '.join(reasons) if reasons else 'Existing engine evidence only'}

def _opportunity_palette(row: pd.Series) -> tuple[str, str, str]:
    """Continuous visual grading using existing decision score/strength only."""
    direction = str(
        row.get("decision_direction", row.get("direction", "NEUTRAL"))
    ).upper()
    state = str(row.get("decision_state", "")).upper()

    score = pd.to_numeric(row.get("decision_score", 0), errors="coerce")
    score = 0.0 if pd.isna(score) else max(0.0, min(100.0, float(score)))

    strength = str(row.get("decision_strength", "")).upper()
    strength_bonus = next(
        (
            value for key, value in {
                "VERY_STRONG": 4.0,
                "STRONG": 2.5,
                "ACTIVE": 1.5,
                "DEVELOPING": 0.5,
            }.items()
            if key in strength or key in state
        ),
        0.0,
    )
    grade = max(0.0, min(100.0, score * 0.94 + strength_bonus))
    ratio = (grade / 100.0) * 0.72

    if direction == "BULLISH":
        light, dark, accent = (236, 253, 245), (20, 83, 45), (22, 163, 74)
    elif direction == "BEARISH":
        light, dark, accent = (254, 242, 242), (127, 29, 29), (220, 38, 38)
    else:
        light, dark, accent = (248, 250, 252), (51, 65, 85), (79, 70, 229)

    bg = tuple(round(light[i] + (dark[i] - light[i]) * ratio) for i in range(3))
    return (
        "#{:02x}{:02x}{:02x}".format(*bg),
        "#{:02x}{:02x}{:02x}".format(*accent),
        "#ffffff" if grade >= 78 else "#0f172a",
    )



def _render_opportunity_cards(
    candidates: pd.DataFrame,
    limit: int = 10,
    snapshot_results: dict[str, pd.DataFrame] | None = None,
) -> None:
    'Minimal first-look cards; detailed evidence remains in the inspector/table.'
    if candidates.empty:
        st.info('No stock currently meets the primary decision-visibility criteria.')
        return
    cards=[]
    for rank, (_, row) in enumerate(candidates.head(limit).iterrows(), start=1):
        bg, accent, text_color = _opportunity_palette(row)
        symbol=html.escape(str(row.get('symbol','—')).upper())
        direction=str(row.get('decision_direction',row.get('direction','NEUTRAL'))).upper()
        strength=str(row.get('decision_strength','—')).replace('_',' ')
        move=pd.to_numeric(row.get('price_change_pct',row.get('move_pct',0)),errors='coerce')
        lifecycle=_alert_lifecycle_diagnostic(row,snapshot_results)
        first=lifecycle['first_alert']
        if first == '—':
            try:
                trading_day = str(st.session_state.get('ds_trading_date','')).strip()
                symbol_key = str(row.get('symbol','')).strip().upper()
                state_day = load_state(STATE_JSON).get(STATE_KEY, {}).get(trading_day, {}) or {}
                durable_alert = (state_day.get('first_alerts', {}) or {}).get(symbol_key, {}) or {}
                durable_ts = str(durable_alert.get('timestamp','')).strip()
                if durable_ts:
                    first = durable_ts.replace('T',' ')[11:19]
            except Exception:
                pass
        sr=_sr_text(row)
        outlook=_setup_outlook_diagnostic(row)
        retrace=_retracement_context(row, snapshot_results)
        move_text='—' if pd.isna(move) else f'{float(move):+.2f}%'
        outlook_text=html.escape(outlook['outlook'])
        caution_text=html.escape(outlook['caution'])
        retrace_html=''
        if retrace.get('status') in {'WATCH','REENTRY ALERT'}:
            rlabel='RE-ENTRY ALERT' if retrace.get('status') == 'REENTRY ALERT' else 'RETRACE WATCH'
            rlevel=retrace.get('entry_level')
            rlevel_text=(f" · {retrace.get('entry_name')} {rlevel:.2f}"
                         if isinstance(rlevel,(int,float)) else '')
            origin=str(retrace.get('break_origin','')).strip()
            retrace_html=f'<div class="minimal-retrace">{rlabel}{html.escape(rlevel_text)}</div>'
            if origin.startswith('PRIOR DAY'):
                retrace_html += '<div class="minimal-retrace-origin">PRIOR-DAY BREAK CARRIED</div>'
        cards.append(f"""<div class="opportunity-card compact minimal-card" style="--card-bg:{bg};--card-accent:{accent};--card-text:{text_color};">
<div class="minimal-top"><span class="opportunity-rank">RANK {rank}</span><span class="opportunity-direction">{direction}</span></div>
<div class="minimal-symbol">{symbol}</div>
<div class="minimal-move"><span>{move_text}</span><b>{html.escape(strength)}</b></div>
<div class="minimal-sr"><span>S/R</span><b>{html.escape(sr)}</b></div>
<div class="minimal-outlook">{outlook_text}</div>
<div class="minimal-caution" title="{caution_text}">{caution_text}</div>
{retrace_html}
<div class="minimal-alert"><span>FIRST ALERT</span><b>{html.escape(first)}</b></div>
</div>""")
    st.markdown('<div class="opportunity-grid compact-grid minimal-grid">'+''.join(cards)+'</div>',unsafe_allow_html=True)

def _render_live_queue(candidates: pd.DataFrame, snapshot_results: dict[str, pd.DataFrame] | None = None) -> None:
    'Recent first-alert queue; presentation only.'
    if candidates is None or candidates.empty or 'first_alert_timestamp' not in candidates.columns:
        return
    work=candidates.copy(); work['_first']=pd.to_datetime(work['first_alert_timestamp'],errors='coerce')
    work=work.dropna(subset=['_first']).sort_values('_first',ascending=False).head(8)
    if work.empty: return
    tiles=[]
    for _,row in work.iterrows():
        bg,accent,_=_opportunity_palette(row)
        symbol=html.escape(str(row.get('symbol','—')).upper())
        direction=str(row.get('decision_direction',row.get('direction','NEUTRAL'))).upper()
        strength=str(row.get('decision_strength',row.get('decision_state','—'))).replace('_',' ')
        move=pd.to_numeric(row.get('price_change_pct',0),errors='coerce')
        move_text='—' if pd.isna(move) else f'{float(move):+.2f}%'
        setup_q=_setup_readiness_diagnostic(row,snapshot_results)
        outlook_q=_setup_outlook_diagnostic(row)
        lifecycle_q=_alert_lifecycle_diagnostic(row,snapshot_results)
        quality=int(setup_q['readiness'])
        tiles.append(f'''<div class="live-queue-tile" style="--queue-bg:{bg};--queue-accent:{accent};"><div class="queue-head"><b>{symbol}</b><span>{direction}</span></div><div class="queue-state">{html.escape(strength.title())}</div><div class="queue-move">{move_text}</div><div class="queue-quality"><span style="width:{quality}%"></span></div><div class="queue-foot"><span>{html.escape(outlook_q['outlook'])} · {quality}%</span><span>First {html.escape(lifecycle_q['first_alert'])}</span></div></div>''')
    st.markdown('<div class="live-queue-panel"><div class="live-queue-title">LIVE QUEUE · RECENT FIRST ALERTS</div><div class="live-queue-sub">Direction + strength colour coded · diagnostic quality only · existing selection unchanged</div><div class="live-queue-grid">'+''.join(tiles)+'</div></div>',unsafe_allow_html=True)


def _render_processing_output(
    result: pd.DataFrame,
    processed_time: datetime,
    source_path: Path,
    snapshot_results: dict[str, pd.DataFrame] | None = None,
) -> None:
    """Show the actual output produced from the latest processed snapshot.

    This is an audit/processing view, not a second decision engine. It exposes
    the rows returned by the existing processing pipeline while keeping the
    decision board itself unchanged.
    """
    if result is None or not isinstance(result, pd.DataFrame) or result.empty:
        return

    candidates = _rank(result)
    gate_passed = int(
        result.get(
            "gate_passed",
            pd.Series(False, index=result.index),
        ).map(_bool).sum()
    )

    with st.expander(
        f"Processing Output • {processed_time:%H:%M:%S} • latest processed snapshot",
        expanded=False,
    ):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Processed rows", len(result))
        c2.metric("Primary gate passed", gate_passed)
        c3.metric("Decision candidates", len(candidates))
        c4.metric("Processing status", "COMPLETE")

        st.caption(
            "Dashboard decision output is filtered by the existing SDL selection logic; "
            "the underlying engine result is unchanged."
        )
        st.caption(f"Source: {source_path.name}")

        preferred = [
            'observation_timestamp', 'first_alert_timestamp', 'symbol',
            'price_change_pct', 'decision_direction', 'decision_state',
            'decision_score', 'decision_strength', 'confirmation_count',
            'conflict_count', 'sr_status', 'gate_passed',
            '_setup_readiness', '_break_confirmation', '_diagnostic_quality',
        ]
        display_source = candidates.copy()
        display_source['_setup_readiness'] = display_source.apply(
            lambda row: _setup_readiness_diagnostic(row, snapshot_results).get('readiness', 0),
            axis=1,
        )
        display_source['_break_confirmation'] = display_source.apply(
            lambda row: _break_quality_diagnostic(row, snapshot_results).get('sustain_label', '—'),
            axis=1,
        )
        display_source['_diagnostic_quality'] = display_source.apply(
            lambda row: _break_quality_diagnostic(row, snapshot_results).get('quality', 0),
            axis=1,
        )
        columns = [c for c in preferred if c in display_source.columns]
        if columns:
            # IMPORTANT: Processing Output is a dashboard presentation surface.
            # The engine still processes every evaluated symbol, but the primary
            # table shown here must use the SAME established candidate pool as
            # Current Decision Opportunities.  No second filter is created.
            output_source = display_source.copy()
            output = output_source.loc[:, columns].copy()
            rename = {
                "observation_timestamp": "Time",
                "first_alert_timestamp": "First Alert",
                "symbol": "Stock",
                "price_change_pct": "Move %",
                "decision_direction": "Direction",
                "decision_state": "Decision",
                "decision_score": "Evidence",
                "decision_strength": "Strength",
                "confirmation_count": "Confirm",
                "conflict_count": "Conflict",
                "sr_status": "S/R",
                "gate_passed": "Gate",
                "_setup_readiness": "Setup Readiness",
                "_break_confirmation": "Break Confirmation",
                "_diagnostic_quality": "Break Quality",
            }
            output = output.rename(columns=rename)
            output["Reason"] = output_source.apply(lambda row: _break_quality_diagnostic(row, snapshot_results).get("reason", "Existing engine evidence only"), axis=1).values
            for timestamp_col in ["Time", "First Alert"]:
                if timestamp_col in output.columns:
                    output[timestamp_col] = (
                        pd.to_datetime(
                            output[timestamp_col],
                            errors="coerce",
                        )
                        .dt.strftime("%H:%M:%S")
                        .fillna("—")
                    )
            def _style_live_output(data: pd.DataFrame) -> pd.io.formats.style.Styler:
                def _row_style(row: pd.Series) -> list[str]:
                    direction = str(row.get("Direction", "")).upper()
                    try:
                        quality = float(row.get("Break Quality", 0))
                    except (TypeError, ValueError):
                        quality = 0.0
                    quality = max(0.0, min(100.0, quality))
                    if direction == "BULLISH":
                        base = (240, 253, 244)
                        hi = (187, 247, 208)
                        accent = "#15803d"
                    elif direction == "BEARISH":
                        base = (255, 245, 245)
                        hi = (254, 202, 202)
                        accent = "#dc2626"
                    else:
                        base = (248, 250, 252)
                        hi = (226, 232, 240)
                        accent = "#475569"
                    ratio = quality / 100.0 * 0.72
                    bg = "#{:02x}{:02x}{:02x}".format(*tuple(round(base[i] + (hi[i] - base[i]) * ratio) for i in range(3)))
                    styles = [f"background-color:{bg};color:#0f172a;font-weight:650"] * len(row)
                    for col in ["Direction", "Decision", "S/R", "Move %", "Break Quality"]:
                        if col in row.index:
                            styles[row.index.get_loc(col)] = f"background-color:{bg};color:{accent};font-weight:900"
                    if "Gate" in row.index:
                        gate = str(row.get("Gate", "")).lower()
                        styles[row.index.get_loc("Gate")] = (
                            "background-color:#dcfce7;color:#15803d;font-weight:950;text-align:center"
                            if gate in {"true", "1", "yes"} else
                            "background-color:#fee2e2;color:#b91c1c;font-weight:900;text-align:center"
                        )
                    return styles
                return data.style.apply(_row_style, axis=1).set_properties(**{"font-size":"11px"})

            st.dataframe(
                _style_live_output(output),
                use_container_width=True,
                hide_index=True,
            )

            with st.expander(
                f"Full engine evaluation audit • {len(result)} rows",
                expanded=False,
            ):
                st.caption(
                    "Audit only. These are all rows processed by the existing SDL engine; "
                    "they are not the dashboard decision pool."
                )
                # Build the audit view from the full engine result.  The
                # diagnostic column exists only on the dashboard display copy,
                # so add it explicitly before selecting audit columns.
                audit_source = result.copy()
                audit_source['_diagnostic_quality'] = audit_source.apply(
                    lambda row: _break_quality_diagnostic(row, snapshot_results).get('quality', 0),
                    axis=1,
                )
                audit_columns = [c for c in columns if c in audit_source.columns]
                if 'decision_reason' in result.columns and 'decision_reason' not in audit_columns:
                    audit_columns.append('decision_reason')
                audit = audit_source.loc[:, audit_columns].copy()
                audit = audit.rename(columns=rename)
                for timestamp_col in ["Time", "First Alert"]:
                    if timestamp_col in audit.columns:
                        audit[timestamp_col] = (
                            pd.to_datetime(audit[timestamp_col], errors="coerce")
                            .dt.strftime("%H:%M:%S")
                            .fillna("—")
                        )
                st.dataframe(
                    audit,
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.dataframe(
                candidates,
                use_container_width=True,
                hide_index=True,
            )



def _render_retracement_lifecycle(
    result: pd.DataFrame,
    snapshot_results: dict[str, pd.DataFrame] | None = None,
    widget_key_prefix: str = "",
) -> None:
    """Render the second-opportunity lifecycle as an auditable dashboard view.

    This view is diagnostic/operational visibility only. It never changes the
    frozen SDL candidate selection or ranking.
    """
    if result is None or not isinstance(result, pd.DataFrame) or result.empty:
        return

    # The dashboard date input may be a datetime.date rather than a string.
    raw_date = st.session_state.get("ds_trading_date", "")
    trading_date = (
        raw_date.strftime("%Y-%m-%d")
        if hasattr(raw_date, "strftime")
        else str(raw_date).strip()[:10]
    )
    try:
        day = load_state(STATE_JSON).get(STATE_KEY, {}).get(trading_date, {}) or {}
    except Exception:
        day = {}

    watches = day.get("retracement_watches", {}) or {}
    alerts = day.get("retracement_alerts", {}) or {}
    breaks = day.get("structural_breaks", {}) or {}
    first_alerts = day.get("first_alerts", {}) or {}

    # The retracement engine needs the COMPLETE chronological snapshot chain.
    # LIVE can legitimately hold only the latest durable result after a restart,
    # so the audit must repair an incomplete in-memory replay cache once. This
    # is a cache/replay concern only; it never changes candidate selection.
    if isinstance(snapshot_results, dict):
        usable_count = sum(
            1
            for frame in snapshot_results.values()
            if isinstance(frame, pd.DataFrame) and not frame.empty
        )
    else:
        usable_count = 0

    # NON-BLOCKING RULE:
    # The Retracement Audit renderer must never trigger a full-day replay
    # reconstruction. The normal LIVE processing path owns replay-cache
    # hydration. If that cache is not ready, this section remains visible from
    # durable lifecycle state and reports the currently available observation
    # count instead of blocking the dashboard render.
    if isinstance(snapshot_results, dict):
        usable_count = sum(
            1
            for frame in snapshot_results.values()
            if isinstance(frame, pd.DataFrame) and not frame.empty
        )
    else:
        usable_count = 0

    # IMPORTANT SCOPE RULE:
    # The retracement audit is NOT an all-219-symbol queue. It must only show
    # stocks that are already fully qualified by the existing frozen dashboard
    # candidate path. _rank() remains the sole authority for that qualification.
    qualified_result = _rank(result)
    if qualified_result is None or qualified_result.empty:
        return

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Evaluate only the existing qualified opportunity pool so a prior-day
    # structural break can be carried into today's retracement context without
    # presenting non-qualified evaluated stocks as opportunities.
    for _, row in qualified_result.iterrows():
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)

        ctx = _retracement_context(row, snapshot_results)
        saved_watch = watches.get(symbol, {}) or {}
        saved_alert = alerts.get(symbol, {}) or {}
        saved_break = breaks.get(symbol, {}) or {}
        first = (
            str(first_alerts.get(symbol, {}).get("timestamp", "")).strip()
            if isinstance(first_alerts.get(symbol, {}), dict)
            else ""
        )

        # A row is relevant if the engine has a current structural break or
        # durable prior-day break, or if the lifecycle state already exists.
        direction = str(
            row.get("decision_direction", row.get("direction", ""))
        ).upper().strip()
        sr = _sr_text(row).upper().strip()
        current_break = (
            (direction == "BULLISH" and sr == "RESISTANCE BROKEN")
            or (direction == "BEARISH" and sr == "SUPPORT BROKEN")
        )
        relevant = bool(saved_break or saved_watch or saved_alert or current_break)
        if not relevant:
            continue

        status = str(
            saved_alert.get("status", "")
            if saved_alert
            else saved_watch.get("status", "")
            if saved_watch
            else ctx.get("status", "")
        ).upper().strip()

        # If the current context explicitly invalidated the lifecycle, show it
        # rather than silently retaining an old watch.
        if ctx.get("status") == "INVALIDATED":
            status = "INVALIDATED"

        break_origin = (
            str(ctx.get("break_origin", "")).strip()
            or str(saved_watch.get("break_origin", "")).strip()
            or ("CURRENT DAY" if current_break else "PRIOR DAY")
        )
        break_ts = ctx.get("break_timestamp")
        if not break_ts:
            break_ts = saved_break.get("break_timestamp", "") or saved_watch.get(
                "break_timestamp", ""
            )

        entry_name = (
            str(ctx.get("entry_name", "")).strip()
            or str(saved_watch.get("entry_name", "")).strip()
            or str(saved_alert.get("entry_name", "")).strip()
            or "—"
        )
        entry_level = (
            ctx.get("entry_level")
            if ctx.get("entry_level") is not None
            else saved_watch.get("entry_level")
            if saved_watch.get("entry_level") is not None
            else saved_alert.get("entry_level")
        )

        reentry_time = str(saved_alert.get("timestamp", "")).strip()
        watch_time = str(saved_watch.get("updated_at", "")).strip()

        def _fmt_ts(value: Any) -> str:
            raw = str(value).strip()
            if not raw:
                return "—"
            try:
                return datetime.fromisoformat(raw).strftime("%H:%M:%S")
            except (TypeError, ValueError):
                try:
                    return pd.to_datetime(raw).strftime("%H:%M:%S")
                except Exception:
                    return "—"

        rows.append(
            {
                "Stock": symbol,
                "Direction": direction or "—",
                "Original Alert": _fmt_ts(
                    first
                    or saved_alert.get("original_first_alert_timestamp", "")
                    or saved_watch.get("original_first_alert_timestamp", "")
                ),
                "Break Origin": break_origin,
                "Break Time": _fmt_ts(break_ts),
                "Status": status or "WATCH",
                "Reference": entry_name,
                "Level": (
                    f"{float(entry_level):.2f}"
                    if entry_level is not None
                    and pd.notna(pd.to_numeric(entry_level, errors="coerce"))
                    else "—"
                ),
                "Watch/Event": _fmt_ts(reentry_time or watch_time),
                "Re-entry Alert": _fmt_ts(reentry_time),
                "Reason": str(
                    saved_alert.get("reason", "")
                    or ctx.get("reason", "")
                    or saved_watch.get("reason", "")
                    or "—"
                ),
                "_bar_count": ctx.get("bar_count"),
                "_ema_ready": ctx.get("ema_ready"),
                "_ema20": ctx.get("ema20"),
                "_vwap": ctx.get("vwap"),
            }
        )

    with st.expander(
        "Retracement / Re-entry Opportunities • lifecycle audit",
        expanded=False,
    ):
        if not rows:
            st.info(
                "No current or carried structural-break retracement lifecycle is "
                "available for this session."
            )
            return

        table = pd.DataFrame(rows)
        st.caption(
            f"Qualified opportunity pool: {len(qualified_result)} stocks. "
            "This audit uses the existing SDL gate, candidate filter and ranking; "
            "the full evaluated universe is intentionally excluded. "
            f"Replay observations available: {usable_count if isinstance(snapshot_results, dict) else 0}."
        )
        # Prioritize actionable lifecycle states, then strongest/more recent
        # evidence without altering primary stock ranking.
        order = {
            "REENTRY ALERT": 0,
            "WATCH": 1,
            "INVALIDATED": 2,
            "UNAVAILABLE": 3,
            "NOT_ACTIVE": 4,
        }
        table["_order"] = table["Status"].map(order).fillna(9)
        table = table.sort_values(
            ["_order", "Direction", "Stock"], kind="stable"
        ).drop(columns=["_order"])

        # Accepted visual target: clean, spacious audit table with readable
        # typography and compact status badges. This CSS is scoped to this
        # section only; no other dashboard surface is modified.
        def _html(value: Any) -> str:
            import html
            return html.escape(str(value if value is not None else "—"))

        def _status_badge(status: str) -> str:
            s = str(status).upper().strip()
            cls = {
                "REENTRY ALERT": "reentry",
                "WATCH": "watch",
                "WARMING UP": "warming",
                "UNAVAILABLE": "unavailable",
                "INVALIDATED": "invalidated",
                "NOT_ACTIVE": "inactive",
            }.get(s, "inactive")
            return f'<span class="rt-status {cls}">{_html(s or "—")}</span>'

        def _direction_html(direction: str) -> str:
            d = str(direction).upper().strip()
            cls = "bullish" if d == "BULLISH" else "bearish" if d == "BEARISH" else "neutral"
            return f'<span class="rt-direction {cls}">{_html(d or "—")}</span>'

        headers = [
            "Stock", "Direction", "Original Alert", "Break Origin",
            "Break Time", "Status", "Reference", "Level",
            "Watch/Event", "Re-entry Alert", "Reason",
        ]
        body = []
        for _, item in table.iterrows():
            body.append(
                "<tr>"
                f"<td class='rt-stock'>{_html(item['Stock'])}</td>"
                f"<td>{_direction_html(item['Direction'])}</td>"
                f"<td>{_html(item['Original Alert'])}</td>"
                f"<td>{_html(item['Break Origin'])}</td>"
                f"<td>{_html(item['Break Time'])}</td>"
                f"<td>{_status_badge(item['Status'])}</td>"
                f"<td>{_html(item['Reference'])}</td>"
                f"<td>{_html(item['Level'])}</td>"
                f"<td>{_html(item['Watch/Event'])}</td>"
                f"<td>{_html(item['Re-entry Alert'])}</td>"
                f"<td class='rt-reason'>{_html(item['Reason'])}</td>"
                "</tr>"
            )

        st.markdown(
            """
            <style>
            .rt-audit-wrap{
                width:100%;
                overflow-x:auto;
                border:1px solid #e3e8ef;
                border-radius:10px;
                background:#fff;
            }
            .rt-audit-table{
                width:100%;
                border-collapse:separate;
                border-spacing:0;
                font-size:13px;
                color:#273449;
                white-space:nowrap;
            }
            .rt-audit-table th{
                background:#f7f8fa;
                color:#667085;
                font-weight:600;
                text-align:left;
                padding:10px 12px;
                border-bottom:1px solid #dfe4ea;
                border-right:1px solid #e9edf2;
            }
            .rt-audit-table td{
                padding:9px 12px;
                border-bottom:1px solid #e9edf2;
                border-right:1px solid #eef1f4;
                vertical-align:middle;
            }
            .rt-audit-table tr:last-child td{border-bottom:0}
            .rt-audit-table th:last-child,
            .rt-audit-table td:last-child{border-right:0}
            .rt-stock{
                font-weight:600;
                color:#273449;
            }
            .rt-reason{
                min-width:230px;
                white-space:normal;
                line-height:1.35;
            }
            .rt-direction{
                font-weight:700;
                letter-spacing:.02em;
            }
            .rt-direction.bullish{color:#159447}
            .rt-direction.bearish{color:#e3262e}
            .rt-direction.neutral{color:#667085}
            .rt-status{
                display:inline-block;
                padding:4px 9px;
                border-radius:6px;
                font-size:12px;
                font-weight:700;
                letter-spacing:.01em;
            }
            .rt-status.reentry{
                background:#e9f8ef;
                color:#159447;
                border:1px solid #9fe0b8;
            }
            .rt-status.watch{
                background:#fff0f1;
                color:#e3262e;
                border:1px solid #ffb8bd;
            }
            .rt-status.warming{
                background:#fff5df;
                color:#9a6500;
                border:1px solid #f2cf8a;
            }
            .rt-status.unavailable{
                background:#eef2f7;
                color:#344b6b;
                border:1px solid #b8c5d6;
            }
            .rt-status.invalidated,
            .rt-status.inactive{
                background:#f2f4f7;
                color:#667085;
                border:1px solid #d0d5dd;
            }
            </style>
            <div class="rt-audit-wrap">
              <table class="rt-audit-table">
                <thead><tr>
                  {headers}
                </tr></thead>
                <tbody>{body}</tbody>
              </table>
            </div>
            """.replace(
                "{headers}",
                "".join(f"<th>{_html(h)}</th>" for h in headers),
            ).replace(
                "{body}",
                "".join(body),
            ),
            unsafe_allow_html=True,
        )

        # Indicator readiness is deliberately visible so "no alert" can be
        # distinguished from an indicator that is still warming up.
        readiness_rows = []
        for item in rows:
            if item.get("_ema_ready") is not None or item.get("_vwap") is not None:
                readiness_rows.append(
                    {
                        "Stock": item["Stock"],
                        "15m EMA20": (
                            f"{float(item['_ema20']):.2f}"
                            if item.get("_ema20") is not None
                            else f"WARMING UP ({item.get('_bar_count', 0)}/20)"
                        ),
                        "Session VWAP": (
                            f"{float(item['_vwap']):.2f}"
                            if item.get("_vwap") is not None
                            else "UNAVAILABLE",
                        ),
                    }
                )
        if readiness_rows:
            st.caption(
                "Retracement references use today's session data only. "
                "15m EMA20 requires 20 completed 15-minute buckets; "
                "VWAP requires usable session volume."
            )
            st.dataframe(
                pd.DataFrame(readiness_rows),
                use_container_width=True,
                hide_index=True,
            )
        st.caption(
            "Original Alert, Break Time, Watch/Event, and Re-entry Alert are "
            "separate timestamps. This layer is diagnostic and does not change "
            "the existing SDL selection or ranking."
        )

def _render_current_result(
    result: pd.DataFrame,
    timeline: pd.DataFrame,
    snapshot_label: str,
    widget_key_prefix: str = "",
    snapshot_results: dict[str, pd.DataFrame] | None = None,
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

    with st.expander("Current Decision Opportunities • Top candidates", expanded=True):
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

        _render_opportunity_cards(filtered, limit=10, snapshot_results=snapshot_results)
        _render_live_queue(filtered, snapshot_results=snapshot_results)
        if not filtered.empty:
            symbol = st.selectbox(
                "Inspect one decision",
                filtered["symbol"].astype(str).tolist(),
                key=f"{widget_key_prefix}ds_inspect_stock",
            )
            selected = filtered.loc[filtered["symbol"].astype(str).eq(symbol)].iloc[0]
            _render_evidence(selected)

        with st.expander("Full qualified decision table • audit view", expanded=False):
            _render_table(filtered)

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

    _render_retracement_lifecycle(
        result,
        snapshot_results=snapshot_results,
        widget_key_prefix=widget_key_prefix,
    )

    # Intraday Stock Evolution is a focused, stock-wise progress view. It remains
    # derived only from the existing timeline events and never creates a new
    # decision rule.
    if isinstance(timeline, pd.DataFrame) and not timeline.empty:
        with st.expander("Intraday Stock Evolution • meaningful changes", expanded=False):
            evo = timeline.copy()
            for col in [
                "Time", "Symbol", "Decision", "Previous", "Direction",
                "Evidence", "Strength", "S/R", "First Alert",
            ]:
                if col not in evo.columns:
                    evo[col] = "—"

            evo["Time"] = evo["Time"].astype(str)
            evo["Symbol"] = evo["Symbol"].astype(str).str.upper().str.strip()
            evo["Decision"] = evo["Decision"].astype(str).str.upper().str.strip()
            evo["Previous"] = evo["Previous"].astype(str).str.upper().str.strip()
            evo["Direction"] = evo["Direction"].astype(str).str.upper().str.strip()

            # Attach the durable first-alert timestamp when the timeline predates
            # this field. The state file is the source of truth.
            try:
                _evo_date_raw = st.session_state.get("ds_trading_date", "")
                if hasattr(_evo_date_raw, "strftime"):
                    _evo_date_key = _evo_date_raw.strftime("%Y-%m-%d")
                else:
                    _evo_date_key = str(_evo_date_raw).strip()[:10]
                day_state = load_state(STATE_JSON).get(STATE_KEY, {}).get(
                    _evo_date_key, {}
                ) or {}
                first_alerts = day_state.get("first_alerts", {}) or {}
            except Exception:
                first_alerts = {}
            def _display_first_alert(row: pd.Series) -> str:
                symbol = str(row["Symbol"]).upper().strip()

                # First Alert is immutable. Prefer an explicit timeline value,
                # then durable state. Never compare it to the current event time.
                for key in ("first_alert_timestamp", "first_alert", "First Alert"):
                    raw = str(row.get(key, "")).strip()
                    if raw and raw not in {"—", "NAN", "NONE"}:
                        try:
                            return datetime.fromisoformat(raw).strftime("%H:%M:%S")
                        except (TypeError, ValueError):
                            pass

                saved = first_alerts.get(symbol, {}) or {}
                raw = str(saved.get("timestamp", "")).strip() if isinstance(saved, dict) else ""
                if raw:
                    try:
                        return datetime.fromisoformat(raw).strftime("%H:%M:%S")
                    except (TypeError, ValueError):
                        pass
                return "—"

            evo["First Alert"] = evo.apply(_display_first_alert, axis=1)

            # Attach the durable second-opportunity lifecycle without replacing
            # the original event history.
            retrace_alerts = day_state.get("retracement_alerts", {}) or {}
            retrace_watches = day_state.get("retracement_watches", {}) or {}
            structural_breaks = day_state.get("structural_breaks", {}) or {}

            def _evolution_event(row: pd.Series) -> str:
                symbol = str(row.get("Symbol", "")).upper().strip()
                previous = str(row.get("Previous", "")).upper()
                direction = str(row.get("Direction", "")).upper()
                decision = str(row.get("Decision", "")).upper()
                sr = str(row.get("S/R", "")).upper()

                # A current-day observation that is the actual qualifying
                # structural break remains the original event.
                is_break = (
                    (direction == "BULLISH" and sr == "RESISTANCE BROKEN")
                    or (direction == "BEARISH" and sr == "SUPPORT BROKEN")
                )
                if is_break:
                    return "ORIGINAL BREAK"

                if symbol in retrace_alerts:
                    alert = retrace_alerts.get(symbol, {}) or {}
                    name = str(alert.get("entry_name", "EMA20/VWAP")).strip()
                    return f"RE-ENTRY ALERT · {name}"

                if symbol in retrace_watches:
                    watch = retrace_watches.get(symbol, {}) or {}
                    name = str(watch.get("entry_name", "EMA20/VWAP")).strip()
                    return f"RETRACE WATCH · {name}"

                if previous in {"BULLISH", "BEARISH"} and direction in {"BULLISH", "BEARISH"} and previous != direction:
                    return "REVERSAL"
                if previous in {"", "—", "NONE", "NAN", "NO DECISION"}:
                    return "NEW ALERT"
                if decision.startswith("DEVELOPING"):
                    return "DEVELOPING"
                if decision == "WAIT_BREAK_CONFIRMATION":
                    return "WAIT BREAK"
                if decision.startswith("ACTIVE"):
                    return "ACTIVE"
                if decision.startswith("STRONG"):
                    return "STRONG"
                return "STATE CHANGE"

            evo["Event"] = evo.apply(_evolution_event, axis=1)

            def _break_origin(row: pd.Series) -> str:
                symbol = str(row.get("Symbol", "")).upper().strip()
                item = structural_breaks.get(symbol, {}) or {}
                if not isinstance(item, dict):
                    return "—"
                return str(item.get("date", "")).strip() or "—"

            evo["Break Origin"] = evo.apply(_break_origin, axis=1)
            symbols = sorted(evo["Symbol"].dropna().unique().tolist())
            f1, f2 = st.columns([2, 1])
            with f1:
                selected_stock = st.selectbox(
                    "Stock",
                    ["All stocks"] + symbols,
                    key=f"{widget_key_prefix}evolution_stock",
                )
            with f2:
                selected_event = st.selectbox(
                    "Progress",
                    ["All", "NEW ALERT", "DEVELOPING", "WAIT BREAK", "ACTIVE", "STRONG", "REVERSAL", "STATE CHANGE"],
                    key=f"{widget_key_prefix}evolution_event",
                )

            filtered_evo = evo.copy()
            if selected_stock != "All stocks":
                filtered_evo = filtered_evo.loc[filtered_evo["Symbol"].eq(selected_stock)].copy()
            if selected_event != "All":
                filtered_evo = filtered_evo.loc[filtered_evo["Event"].eq(selected_event)].copy()

            if selected_stock == "All stocks":
                filtered_evo = filtered_evo.tail(30)
            else:
                filtered_evo = filtered_evo.tail(60)

            display_cols = [
                "Time", "Symbol", "First Alert", "Event", "Break Origin",
                "Decision", "Previous", "Direction", "Evidence", "Strength", "S/R",
            ]
            display_cols = [c for c in display_cols if c in filtered_evo.columns]

            def _evo_style(row: pd.Series) -> list[str]:
                event = str(row.get("Event", ""))
                decision = str(row.get("Decision", "")).upper()
                direction = str(row.get("Direction", "")).upper()
                if event == "NEW ALERT":
                    return ["background-color:#ecfdf5;color:#166534;font-weight:700"] * len(row)
                if event == "REVERSAL":
                    return ["background-color:#fff1f2;color:#9f1239;font-weight:700"] * len(row)
                if decision.startswith("STRONG"):
                    return ["background-color:#dcfce7;color:#166534"] * len(row)
                if decision.startswith("ACTIVE"):
                    return ["background-color:#f0fdf4;color:#15803d"] * len(row)
                if event == "WAIT BREAK":
                    return ["background-color:#eef2ff;color:#3730a3"] * len(row)
                if decision.startswith("DEVELOPING"):
                    return ["background-color:#fffbeb;color:#92400e"] * len(row)
                if direction == "BEARISH":
                    return ["background-color:#fff7f7;color:#991b1b"] * len(row)
                return ["background-color:#f8fafc;color:#334155"] * len(row)

            st.dataframe(
                filtered_evo[display_cols].style.apply(_evo_style, axis=1),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Progress colours: green = strengthening/strong, amber = developing, "
                "indigo = wait-break, red/pink = reversal. First Alert is immutable "
                "provenance; Event Time changes with each observation or re-entry event."
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

    # First Alert is durable provenance. Older persisted results may not carry
    # the column, so recover it from the established first_alerts map.
    first_alerts = day.get("first_alerts", {}) or {}
    if not result.empty and "symbol" in result.columns:
        result["first_alert_timestamp"] = result["symbol"].map(
            lambda value: str(
                first_alerts.get(
                    str(value).strip().upper(), {}
                ).get("timestamp", "")
            )
        )

    # Backfill provenance from the durable first_alerts map when an older
    # persisted result does not contain the first_alert_timestamp column.
    day_first_alerts = day.get("first_alerts", {}) or {}
    if not result.empty and "symbol" in result.columns:
        result["first_alert_timestamp"] = result["symbol"].map(
            lambda value: str(
                day_first_alerts.get(
                    str(value).strip().upper(), {}
                ).get("timestamp", "")
            )
        )

    timeline_rows = saved.get("timeline", [])
    timeline = (
        pd.DataFrame(timeline_rows)
        if isinstance(timeline_rows, list)
        else pd.DataFrame()
    )
    source_file = str(saved.get("source_file", "")).strip()
    observation_timestamp = str(saved.get("observation_timestamp", "")).strip()
    return result, timeline, source_file, observation_timestamp


def _hydrate_retracement_replay(
    sources: list[Path],
    trading_date: str,
) -> tuple[dict[str, pd.DataFrame], int, int]:
    """Incrementally hydrate historical replay observations for retracement.

    This is separate from the LIVE checkpoint. It reconstructs only the
    missing chronological replay prefix in small batches. The authoritative
    LIVE checkpoint and primary candidate logic are never changed.
    """
    cache = _get_replay_cache(trading_date)
    snapshots = cache.get("snapshots", {})
    if not isinstance(snapshots, dict):
        snapshots = {}

    if not sources:
        return snapshots, 0, 0

    source_keys = [_source_key(p) for p in sources]
    prefix = 0
    while prefix < len(source_keys) and source_keys[prefix] in snapshots:
        frame = snapshots.get(source_keys[prefix])
        if not isinstance(frame, pd.DataFrame):
            break
        prefix += 1

    if prefix >= len(sources):
        return snapshots, prefix, len(sources)

    init_key = f"_rt_hydration_initialized_{trading_date}"
    initialized = bool(st.session_state.get(init_key, False))
    batch_size = 2 if not initialized else 10
    st.session_state[init_key] = True

    start = prefix
    end = min(len(sources), start + batch_size)

    state = load_state(STATE_JSON)
    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    first_alerts = day.get("first_alerts", {}) or {}
    first_range = _first_range_from_path(sources[0], trading_date)

    if start == 0:
        snapshots[source_keys[0]] = pd.DataFrame()
        start = 1
        if start >= end:
            _store_replay_cache(
                trading_date, snapshots, cache.get("timeline", pd.DataFrame())
            )
            return snapshots, 1, len(sources)

    previous_raw = _snapshot_rows(_read(sources[start - 1]))

    for path in sources[start:end]:
        result = _process_snapshot(path, trading_date, previous_raw, first_range)
        result = _attach_snapshot_metadata(result, path)
        timestamp = parse_observation_timestamp(path)

        if not result.empty:
            result = _update_first_alerts(
                state, trading_date, result, timestamp, first_alerts
            )
            snapshots[_source_key(path)] = result
            result = _update_retracement_alerts(
                state, trading_date, result, snapshots
            )
            snapshots[_source_key(path)] = result
        else:
            snapshots[_source_key(path)] = result

        previous_raw = _snapshot_rows(_read(path))

    save_state(state, STATE_JSON)
    _store_replay_cache(
        trading_date, snapshots, cache.get("timeline", pd.DataFrame())
    )
    return snapshots, end, len(sources)


if hasattr(st, "fragment"):
    @st.fragment(run_every="300s")
    def _live_auto_panel(source_root: Path, trading_date: str, auto_update: bool, rollover_fallback: bool = False) -> None:
        # Re-discover on every live fragment cycle so newly-arrived snapshots
        # become visible without requiring a manual full-page refresh.
        try:
            sources = _discover_sources(trading_date, source_root)
            if not sources:
                st.info("No intraday snapshots are currently available for this date.")
                return

            # Hydrate retracement history incrementally in the LIVE path.
            # The audit renderer itself remains read-only and non-blocking.
            _hydrate_retracement_replay(sources, trading_date)

            _, market_open = _market_session_status(trading_date)
            session_state = st.session_state.setdefault(_live_session_key(trading_date), {})
            session_state["last_source_key"] = _source_key(sources[-1])

            # LIVE FEED always resolves to the chronologically latest available
            # source snapshot. When Auto-Live is ON, newly arriving source files
            # are processed incrementally on each fragment cycle, regardless of
            # whether the market is currently open. Market status never hides the
            # latest available snapshot.
            # On a calendar rollover, CURRENT DAY is intentionally displaying
            # the previous trading day's last completed result. Restore that
            # durable result directly instead of replaying all snapshots merely
            # to reconstruct an already-processed day.
            if rollover_fallback:
                restored = _restore_last_complete_state(trading_date)
                if restored is not None:
                    latest, timeline, persisted_source, persisted_timestamp = restored
                elif auto_update:
                    latest, timeline, _changed = _auto_process_new_snapshots(
                        sources, trading_date
                    )
                    persisted_source = ""
                    persisted_timestamp = ""
                else:
                    latest, timeline, _ = _load_day_for_snapshot_view(
                        sources, trading_date
                    )
                    persisted_source = ""
                    persisted_timestamp = ""
            elif auto_update and market_open:
                latest, timeline, _changed = _auto_process_new_snapshots(
                    sources, trading_date
                )
                persisted_source = ""
                persisted_timestamp = ""
            elif auto_update and not market_open:
                # After the regular session closes, LIVE becomes a frozen
                # read-only view of the last complete processed state. The
                # 5-minute fragment may still refresh the page, but it must
                # not keep mutating the closed session.
                restored = _restore_last_complete_state(trading_date)
                if restored is not None:
                    latest, timeline, persisted_source, persisted_timestamp = restored
                else:
                    latest, timeline, _ = _load_day_for_snapshot_view(
                        sources, trading_date
                    )
                session_state["finalized"] = True
            else:
                latest, timeline, _ = _load_day_for_snapshot_view(
                    sources, trading_date
                )
                persisted_source = ""
                persisted_timestamp = ""
            session_state["finalized"] = not market_open

            if latest is None or latest.empty:
                st.info("The first snapshot is BASE ONLY. Waiting for the first decision-bearing snapshot.")
                return

            latest_path = sources[-1]
            latest_time = parse_observation_timestamp(latest_path)
            if persisted_source:
                candidate_path = Path(persisted_source)
                if candidate_path.is_file():
                    latest_path = candidate_path
                    latest_time = (
                        datetime.fromisoformat(persisted_timestamp)
                        if persisted_timestamp
                        else parse_observation_timestamp(candidate_path)
                    )
            if isinstance(latest, pd.DataFrame) and not latest.empty:
                if "source_file" in latest.columns:
                    source_values = latest["source_file"].dropna().astype(str)
                    if not source_values.empty:
                        candidate = Path(source_values.iloc[-1])
                        if candidate.is_file():
                            latest_path = candidate
                if "source_timestamp" in latest.columns:
                    processed_times = pd.to_datetime(
                        latest["source_timestamp"], errors="coerce"
                    ).dropna()
                    if not processed_times.empty:
                        latest_time = processed_times.max().to_pydatetime()
                elif "observation_timestamp" in latest.columns:
                    processed_times = pd.to_datetime(
                        latest["observation_timestamp"], errors="coerce"
                    ).dropna()
                    if not processed_times.empty:
                        latest_time = processed_times.max().to_pydatetime()
            source_latest_time = parse_observation_timestamp(sources[-1])
            if not market_open:
                if persisted_source:
                    status = (
                        "LIVE FEED • SESSION CLOSED • "
                        "LAST COMPLETE SNAPSHOT"
                    )
                else:
                    status = (
                        "LIVE FEED • SESSION CLOSED • "
                        "LAST AVAILABLE SNAPSHOT"
                    )
            elif auto_update:
                if latest_time < source_latest_time:
                    status = (
                        "LIVE FEED • processing catch-up • "
                        "chronologically monitored"
                    )
                else:
                    status = (
                        "LIVE FEED • last available snapshot • "
                        "chronologically monitored"
                    )
            else:
                status = "LIVE FEED • last processed snapshot • Auto-update OFF"

            if latest_time < source_latest_time:
                st.caption(
                    f"{status} • processed {latest_time:%H:%M:%S} / "
                    f"source latest {source_latest_time:%H:%M:%S} • {latest_path.name}"
                )
            else:
                st.caption(
                    f"{status} • {latest_time:%H:%M:%S} • {latest_path.name}"
                )

            # The LIVE result is the output of the existing processing pipeline
            # applied to the data available through this processed timestamp.
            # Keep the row-level output collapsed so it does not compete with
            # the decision-first board.
            _live_cache = _get_replay_cache(trading_date)
            _render_processing_output(
                latest,
                latest_time,
                latest_path,
                _live_cache.get("snapshots", {}) if isinstance(_live_cache, dict) else {},
            )
            _render_current_result(latest, timeline, latest_time.strftime("%H:%M:%S"), "live_", _live_cache.get("snapshots", {}) if isinstance(_live_cache, dict) else {})
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
    # A calendar-day rollover must not blank the decision center. CURRENT DAY
    # uses today's snapshots when present; otherwise it retains the most recent
    # available trading-day result until a new current-day source arrives.
    selected_calendar_date = trading_date
    available_dates = _available_trading_dates(source_root)

    if view_mode == "CURRENT DAY":
        try:
            sources = _discover_sources(selected_calendar_date, source_root)
        except Exception as exc:
            st.error(f"Source discovery failed: {type(exc).__name__}: {exc}")
            return

        data_trading_date = selected_calendar_date
        if not sources:
            prior_dates = [
                d for d in available_dates if d <= selected_calendar_date
            ]
            if prior_dates:
                data_trading_date = prior_dates[-1]
                sources = _discover_sources(data_trading_date, source_root)
                if data_trading_date != selected_calendar_date:
                    st.info(
                        f"No snapshots yet for {selected_calendar_date}. "
                        f"Showing latest available trading day: {data_trading_date}. "
                        "New-session LIVE processing will begin when the first "
                        "current-day snapshot arrives."
                    )
            else:
                st.warning("No Daywise snapshots are available yet.")
                return
        trading_date = data_trading_date
    else:
        # Historical mode has its own date selector and source discovery below.
        # Use the latest available day only for the compact top strip.
        data_trading_date = (
            available_dates[-1] if available_dates else selected_calendar_date
        )
        sources = (
            _discover_sources(data_trading_date, source_root)
            if available_dates else []
        )

    if not sources:
        st.warning("No Daywise snapshots are available yet.")
        return

    latest_path = sources[-1]
    latest_time = parse_observation_timestamp(latest_path)
    st.markdown(
        f'<div class="snapshot"><b>Snapshots:</b> {len(sources)} &nbsp;|&nbsp; '
        f'<b>First:</b> {parse_observation_timestamp(sources[0]):%H:%M:%S} &nbsp;|&nbsp; '
        f'<b>Latest:</b> {latest_time:%H:%M:%S}</div>',
        unsafe_allow_html=True,
    )

    # TOP deployment: compact operational status only. No decision or
    # processing logic is changed here.
    _, market_open = _market_session_status(trading_date)
    session_class = "top-status-live" if market_open else "top-status-closed"
    session_label = "MARKET OPEN" if market_open else "MARKET CLOSED"

    # LIVE FEED is the chronologically latest available snapshot.
    # Market status is separate: after hours, the last available snapshot
    # remains the live dashboard result until a newer source file arrives.
    auto_live_enabled = st.session_state.get("ds_auto_update", True)
    if auto_live_enabled and market_open:
        live_feed_class = "top-status-active"
        live_feed_label = "LIVE FEED • LAST AVAILABLE"
    elif auto_live_enabled and not market_open:
        live_feed_class = "top-status-closed"
        live_feed_label = "LIVE FEED • SESSION CLOSED"
    else:
        live_feed_class = "top-status-closed"
        live_feed_label = "LIVE FEED • PAUSED"

    st.markdown(
        f'''
<div class="top-status">
  <div class="top-status-chip top-status-ready">
    <span class="top-status-dot"></span>DATA READY
  </div>
  <div class="top-status-chip {live_feed_class}">
    <span class="top-status-dot"></span>{live_feed_label}
  </div>
  <div class="top-status-chip {session_class}">
    <span class="top-status-dot"></span>{session_label}
  </div>
  <div class="top-status-chip">
    <span class="top-status-dot"></span>LAST {latest_time:%H:%M:%S}
  </div>
</div>
''',
        unsafe_allow_html=True,
    )

    if view_mode == "CURRENT DAY":
        # CURRENT DAY intentionally renders LIVE and INTRADAY SNAPSHOT together.
        # LIVE owns the live-processing path; the snapshot section only reads
        # the already-prepared replay cache (or explicitly prepares it when
        # needed for snapshot inspection). The two views use independent
        # Streamlit widget keys so changing the snapshot selector cannot alter
        # LIVE state.
        with st.expander("LIVE • Feed & Session", expanded=True):
            a1, a2 = st.columns([2, 1])
            with a1:
                auto_update = st.checkbox(
                    "Auto-update live feed (5 min)",
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
                _live_auto_panel(
                    source_root,
                    trading_date,
                    auto_update,
                    rollover_fallback=(trading_date != selected_calendar_date),
                )
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

                    status = (
                        "LIVE FEED • last available snapshot • chronologically monitored"
                        if auto_update
                        else "LIVE FEED • last available snapshot • Auto-update OFF"
                    )
                    if not market_open:
                        status += " • market closed"

                    st.caption(
                        f"{status} • {live_time:%H:%M:%S} • {live_path.name}"
                    )
                    _live_cache = _get_replay_cache(trading_date)
                    _render_current_result(
                        latest, timeline, live_time.strftime("%H:%M:%S"), "live_",
                        _live_cache.get("snapshots", {}) if isinstance(_live_cache, dict) else {},
                    )


        with st.expander("INTRADAY SNAPSHOT / REPLAY", expanded=False):
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
                _render_current_result(result, timeline, labels[idx], "intraday_", snapshots)


    else:  # HISTORICAL
        with st.expander("HISTORICAL REPLAY", expanded=False):
            historical_default = (
                available_dates[-1]
                if available_dates
                else date.today().strftime("%Y-%m-%d")
            )
            historical_date = st.date_input(
                "Historical trading date",
                value=datetime.strptime(historical_default, "%Y-%m-%d").date(),
                key="ds_historical_date",
            ).strftime("%Y-%m-%d")
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
            _render_current_result(result, timeline, parse_observation_timestamp(selected_path).strftime("%H:%M:%S"), "historical_", snapshots)


if __name__ == "__main__":
    render()
