from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from config import INTRADAY_SOURCE_ROOT, STATE_JSON
from source_loader import (
    discover_daywise_files,
    parse_observation_timestamp,
    read_source,
)
from storage import load_state, save_state
from derivative_signal.signal_engine import build_signal

STATE_KEY = "derivative_signal"

QUALIFIED_STATES = {
    "STRONG_BULLISH",
    "STRONG_BEARISH",
    "STRONG_NEAR_LEVEL",
    "ACTIVE_BULLISH",
    "ACTIVE_BEARISH",
    "WAIT_BREAK_CONFIRMATION",
    "DEVELOPING",
}


def _discover_sources(trading_date: str) -> list[Path]:
    files = discover_daywise_files(INTRADAY_SOURCE_ROOT, trading_date)
    return sorted(
        [Path(p) for p in files if Path(p).is_file()],
        key=lambda p: (
            p.stat().st_mtime,
            p.name,
        ),
    )


def _read(path: Path) -> pd.DataFrame:
    df = read_source(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _previous(
    state: dict[str, Any],
    trading_date: str,
) -> dict[str, dict]:
    return (
        state.get(STATE_KEY, {})
        .get(trading_date, {})
        .get("previous_snapshot", {})
    )


def _snapshot_rows(df: pd.DataFrame) -> dict[str, dict]:
    # Store only engine inputs needed for the next snapshot.
    keep = [
        "Symbol",
        "Close",
        "Price Chg %",
        "OI Chg %",
        "Tot PE-CE OI Chg",
        "PCR Chg %",
        "IV Chg %",
        "Volume Chg %",
        "ATM Straddle %",
        "Support",
        "Resistance",
        "Futures Buildup",
        "Futures OI Chg %",
    ]
    rows: dict[str, dict] = {}
    for record in df.to_dict(orient="records"):
        symbol = str(record.get("Symbol", "")).strip().upper()
        if symbol:
            rows[symbol] = {k: record.get(k) for k in keep}
    return rows


def _process_snapshot(
    path: Path,
    trading_date: str,
    previous: dict[str, dict],
) -> pd.DataFrame:
    df = _read(path)
    rows = []

    for record in df.to_dict(orient="records"):
        symbol = str(record.get("Symbol", "")).strip().upper()
        if symbol:
            rows.append(build_signal(record, previous.get(symbol)))

    return pd.DataFrame(rows)


def process_selected_source(
    path: Path,
    trading_date: str,
) -> pd.DataFrame:
    state = load_state(STATE_JSON)
    previous = _previous(state, trading_date)

    result = _process_snapshot(path, trading_date, previous)

    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    day["previous_snapshot"] = _snapshot_rows(_read(path))
    day["source_file"] = str(path)
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)

    return result


def process_all_sources(
    paths: list[Path],
    trading_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Replay all snapshots in chronological order.

    Returns:
      latest_result: decision state at the latest available snapshot
      timeline: qualifying decision changes across the day
    """
    state = load_state(STATE_JSON)
    previous: dict[str, dict] = {}
    timeline_rows: list[dict[str, Any]] = []
    latest_result = pd.DataFrame()

    ordered = sorted(
        paths,
        key=lambda p: (
            parse_observation_timestamp(p),
            p.stat().st_mtime,
            p.name,
        ),
    )

    previous_state: dict[str, str] = {}

    for path in ordered:
        result = _process_snapshot(path, trading_date, previous)
        if result.empty:
            continue

        timestamp = parse_observation_timestamp(path)

        for row in result.to_dict(orient="records"):
            state_name = str(row.get("state", "WATCH"))
            old_state = previous_state.get(row["symbol"])

            if (
                state_name != old_state
                and state_name in QUALIFIED_STATES
            ):
                timeline_rows.append(
                    {
                        "timestamp": timestamp,
                        "symbol": row["symbol"],
                        "state": state_name,
                        "direction": row["direction"],
                        "strength": row["strength"],
                        "action": row["action"],
                        "opportunity": row["opportunity"],
                    }
                )

            previous_state[row["symbol"]] = state_name

        previous = _snapshot_rows(_read(path))
        latest_result = result

    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    day["previous_snapshot"] = previous
    day["source_file"] = str(ordered[-1]) if ordered else ""
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)

    timeline = pd.DataFrame(timeline_rows)
    return latest_result, timeline


def _decision_text(row: pd.Series) -> str:
    state = str(row.get("state", ""))

    mapping = {
        "STRONG_BULLISH": "🟢 STRONG BULLISH",
        "STRONG_BEARISH": "🔴 STRONG BEARISH",
        "STRONG_NEAR_LEVEL": "🟠 BREAKOUT SETUP",
        "ACTIVE_BULLISH": "🟢 ACTIVE BULLISH",
        "ACTIVE_BEARISH": "🔴 ACTIVE BEARISH",
        "WAIT_BREAK_CONFIRMATION": "🟡 WAIT FOR BREAK",
        "DEVELOPING": "🟡 DEVELOPING",
        "DIRECTIONAL_UNCONFIRMED": "⚪ UNCONFIRMED",
        "INSUFFICIENT_DATA": "⚪ NO DATA",
    }
    return mapping.get(state, "⚪ WATCH")


def _direction_text(direction: str) -> str:
    if direction == "BULLISH":
        return "▲ BULLISH"
    if direction == "BEARISH":
        return "▼ BEARISH"
    return "— NEUTRAL"


def _strength_html(score: int) -> str:
    score = max(0, min(5, int(score or 0)))
    circles = []
    for index in range(1, 6):
        if index <= score:
            if score >= 4:
                cls = "filled-green"
            elif score >= 3:
                cls = "filled-amber"
            else:
                cls = "filled-grey"
        else:
            cls = "empty"
        circles.append(f'<span class="strength-circle {cls}"></span>')
    return "".join(circles)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2.0rem;
            padding-bottom: 2rem;
            max-width: 1450px;
        }

        .hero {
            padding: 22px 26px;
            border-radius: 16px;
            background: linear-gradient(135deg, #172554, #312e81);
            color: white;
            margin-bottom: 16px;
        }

        .hero-title {
            font-size: 30px;
            font-weight: 800;
            letter-spacing: -0.4px;
        }

        .hero-subtitle {
            opacity: .82;
            margin-top: 4px;
            font-size: 14px;
        }

        .decision-card {
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 15px 17px;
            background: #ffffff;
            min-height: 120px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, .06);
        }

        .decision-symbol {
            font-size: 17px;
            font-weight: 800;
            color: #111827;
        }

        .decision-state {
            font-size: 14px;
            font-weight: 750;
            margin-top: 5px;
        }

        .decision-meta {
            color: #64748b;
            font-size: 12px;
            margin-top: 7px;
        }

        .strength-wrap {
            margin-top: 8px;
            white-space: nowrap;
        }

        .strength-circle {
            display: inline-block;
            width: 13px;
            height: 13px;
            border-radius: 50%;
            margin-right: 4px;
            border: 1px solid #cbd5e1;
            vertical-align: middle;
        }

        .filled-green {
            background: #16a34a;
            border-color: #16a34a;
        }

        .filled-amber {
            background: #f59e0b;
            border-color: #f59e0b;
        }

        .filled-grey {
            background: #64748b;
            border-color: #64748b;
        }

        .empty {
            background: #f8fafc;
        }

        .section-label {
            font-size: 13px;
            font-weight: 800;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: .6px;
            margin: 18px 0 8px;
        }

        .level-box {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 12px 14px;
            background: #f8fafc;
        }

        .level-value {
            font-size: 20px;
            font-weight: 800;
            color: #0f172a;
        }

        .level-caption {
            font-size: 11px;
            color: #64748b;
        }

        .action-box {
            border-radius: 12px;
            padding: 13px 16px;
            background: #eef2ff;
            border: 1px solid #c7d2fe;
            font-weight: 800;
            color: #312e81;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _rank_result(result: pd.DataFrame) -> pd.DataFrame:
    if result.empty:
        return result

    state_rank = {
        "STRONG_BULLISH": 8,
        "STRONG_BEARISH": 8,
        "STRONG_NEAR_LEVEL": 7,
        "ACTIVE_BULLISH": 6,
        "ACTIVE_BEARISH": 6,
        "WAIT_BREAK_CONFIRMATION": 5,
        "DEVELOPING": 4,
        "DIRECTIONAL_UNCONFIRMED": 2,
        "WATCH": 1,
        "INSUFFICIENT_DATA": 0,
    }

    out = result.copy()
    out["_state_rank"] = out["state"].map(state_rank).fillna(0)
    out = out.sort_values(
        ["_state_rank", "strength", "price_change_pct"],
        ascending=[False, False, False],
        na_position="last",
    )
    return out


def _render_candidate_cards(result: pd.DataFrame) -> None:
    candidates = result[
        result["state"].isin(QUALIFIED_STATES)
    ].copy()
    candidates = _rank_result(candidates).head(8)

    if candidates.empty:
        st.info("No qualified intraday candidates at this snapshot.")
        return

    st.markdown('<div class="section-label">Top intraday decisions</div>', unsafe_allow_html=True)

    for start in range(0, len(candidates), 4):
        rowset = candidates.iloc[start:start + 4]
        cols = st.columns(4)

        for col, (_, row) in zip(cols, rowset.iterrows()):
            with col:
                direction = _direction_text(row["direction"])
                decision = _decision_text(row)
                price = row.get("reference_price")
                price_change = row.get("price_change_pct")
                support = row.get("support")
                resistance = row.get("resistance")

                st.markdown(
                    f"""
                    <div class="decision-card">
                      <div class="decision-symbol">{row['symbol']}</div>
                      <div class="decision-state">{decision}</div>
                      <div class="decision-meta">{direction}</div>
                      <div class="strength-wrap">
                        {_strength_html(int(row.get('strength', 0) or 0))}
                        <span style="font-size:12px;color:#475569;margin-left:5px;">
                          {row.get('strength_label', '')}
                        </span>
                      </div>
                      <div class="decision-meta">
                        CMP {price:.2f} &nbsp; | &nbsp; Move {price_change:+.2f}%
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if row["direction"] == "BULLISH":
                    level_text = (
                        f"R {resistance:.2f}"
                        if pd.notna(resistance)
                        else "R —"
                    )
                elif row["direction"] == "BEARISH":
                    level_text = (
                        f"S {support:.2f}"
                        if pd.notna(support)
                        else "S —"
                    )
                else:
                    level_text = "S/R —"

                st.caption(
                    f"{level_text}  •  {row.get('opportunity', 'WATCH')}  •  "
                    f"{row.get('action', 'WATCH')}"
                )


def _render_detail(result: pd.DataFrame) -> None:
    if result.empty:
        return

    ranked = _rank_result(result)
    symbol = st.selectbox(
        "Inspect decision",
        ranked["symbol"].tolist(),
        key="ds_candidate",
    )
    row = ranked.loc[ranked.symbol == symbol].iloc[0]

    st.markdown(
        f"""
        <div class="section-label">Decision detail — {symbol}</div>
        <div class="action-box">
            {_decision_text(row)} &nbsp; | &nbsp;
            {_direction_text(row['direction'])} &nbsp; | &nbsp;
            ACTION: {row.get('action', 'WATCH')}
        </div>
        """,
        unsafe_allow_html=True,
    )

    a, b, c, d, e = st.columns(5)

    with a:
        st.markdown(
            f'<div class="level-box"><div class="level-caption">CMP</div>'
            f'<div class="level-value">{row["reference_price"]:.2f}</div></div>',
            unsafe_allow_html=True,
        )
    with b:
        value = row.get("support")
        text = "—" if pd.isna(value) else f"{value:.2f}"
        st.markdown(
            f'<div class="level-box"><div class="level-caption">SUPPORT</div>'
            f'<div class="level-value">{text}</div></div>',
            unsafe_allow_html=True,
        )
    with c:
        value = row.get("resistance")
        text = "—" if pd.isna(value) else f"{value:.2f}"
        st.markdown(
            f'<div class="level-box"><div class="level-caption">RESISTANCE</div>'
            f'<div class="level-value">{text}</div></div>',
            unsafe_allow_html=True,
        )
    with d:
        value = row.get("price_change_pct")
        text = "—" if pd.isna(value) else f"{value:+.2f}%"
        st.markdown(
            f'<div class="level-box"><div class="level-caption">PRICE MOVE</div>'
            f'<div class="level-value">{text}</div></div>',
            unsafe_allow_html=True,
        )
    with e:
        st.markdown(
            f'<div class="level-box"><div class="level-caption">STRENGTH</div>'
            f'<div class="level-value">{int(row["strength"])}/5</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-label">Why this direction?</div>', unsafe_allow_html=True)
    reasons = row.get("reasons", [])
    for reason in reasons:
        st.write(f"• {reason}")

    factors = row.get("strength_factors", [])
    if factors:
        st.caption(
            "Strength confirmation: " + " • ".join(factors)
        )

    # Raw indicators remain available only behind an explicit diagnostic
    # expander. They are not part of the decision table.
    with st.expander("Diagnostic evidence (optional)", expanded=False):
        st.write(
            {
                "ATM Straddle %": row.get("straddle_pct"),
                "ATM Straddle change %": row.get("straddle_delta_pct"),
                "Straddle stage": row.get("straddle_stage"),
                "IV change %": row.get("iv_change_pct"),
                "PCR change %": row.get("pcr_change_pct"),
                "OI evidence": row.get("oi_evidence"),
                "Options structure": row.get("options_structure"),
                "Futures buildup": row.get("futures_buildup"),
                "Futures OI change %": row.get("futures_oi_change_pct"),
                "Volume change %": row.get("volume_change_pct"),
                "S/R location": row.get("location"),
                "Level distance %": row.get("level_distance_pct"),
                "Persistence": row.get("persistence"),
            }
        )


def _render_timeline(timeline: pd.DataFrame) -> None:
    if timeline.empty:
        st.info("No qualifying state changes found in the selected folder.")
        return

    st.markdown('<div class="section-label">Intraday decision timeline</div>', unsafe_allow_html=True)

    view = timeline.copy()
    view["Time"] = pd.to_datetime(view["timestamp"]).dt.strftime("%H:%M")
    view["Decision"] = view.apply(
        lambda r: _decision_text(pd.Series({"state": r["state"]})),
        axis=1,
    )
    view["Direction"] = view["direction"].map(
        {"BULLISH": "▲ BULLISH", "BEARISH": "▼ BEARISH"}
    ).fillna("—")
    view["Strength"] = view["strength"].map(
        lambda x: "●" * int(x or 0) + "○" * (5 - int(x or 0))
    )

    st.dataframe(
        view[
            ["Time", "symbol", "Decision", "Direction", "Strength", "action"]
        ].rename(
            columns={
                "symbol": "Stock",
                "action": "Action",
            }
        ),
        width="stretch",
        hide_index=True,
    )


def render() -> None:
    _inject_css()

    st.markdown(
        """
        <div class="hero">
          <div class="hero-title">NTIS SDL — Intraday Decision Center</div>
          <div class="hero-subtitle">
            Precise candidate ranking • directional strength • breakout levels • action
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Apply pending date before the date widget is instantiated.
    pending = st.session_state.pop("ds_pending_date", None)
    if pending is not None:
        pending_date = _as_date(pending)
        if pending_date is not None:
            st.session_state["ds_date"] = pending_date

    selected_date = st.date_input(
        "Trading date",
        value=date.today(),
        key="ds_trading_date",
    )
    trading_date = selected_date.isoformat()

    sources = _discover_sources(trading_date)
    if not sources:
        st.info("No eligible Daywise source files found for the selected date.")
        return

    mode = st.radio(
        "Read mode",
        ["Latest File", "All Files / Day Replay"],
        horizontal=True,
        key="ds_read_mode",
    )

    if mode == "Latest File":
        selected_path = sources[-1]

        st.caption(
            f"Latest snapshot: {selected_path.name}  •  "
            f"{datetime.fromtimestamp(selected_path.stat().st_mtime):%d %b %Y %H:%M:%S}"
        )

        if st.button(
            "▶ PROCESS LATEST SNAPSHOT",
            type="primary",
            width="stretch",
            key="ds_process_latest",
        ):
            try:
                st.session_state["ds_result"] = process_selected_source(
                    selected_path,
                    trading_date,
                )
                st.session_state["ds_timeline"] = pd.DataFrame()
                st.session_state["ds_source"] = selected_path.name
                st.success("Latest snapshot processed.")
            except Exception as exc:
                st.error(
                    f"Processing failed: {type(exc).__name__}: {exc}"
                )

    else:
        st.caption(
            f"Day replay: {len(sources)} eligible snapshots will be read "
            "chronologically. Source files are read-only."
        )

        if st.button(
            "▶ PROCESS ALL FILES",
            type="primary",
            width="stretch",
            key="ds_process_all",
        ):
            try:
                latest, timeline = process_all_sources(
                    sources,
                    trading_date,
                )
                st.session_state["ds_result"] = latest
                st.session_state["ds_timeline"] = timeline
                st.session_state["ds_source"] = (
                    f"{len(sources)} files / day replay"
                )
                st.success(
                    f"Processed {len(sources)} snapshots chronologically."
                )
            except Exception as exc:
                st.error(
                    f"Replay failed: {type(exc).__name__}: {exc}"
                )

    result = st.session_state.get("ds_result")
    if result is None or result.empty:
        st.info(
            "Choose Latest File or All Files / Day Replay and process the data."
        )
        return

    result = _rank_result(result)

    # Compact decision summary — no raw indicator counters.
    candidates = result[
        result["state"].isin(QUALIFIED_STATES)
    ]
    strong = candidates[candidates["strength"] >= 4]
    bullish = candidates[candidates["direction"] == "BULLISH"]
    bearish = candidates[candidates["direction"] == "BEARISH"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tradable Candidates", len(candidates))
    c2.metric("Strong (4–5/5)", len(strong))
    c3.metric("Bullish", len(bullish))
    c4.metric("Bearish", len(bearish))

    _render_candidate_cards(result)

    st.markdown(
        '<div class="section-label">Decision table</div>',
        unsafe_allow_html=True,
    )

    table = result[
        result["state"].isin(QUALIFIED_STATES)
    ].copy()

    if table.empty:
        st.info("No qualified candidates in the latest snapshot.")
    else:
        table["Strength"] = table["strength"].map(
            lambda x: "●" * int(x or 0) + "○" * (5 - int(x or 0))
        )
        table["Decision"] = table.apply(_decision_text, axis=1)
        table["Direction"] = table["direction"].map(
            {"BULLISH": "▲ BULLISH", "BEARISH": "▼ BEARISH"}
        ).fillna("—")
        table["Price"] = table["reference_price"].map(
            lambda x: "—" if pd.isna(x) else f"{x:.2f}"
        )
        table["Move"] = table["price_change_pct"].map(
            lambda x: "—" if pd.isna(x) else f"{x:+.2f}%"
        )
        table["Support"] = table["support"].map(
            lambda x: "—" if pd.isna(x) else f"{x:.2f}"
        )
        table["Resistance"] = table["resistance"].map(
            lambda x: "—" if pd.isna(x) else f"{x:.2f}"
        )

        # Only decision-essential fields are exposed.
        st.dataframe(
            table[
                [
                    "symbol",
                    "Strength",
                    "Decision",
                    "Direction",
                    "Price",
                    "Support",
                    "Resistance",
                    "opportunity",
                    "action",
                ]
            ].rename(
                columns={
                    "symbol": "Stock",
                    "opportunity": "Opportunity",
                    "action": "Action",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    _render_detail(result)

    timeline = st.session_state.get("ds_timeline")
    if isinstance(timeline, pd.DataFrame) and not timeline.empty:
        _render_timeline(timeline)

    st.caption(
        f"Source: {st.session_state.get('ds_source', 'current snapshot')}  •  "
        "Git repository is read-only. External source files are read-only. "
        "The +/-0.75% price gate remains authoritative. "
        "Straddle/IV/OI/PCR/Futures/Volume are supporting evidence, not hidden new trade triggers."
    )
