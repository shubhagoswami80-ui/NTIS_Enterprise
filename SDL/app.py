from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from config import EVENT_CSV
from pipeline import (
    discover_historical_snapshots,
    process_latest_snapshot_for_today,
)
from storage import load_events


st.set_page_config(
    page_title="SDL — Straddle Breakout",
    page_icon="📈",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Visual system
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .stApp { background: #f7f8fc; }

    .block-container {
        max-width: 1240px;
        padding-top: 1.15rem;
        padding-bottom: 1rem;
    }

    .sdl-header {
        background: linear-gradient(105deg, #0d1830 0%, #17264b 62%, #243a72 100%);
        color: white;
        padding: 17px 20px 15px 20px;
        border-radius: 11px;
        margin-bottom: 11px;
        box-shadow: 0 8px 24px rgba(20, 34, 72, .12);
    }

    .sdl-header-title {
        font-size: 23px;
        font-weight: 750;
        line-height: 1.25;
        margin: 0;
    }

    .sdl-header-subtitle {
        font-size: 12px;
        opacity: .88;
        margin-top: 3px;
    }

    .section-card {
        background: white;
        border: 1px solid #e7eaf2;
        border-radius: 10px;
        padding: 12px;
        margin: 9px 0;
        box-shadow: 0 4px 16px rgba(20, 34, 72, .055);
    }

    .section-title {
        color: #17233f;
        font-size: 17px;
        font-weight: 720;
        margin-bottom: 8px;
    }

    .metric-card {
        background: #fbfcff;
        border: 1px solid #e8ebf3;
        border-radius: 9px;
        padding: 11px 12px;
        min-height: 76px;
    }

    .metric-label {
        color: #6d7588;
        font-size: 9px;
        font-weight: 750;
        letter-spacing: .06em;
        text-transform: uppercase;
    }

    .metric-value {
        color: #17233f;
        font-size: 20px;
        font-weight: 760;
        margin-top: 4px;
    }

    .metric-detail {
        color: #7b8394;
        font-size: 10px;
        margin-top: 2px;
    }

    .up-card {
        background: #f1fbf6;
        border-color: #b9ead2;
    }

    .down-card {
        background: #fff4f4;
        border-color: #f1c4c4;
    }

    .status-pill {
        display: inline-block;
        padding: 4px 9px;
        border-radius: 999px;
        font-size: 10px;
        font-weight: 750;
        background: #edf9f2;
        color: #16824e;
        border: 1px solid #bce8cf;
    }

    .muted {
        color: #747d90;
        font-size: 11px;
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #5844d8, #6c4ee6);
        border: 0;
        border-radius: 10px;
        font-weight: 700;
        min-height: 40px;
    }

    div.stButton > button,
    div[data-testid="stDownloadButton"] button {
        border-radius: 10px;
        font-size: 14px;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #e6e9f1;
        border-radius: 8px;
        overflow: hidden;
    }

    .footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #747d90;
        font-size: 10px;
        margin-top: 10px;
        padding-top: 7px;
        border-top: 1px solid #e6e9f1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _events() -> pd.DataFrame:
    events = load_events(EVENT_CSV)
    if events is None:
        return pd.DataFrame()
    return events.copy()


def _normalise_trading_date(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


def _today_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty or "trading_date" not in events.columns:
        return pd.DataFrame()

    today = pd.Timestamp.now().date().isoformat()
    dates = events["trading_date"].map(_normalise_trading_date)

    return events.loc[dates == today].copy()


def _latest_workbook() -> tuple[Path | None, str | None]:
    today = pd.Timestamp.now().date().isoformat()

    try:
        files = list(discover_historical_snapshots(today))
    except Exception:
        return None, None

    valid_files = []
    for item in files:
        path = Path(item)
        try:
            if path.is_file():
                valid_files.append(path)
        except OSError:
            continue

    if not valid_files:
        return None, None

    latest = max(valid_files, key=lambda p: p.stat().st_mtime)
    modified = pd.Timestamp.fromtimestamp(latest.stat().st_mtime).strftime(
        "%d %b %Y, %H:%M:%S"
    )
    return latest, modified


def _last_processed(events: pd.DataFrame) -> str:
    if events.empty or "observation_timestamp" not in events.columns:
        return "—"

    values = pd.to_datetime(
        events["observation_timestamp"], errors="coerce"
    ).dropna()

    if values.empty:
        return "—"

    return values.max().strftime("%d %b %Y, %H:%M:%S")


def _display_events(
    df: pd.DataFrame,
    historical: bool = False,
) -> pd.DataFrame:
    """
    Build the dashboard table explicitly from named source columns.

    This avoids relying on positional/implicit column alignment and ensures
    every displayed heading corresponds to the exact source field.
    """
    mapping = [
        ("observation_timestamp", "Observation Time"),
        ("symbol", "Symbol"),
        ("direction", "Direction"),
        ("open_price", "Open Price"),
        ("current_price", "Current Price"),
        ("opening_straddle_premium", "Opening Straddle"),
        ("expected_1x_price", "Expected 1× Price"),
        ("breakout_distance", "Breakout Distance"),
    ]

    if historical:
        mapping.append(("strategy_version", "Strategy Version"))

    available = [(source, label) for source, label in mapping if source in df.columns]

    if not available:
        return pd.DataFrame()

    # Explicitly construct each displayed column by source name.
    display = pd.DataFrame(index=df.index)
    for source, label in available:
        display[label] = df[source].to_numpy()

    return display.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="sdl-header">
        <div class="sdl-header-title">SDL — Straddle Breakout</div>
        <div class="sdl-header-subtitle">
            Phase-1: Breakout monitoring and historical breakout evidence
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Processing action
# ---------------------------------------------------------------------------

action_col, info_col = st.columns([1, 2.2])

with action_col:
    process_clicked = st.button(
        "▶  Process Latest Snapshot",
        type="primary",
        width="stretch",
    )

with info_col:
    st.markdown(
        '<div class="muted" style="padding-top:11px;">'
        "Process the most recent workbook currently available in the configured "
        "Daywise source repository."
        "</div>",
        unsafe_allow_html=True,
    )

if process_clicked:
    try:
        latest, new_events, _, note = process_latest_snapshot_for_today()

        if latest is None:
            st.warning(note)
        else:
            st.success(f"Processed latest workbook: {latest.name}")
            st.caption(note)
            st.rerun()
    except Exception as exc:
        st.error(f"Processing failed: {exc}")


# ---------------------------------------------------------------------------
# Snapshot status
# ---------------------------------------------------------------------------

events = _events()
today_events = _today_events(events)
latest, file_modified = _latest_workbook()

up_count = (
    int((today_events["direction"].astype(str).str.upper() == "UP").sum())
    if not today_events.empty and "direction" in today_events.columns
    else 0
)

down_count = (
    int((today_events["direction"].astype(str).str.upper() == "DOWN").sum())
    if not today_events.empty and "direction" in today_events.columns
    else 0
)

latest_name = latest.name if latest else "Not processed"
last_processed = _last_processed(events)

st.markdown(
    '<div class="section-card"><div class="section-title">◷ Latest Snapshot</div>',
    unsafe_allow_html=True,
)

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Latest Workbook</div>
            <div class="metric-value" style="font-size:18px;">{latest_name}</div>
            <div class="metric-detail">Current source selection</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">File Modified</div>
            <div class="metric-value" style="font-size:18px;">{file_modified or "—"}</div>
            <div class="metric-detail">Filesystem timestamp</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Last Processed</div>
            <div class="metric-value" style="font-size:18px;">{last_processed}</div>
            <div class="metric-detail">Latest recorded observation</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        f"""
        <div class="metric-card up-card">
            <div class="metric-label">Today's Breakouts</div>
            <div class="metric-value">{up_count}</div>
            <div class="metric-detail">UP</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c5:
    st.markdown(
        f"""
        <div class="metric-card down-card">
            <div class="metric-label">Today's Breakdowns</div>
            <div class="metric-value">{down_count}</div>
            <div class="metric-detail">DOWN</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Today's events
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="section-card"><div class="section-title">◎ Today\'s Straddle Breakouts</div>',
    unsafe_allow_html=True,
)

_, history_col = st.columns([5, 1])

with history_col:
    view_history = st.button("◷  View History", width="stretch")

if view_history:
    st.session_state["show_history"] = True

if today_events.empty:
    st.info("No recorded straddle breakouts for today.")
else:
    display_today = _display_events(today_events)

    if display_today.empty:
        st.info("Today's events exist, but no displayable event columns were found.")
    else:
        st.dataframe(
            display_today,
            width="stretch",
            hide_index=True,
        )

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Historical events
# ---------------------------------------------------------------------------

show_history = st.session_state.get("show_history", True)

if show_history:
    st.markdown(
        '<div class="section-card"><div class="section-title">▣ Earlier Straddle Breakouts</div>',
        unsafe_allow_html=True,
    )

    if events.empty or "trading_date" not in events.columns:
        st.info("No historical breakout events recorded yet.")
    else:
        # Normalize dates only for filtering/display selection.
        normalized_dates = events["trading_date"].map(_normalise_trading_date)
        dates = sorted(
            normalized_dates.dropna().unique(),
            reverse=True,
        )

        if not dates:
            st.info("No valid trading dates found in the event store.")
        else:
            filter_col, refresh_col, export_col = st.columns([2, 1, 1])

            with filter_col:
                selected = st.selectbox("Trading Date", dates)

            with refresh_col:
                if st.button("↻  Refresh", width="stretch"):
                    st.rerun()

            historical = events.loc[normalized_dates == selected].copy()

            with export_col:
                csv_data = historical.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⇩  Export CSV",
                    data=csv_data,
                    file_name=f"sdl_breakouts_{selected}.csv",
                    mime="text/csv",
                    width="stretch",
                )

            display_history = _display_events(
                historical,
                historical=True,
            )

            if display_history.empty:
                st.info("No displayable historical event columns were found.")
            else:
                st.dataframe(
                    display_history,
                    width="stretch",
                    hide_index=True,
                )

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="footer">
        <span>
            Phase-1 only: no SL, target outcome, success/failure or P&amp;L is calculated.
        </span>
        <span>
            <span class="status-pill">● System Healthy</span>
            &nbsp;&nbsp;
            Version: v1.0.0
            &nbsp;&nbsp;
            © 2026 SDL — Straddle Breakout
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)
