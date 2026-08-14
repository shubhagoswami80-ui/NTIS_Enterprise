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
from approaching_breakout import load_approaching_breakouts


st.set_page_config(
    page_title="SDL — Straddle Breakout",
    page_icon="📈",
    layout="wide",
)

APPROACHING_CSV = Path(EVENT_CSV).parent / "approaching_breakouts.csv"


st.markdown(
    """
    <style>
    .stApp { background:#f7f8fc; }
    .block-container { max-width:1500px; padding-top:1rem; padding-bottom:2rem; }

    .sdl-header {
        background:linear-gradient(105deg,#0d1830 0%,#17264b 62%,#243a72 100%);
        color:white; padding:20px 24px; border-radius:14px; margin-bottom:16px;
        box-shadow:0 8px 24px rgba(20,34,72,.12);
    }
    .sdl-header-title { font-size:27px; font-weight:750; line-height:1.1; }
    .sdl-header-subtitle { font-size:13px; opacity:.86; margin-top:5px; }

    .section-card {
        background:white; border:1px solid #e7eaf2; border-radius:14px;
        padding:17px; margin:13px 0; box-shadow:0 4px 16px rgba(20,34,72,.055);
    }
    .section-title { color:#17233f; font-size:19px; font-weight:720; margin-bottom:10px; }
    .section-subtitle { color:#687188; font-size:12px; margin-bottom:12px; }

    .metric-card {
        background:#fbfcff; border:1px solid #e8ebf3; border-radius:12px;
        padding:14px 15px; min-height:88px;
    }
    .metric-label { color:#6d7588; font-size:10px; font-weight:750;
        letter-spacing:.06em; text-transform:uppercase; }
    .metric-value { color:#17233f; font-size:22px; font-weight:760; margin-top:5px; }
    .metric-detail { color:#7b8394; font-size:11px; margin-top:2px; }

    .up-card { background:#f1fbf6; border-color:#b9ead2; }
    .down-card { background:#fff4f4; border-color:#f1c4c4; }
    .fifty-card { background:#f5f2ff; border-color:#d8cff9; }

    .status-pill { display:inline-block; padding:4px 9px; border-radius:999px;
        font-size:10px; font-weight:750; background:#edf9f2; color:#16824e;
        border:1px solid #bce8cf; }

    .muted { color:#747d90; font-size:12px; }

    div.stButton > button { border-radius:9px; }
    div.stButton > button[kind="primary"] {
        background:linear-gradient(90deg,#5844d8,#6c4ee6);
        border:0; border-radius:9px; font-weight:700; min-height:42px;
    }
    [data-testid="stDataFrame"] {
        border:1px solid #e6e9f1; border-radius:10px; overflow:hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _normalise_date(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _events() -> pd.DataFrame:
    value = load_events(EVENT_CSV)
    return pd.DataFrame() if value is None else value.copy()


def _today_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty or "trading_date" not in events.columns:
        return pd.DataFrame()

    dates = events["trading_date"].map(_normalise_date)
    return events.loc[
        dates == pd.Timestamp.now().date().isoformat()
    ].copy()


def _latest_workbook():
    today = pd.Timestamp.now().date().isoformat()

    try:
        files = [Path(p) for p in discover_historical_snapshots(today)]
        files = [p for p in files if p.is_file()]
    except Exception:
        return None, None

    if not files:
        return None, None

    latest = max(files, key=lambda p: p.stat().st_mtime)
    modified = pd.Timestamp.fromtimestamp(
        latest.stat().st_mtime
    ).strftime("%d %b %Y, %H:%M:%S")

    return latest, modified


def _last_processed(events: pd.DataFrame) -> str:
    if events.empty or "observation_timestamp" not in events.columns:
        return "—"

    values = pd.to_datetime(
        events["observation_timestamp"],
        errors="coerce",
    ).dropna()

    return (
        "—"
        if values.empty
        else values.max().strftime("%d %b %Y, %H:%M:%S")
    )


def _event_display(
    df: pd.DataFrame,
    historical: bool = False,
) -> pd.DataFrame:
    mapping = [
        ("observation_timestamp", "Observation Time"),
        ("symbol", "Symbol"),
        ("direction", "Direction"),
        ("open_price", "Open Price"),
        ("current_price", "Current Price"),
        ("opening_straddle_premium", "Frozen Straddle"),
        ("expected_1x_price", "1× Breakout Level"),
        ("breakout_distance", "Distance to 1×"),
    ]

    if historical:
        mapping.append(("strategy_version", "Strategy Version"))

    out = pd.DataFrame(index=df.index)

    for source, label in mapping:
        if source in df.columns:
            out[label] = df[source].to_numpy()

    return out.reset_index(drop=True)


def _approaching_display(df: pd.DataFrame) -> pd.DataFrame:
    mapping = [
        ("observation_timestamp", "First Observed"),
        ("symbol", "Symbol"),
        ("direction", "Direction"),
        ("open_price", "Open Price"),
        ("current_price", "Price at 50%+"),
        ("opening_straddle_premium", "Frozen Straddle"),
        ("approaching_level", "50% Level"),
        ("breakout_level", "1× Level"),
        ("distance_to_breakout", "Distance to 1×"),
        ("approach_progress_pct", "Progress %"),
    ]

    out = pd.DataFrame(index=df.index)

    for source, label in mapping:
        if source in df.columns:
            out[label] = df[source].to_numpy()

    return out.reset_index(drop=True)


st.markdown(
    """
    <div class="sdl-header">
        <div class="sdl-header-title">SDL — Straddle Breakout</div>
        <div class="sdl-header-subtitle">
            Phase-1: breakout monitoring, 50% reach evidence and historical evidence
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


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
        "Process the most recent workbook from the configured Daywise source repository."
        "</div>",
        unsafe_allow_html=True,
    )


if process_clicked:
    try:
        latest, _, _, note = process_latest_snapshot_for_today()

        if latest is None:
            st.warning(note)
        else:
            st.success(f"Processed: {Path(latest).name}")
            st.caption(note)
            st.rerun()

    except Exception as exc:
        st.error(f"Processing failed: {exc}")


events = _events()
today_events = _today_events(events)

latest, file_modified = _latest_workbook()

approaching = load_approaching_breakouts(
    APPROACHING_CSV
)

today = pd.Timestamp.now().date().isoformat()

if not approaching.empty and "trading_date" in approaching.columns:
    approaching_dates = approaching["trading_date"].map(_normalise_date)
    today_50 = approaching.loc[
        approaching_dates == today
    ].copy()
else:
    today_50 = pd.DataFrame()

if not today_50.empty and {"trading_date", "symbol"}.issubset(
    today_50.columns
):
    today_50 = today_50.drop_duplicates(
        ["trading_date", "symbol"],
        keep="first",
    )


up_count = (
    int(
        (
            today_events["direction"]
            .astype(str)
            .str.upper()
            == "UP"
        ).sum()
    )
    if not today_events.empty and "direction" in today_events.columns
    else 0
)

down_count = (
    int(
        (
            today_events["direction"]
            .astype(str)
            .str.upper()
            == "DOWN"
        ).sum()
    )
    if not today_events.empty and "direction" in today_events.columns
    else 0
)


# ---------------------------------------------------------------------------
# Snapshot status
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="section-card"><div class="section-title">◷ Snapshot Status</div>',
    unsafe_allow_html=True,
)

c1, c2, c3, c4, c5, c6 = st.columns(6)

metrics = [
    (
        "Latest Workbook",
        latest.name if latest else "Not processed",
        "Current source",
        "metric-card",
    ),
    (
        "File Modified",
        file_modified or "—",
        "Filesystem timestamp",
        "metric-card",
    ),
    (
        "Last Processed",
        _last_processed(events),
        "Latest recorded observation",
        "metric-card",
    ),
    (
        "Breakouts",
        str(len(today_events)),
        "Today",
        "metric-card up-card",
    ),
    (
        "Breakdowns",
        str(down_count),
        "DOWN",
        "metric-card down-card",
    ),
    (
        "50% Reached",
        str(len(today_50)),
        "Unique stocks today",
        "metric-card fifty-card",
    ),
]

for col, (label, value, detail, card_class) in zip(
    [c1, c2, c3, c4, c5, c6],
    metrics,
):
    col.markdown(
        f"""
        <div class="{card_class}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-detail">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Today's breakout events
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="section-card"><div class="section-title">◎ Today\'s Straddle Breakouts</div>',
    unsafe_allow_html=True,
)

if today_events.empty:
    st.info("No recorded straddle breakouts for today.")
else:
    st.dataframe(
        _event_display(today_events),
        width="stretch",
        hide_index=True,
    )

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Today's 50% reached layer
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="section-card"><div class="section-title">◈ Today\'s 50% Reached Stocks</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-subtitle">'
    "First observed stocks that reached at least 50% of their own frozen opening "
    "straddle. Reaching 100% is not required. Each stock is recorded once per trading day."
    "</div>",
    unsafe_allow_html=True,
)

if today_50.empty:
    st.info(
        "No stocks have reached 50% of the frozen opening straddle for today."
    )
else:
    st.dataframe(
        _approaching_display(today_50),
        width="stretch",
        hide_index=True,
    )

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Historical evidence
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="section-card"><div class="section-title">▣ Historical Evidence</div>',
    unsafe_allow_html=True,
)

tab_50, tab_breakouts = st.tabs(
    ["50% Reached History", "Breakout History"]
)


with tab_50:
    if approaching.empty or "trading_date" not in approaching.columns:
        st.info("No historical 50% records available yet.")
    else:
        historical_50 = approaching.copy()
        historical_50["_date"] = historical_50[
            "trading_date"
        ].map(_normalise_date)

        historical_50 = historical_50.drop_duplicates(
            ["_date", "symbol"],
            keep="first",
        )

        dates = sorted(
            historical_50["_date"].dropna().unique(),
            reverse=True,
        )

        if not dates:
            st.info("No valid historical 50% trading dates found.")
        else:
            selected_50 = st.selectbox(
                "Trading Date — 50% layer",
                dates,
                key="approach_date",
            )

            selected_50_df = historical_50.loc[
                historical_50["_date"] == selected_50
            ].drop(columns=["_date"]).copy()

            st.caption(
                f"{len(selected_50_df)} unique stocks — "
                "uniqueness key: (trading date, symbol)"
            )

            st.dataframe(
                _approaching_display(selected_50_df),
                width="stretch",
                hide_index=True,
            )

            st.download_button(
                "⇩  Export 50% CSV",
                data=selected_50_df.to_csv(index=False).encode("utf-8"),
                file_name=f"sdl_50pct_{selected_50}.csv",
                mime="text/csv",
                width="stretch",
            )


with tab_breakouts:
    if events.empty or "trading_date" not in events.columns:
        st.info("No historical breakout events recorded yet.")
    else:
        historical_events = events.copy()
        historical_events["_date"] = historical_events[
            "trading_date"
        ].map(_normalise_date)

        dates = sorted(
            historical_events["_date"].dropna().unique(),
            reverse=True,
        )

        if not dates:
            st.info("No valid historical breakout dates found.")
        else:
            selected_breakout = st.selectbox(
                "Trading Date — breakout layer",
                dates,
                key="breakout_date",
            )

            selected_breakout_df = historical_events.loc[
                historical_events["_date"] == selected_breakout
            ].drop(columns=["_date"]).copy()

            st.dataframe(
                _event_display(
                    selected_breakout_df,
                    historical=True,
                ),
                width="stretch",
                hide_index=True,
            )

            st.download_button(
                "⇩  Export Breakout CSV",
                data=selected_breakout_df.to_csv(
                    index=False
                ).encode("utf-8"),
                file_name=f"sdl_breakouts_{selected_breakout}.csv",
                mime="text/csv",
                width="stretch",
            )


st.markdown("</div>", unsafe_allow_html=True)


st.markdown(
    """
    <div class="muted" style="margin-top:14px;">
        Phase-1 only: no SL, target outcome, success/failure or P&amp;L is calculated.
        &nbsp;&nbsp;
        <span class="status-pill">● System Healthy</span>
    </div>
    """,
    unsafe_allow_html=True,
)
