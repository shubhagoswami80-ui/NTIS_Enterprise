from __future__ import annotations

from datetime import date, datetime
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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    state = load_state(STATE_JSON)
    previous: dict[str, dict] = {}
    previous_state: dict[str, str] = {}
    previous_direction: dict[str, str] = {}
    timeline_rows: list[dict[str, Any]] = []
    latest_result = pd.DataFrame()
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

    return latest_result, pd.DataFrame(timeline_rows)


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
    """
    Return the primary-dashboard visibility mask.

    All rows remain available in `result`; only this mask determines what is
    promoted to the primary decision view.
    """
    if result.empty:
        return pd.Series(dtype=bool)

    state = (
        result.get(
            "decision_state",
            pd.Series("", index=result.index),
        )
        .astype(str)
        .str.upper()
    )
    score = pd.to_numeric(
        result.get(
            "decision_score",
            pd.Series(0, index=result.index),
        ),
        errors="coerce",
    ).fillna(0)

    confirmations = pd.to_numeric(
        result.get(
            "confirmation_count",
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
    ).map(_bool)

    # No decision is always excluded from the primary dashboard.
    mask = pd.Series(False, index=result.index)

    strong_or_active = state.isin(
        {
            "STRONG_BULLISH",
            "STRONG_BEARISH",
            "ACTIVE_BULLISH",
            "ACTIVE_BEARISH",
        }
    )
    mask |= strong_or_active & gate & (conflicts == 0)

    # A break-confirmation setup is useful even before the +/-0.75% gate,
    # but it must still have meaningful evidence and no material conflict.
    wait_break = state.eq("WAIT_BREAK_CONFIRMATION")
    mask |= (
        wait_break
        & (score >= 60)
        & (confirmations >= 3)
        & (conflicts <= 1)
    )

    # Developing rows are deliberately NOT all shown. Weak developing rows
    # are exactly the clutter we want to remove.
    developing = state.isin(DEVELOPING_STATES)
    mask |= (
        developing
        & (score >= 60)
        & (confirmations >= 3)
        & (conflicts == 0)
    )

    return mask


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

    cols = st.columns(5)
    values = [
        ("EVALUATED", total, ""),
        ("DECISION POOL", visible, ""),
        ("BULLISH", bullish, "metric-green"),
        ("BEARISH", bearish, "metric-red"),
        ("DEVELOPING", developing, "metric-amber"),
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
  <div class="hero-sub">
    Evidence-filtered intraday decisions — only relevant directional
    opportunities are promoted to the primary dashboard.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    source_text = st.text_input(
        "Source folder",
        value=str(Path(INTRADAY_SOURCE_ROOT).expanduser()),
    )
    source_root = Path(source_text).expanduser()

    c1, c2 = st.columns([1, 2])
    with c1:
        trading_date = st.date_input(
            "Trading date",
            value=date.today(),
        ).strftime("%Y-%m-%d")

    with c2:
        mode = st.radio(
            "Read mode",
            ["Latest File", "All Files / Day Replay"],
            horizontal=True,
        )

    try:
        sources = _discover_sources(
            trading_date,
            source_root,
        )
    except Exception as exc:
        st.error(
            f"Source discovery failed: {type(exc).__name__}: {exc}"
        )
        return

    if not sources:
        st.warning(
            "No Daywise snapshots found for the selected date."
        )
        return

    latest_timestamp = parse_observation_timestamp(sources[-1])
    live_batch_count = len(sources)

    st.markdown(
        f"""
<div class="snapshot">
<b>Snapshots:</b> {len(sources)}
&nbsp; | &nbsp;
<b>First:</b> {parse_observation_timestamp(sources[0]):%H:%M:%S}
&nbsp; | &nbsp;
<b>Latest:</b> {latest_timestamp:%H:%M:%S}
&nbsp; | &nbsp;
<b>Base:</b> first snapshot is reference-only
</div>
""",
        unsafe_allow_html=True,
    )

    if mode == "Latest File":
        # The selected/latest file is a DISPLAY choice only.
        # A live calculation must always consume the complete discovered
        # snapshot batch chronologically so the base snapshot and every
        # intermediate snapshot are respected before promoting the latest
        # result.
        selected_idx = st.selectbox(
            "Snapshot",
            list(range(len(sources))),
            index=len(sources) - 1,
            format_func=lambda i: (
                f"{parse_observation_timestamp(sources[i]):%H:%M:%S}"
                f" — {sources[i].name}"
            ),
        )

        if st.button(
            "PROCESS SELECTED SNAPSHOT BATCH",
            type="primary",
            use_container_width=True,
        ):
            try:
                batch_sources = sources[: selected_idx + 1]
                latest, _timeline = process_all_sources(
                    batch_sources,
                    trading_date,
                )
                st.session_state["ds_result"] = latest
                st.session_state["ds_timeline"] = pd.DataFrame()
                st.session_state["ds_processed_source"] = (
                    str(batch_sources[-1]) if batch_sources else ""
                )
                st.rerun()
            except Exception as exc:
                st.error(
                    f"Batch processing failed: {type(exc).__name__}: {exc}"
                )

    else:
        st.info(
            f"{len(sources)} snapshots discovered. "
            "Replay processes all files chronologically; "
            "the first snapshot is BASE ONLY."
        )

        if st.button(
            "PROCESS ALL FILES / DAY REPLAY",
            type="primary",
            use_container_width=True,
        ):
            try:
                latest, timeline = process_all_sources(
                    sources,
                    trading_date,
                )
                st.session_state["ds_result"] = latest
                st.session_state["ds_timeline"] = timeline
            except Exception as exc:
                st.error(
                    f"Replay failed: {type(exc).__name__}: {exc}"
                )

    result = st.session_state.get("ds_result")

    if (
        result is None
        or not isinstance(result, pd.DataFrame)
        or result.empty
    ):
        st.info(
            "Select a mode and process the data."
        )
        return

    # Only the latest processed snapshot is promoted to the live decision
    # pool. Earlier states remain history, not live opportunities.
    candidates = _rank(result)

    st.success(
        f"{len(result)} symbols evaluated; "
        f"{len(candidates)} promoted to the primary decision pool."
    )

    _render_summary(result, candidates)

    # Direction filter is a visibility control only; it never changes the
    # underlying calculation/evidence.
    st.markdown(
        '<div class="section">Current Decision Opportunities</div>',
        unsafe_allow_html=True,
    )

    filter_value = st.radio(
        "Show",
        ["All", "Bullish", "Bearish", "Developing", "Wait Break"],
        horizontal=True,
    )

    filtered = candidates.copy()

    if filter_value == "Bullish":
        filtered = filtered[
            filtered["decision_direction"]
            .astype(str).str.upper().eq("BULLISH")
        ]
    elif filter_value == "Bearish":
        filtered = filtered[
            filtered["decision_direction"]
            .astype(str).str.upper().eq("BEARISH")
        ]
    elif filter_value == "Developing":
        filtered = filtered[
            filtered["decision_state"]
            .astype(str).str.upper().str.startswith("DEVELOPING")
        ]
    elif filter_value == "Wait Break":
        filtered = filtered[
            filtered["decision_state"]
            .astype(str).str.upper().eq(
                "WAIT_BREAK_CONFIRMATION"
            )
        ]

    _render_table(filtered)

    if not filtered.empty:
        symbol = st.selectbox(
            "Inspect one decision",
            filtered["symbol"].astype(str).tolist(),
        )
        selected = filtered.loc[
            filtered["symbol"].astype(str).eq(symbol)
        ].iloc[0]
        _render_evidence(selected)

    # NO DECISION is deliberately not rendered as 100+ dashboard rows.
    # It remains visible only as a compact coverage metric.
    no_decision_count = int(
        result.get(
            "decision_state",
            pd.Series("", index=result.index),
        )
        .astype(str)
        .str.upper()
        .eq("NO DECISION")
        .sum()
    )

    weak_excluded = len(result) - len(candidates) - no_decision_count

    st.markdown(
        f"""
<div class="note">
Coverage: {len(result)} evaluated.
NO DECISION hidden: {no_decision_count}.
Weak / conflicted candidates hidden from the primary pool: {max(0, weak_excluded)}.
Underlying evidence is preserved in the processing result and replay state.
</div>
""",
        unsafe_allow_html=True,
    )

    replay_data = st.session_state.get(
        "ds_timeline",
        pd.DataFrame(),
    )

    if isinstance(replay_data, pd.DataFrame) and not replay_data.empty:
        unique_times = (
            replay_data["Time"].astype(str).nunique()
            if "Time" in replay_data.columns
            else 0
        )
        st.caption(
            f"Replay coverage: {unique_times} recorded observation time(s). "
            "Coverage reflects the source snapshots available for this session; "
            "it is not interpreted as a missing decision change."
        )

    _render_timeline(replay_data)


if __name__ == "__main__":
    render()
