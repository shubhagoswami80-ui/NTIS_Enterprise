from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from config import EVENT_CSV
from pipeline import (
    discover_historical_snapshots,
    process_latest_snapshot_for_today,
    replay_trading_date,
    replay_all_available,
)
from source_loader import parse_observation_timestamp
from storage import load_events


st.set_page_config(
    page_title="SDL — Straddle Breakout Decision Center",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# SDL Decision Center visual system
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .stApp { background: #f7f8fc; }
    .block-container { max-width: 1380px; padding-top: 1.0rem; padding-bottom: 1.2rem; }

    .sdl-header {
        background: linear-gradient(105deg, #0d1830 0%, #17264b 62%, #243a72 100%);
        color: white; padding: 18px 22px; border-radius: 12px;
        margin-bottom: 12px; box-shadow: 0 7px 20px rgba(20,34,72,.10);
    }
    .sdl-title { font-size: 25px; font-weight: 760; margin: 0; }
    .sdl-subtitle { font-size: 12px; opacity: .88; margin-top: 4px; }

    .card {
        background: white; border: 1px solid #e6e9f1; border-radius: 11px;
        padding: 13px 15px; margin: 9px 0;
        box-shadow: 0 3px 12px rgba(20,34,72,.045);
    }
    .card-title { color: #17233f; font-size: 17px; font-weight: 740; margin-bottom: 5px; }
    .card-subtitle { color: #737c90; font-size: 11px; margin-bottom: 9px; }

    .decision {
        border-radius: 10px; padding: 13px 15px; margin: 4px 0;
        border: 1px solid #e5e8ef;
    }
    .decision-up { background:#edf9f1; border-color:#b9e5c9; color:#146c3b; }
    .decision-down { background:#fff0f0; border-color:#efc2c2; color:#982020; }
    .decision-partial { background:#fff6e5; border-color:#f0d59d; color:#8b5a00; }
    .decision-none { background:#f3f4f6; color:#5d6472; }

    .decision-main { font-size: 18px; font-weight: 780; }
    .decision-meta { font-size: 11px; margin-top: 4px; opacity: .85; }

    .metric {
        background:#fbfcff; border:1px solid #e6e9f1; border-radius:9px;
        padding:10px 12px; min-height:68px;
    }
    .metric-label { color:#747d90; font-size:9px; font-weight:760; letter-spacing:.06em; text-transform:uppercase; }
    .metric-value { color:#17233f; font-size:20px; font-weight:760; margin-top:3px; }
    .metric-detail { color:#7c8495; font-size:10px; }

    .evidence-ok { color:#177245; font-weight:700; }
    .evidence-missing { color:#9a6700; font-weight:700; }
    .muted { color:#737c90; font-size:11px; }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg,#5844d8,#6c4ee6);
        border:0; border-radius:9px; font-weight:700; min-height:40px;
    }
    div.stButton > button { border-radius:9px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Existing pipeline helpers — no new processing engine
# ---------------------------------------------------------------------------

def _events() -> pd.DataFrame:
    df = load_events(EVENT_CSV)
    return df.copy() if df is not None else pd.DataFrame()


def _source_timestamp(path: Path) -> pd.Timestamp:
    try:
        return parse_observation_timestamp(path)
    except Exception:
        try:
            return pd.Timestamp.fromtimestamp(path.stat().st_mtime)
        except Exception:
            return pd.NaT


def _today_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty or "trading_date" not in events.columns:
        return pd.DataFrame()
    today = pd.Timestamp.now().date().isoformat()
    return events[events["trading_date"].astype(str) == today].copy()


def _available_source_dates() -> list[str]:
    try:
        files = [Path(p) for p in discover_historical_snapshots()]
    except Exception:
        return []
    dates = []
    for p in files:
        ts = _source_timestamp(p)
        if pd.notna(ts):
            dates.append(ts.date().isoformat())
    return sorted(set(dates), reverse=True)


def _latest_source() -> tuple[Path | None, pd.Timestamp | None]:
    today = pd.Timestamp.now().date().isoformat()
    try:
        files = [Path(p) for p in discover_historical_snapshots(today)]
    except Exception:
        return None, None
    if not files:
        return None, None
    valid = [(p, _source_timestamp(p)) for p in files]
    valid = [(p, ts) for p, ts in valid if pd.notna(ts)]
    if not valid:
        return None, None
    return max(valid, key=lambda x: x[1])


def _fmt_ts(value) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return "—"
    return ts.strftime("%d %b %Y, %H:%M:%S")


def _num(value):
    return pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]


def _evidence_state(row: pd.Series) -> tuple[str, int, int]:
    fields = [
        "price_chg_pct",
        "oi_chg_pct",
        "ce_oi_chg_pct",
        "pe_oi_chg_pct",
        "pe_minus_ce_oi_chg",
        "iv_chg_pct",
        "pcr_chg_pct",
    ]
    present = 0
    for field in fields:
        if field in row.index and pd.notna(_num(row.get(field))):
            present += 1
    total = len(fields)
    return ("COMPLETE" if present == total else "PARTIAL"), present, total


def _decision(row: pd.Series) -> tuple[str, str]:
    direction = str(row.get("direction", "")).strip().upper()
    evidence, present, total = _evidence_state(row)

    if direction == "UP":
        label = "🟢 UP BREAKOUT"
        css = "decision-up"
    elif direction == "DOWN":
        label = "🔴 DOWN BREAKOUT"
        css = "decision-down"
    else:
        label = "⚪ BREAKOUT — DIRECTION UNAVAILABLE"
        css = "decision-none"

    if evidence == "PARTIAL":
        label += " · EVIDENCE PARTIAL"
        css = "decision-partial" if direction not in {"UP", "DOWN"} else css

    return label, css


def _decision_queue(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    out = df.copy()
    out["_timestamp"] = pd.to_datetime(
        out.get("observation_timestamp"), errors="coerce"
    )
    out["_direction_order"] = out.get("direction", "").astype(str).str.upper().map(
        {"UP": 0, "DOWN": 1}
    ).fillna(2)

    out = out.sort_values(
        ["_timestamp", "_direction_order"],
        ascending=[False, True],
        na_position="last",
    )

    rows = []
    for _, row in out.iterrows():
        label, _ = _decision(row)
        evidence, present, total = _evidence_state(row)
        rows.append(
            {
                "TRIGGER": _fmt_ts(row.get("observation_timestamp")),
                "SYMBOL": str(row.get("symbol", "")).upper(),
                "DECISION": label,
                "EVIDENCE": f"{present}/{total}",
                "BREAKOUT DIST": row.get("breakout_distance"),
                "PRICE CHG %": row.get("price_chg_pct"),
                "FUT OI CHG %": row.get("oi_chg_pct"),
                "CE OI CHG %": row.get("ce_oi_chg_pct"),
                "PE OI CHG %": row.get("pe_oi_chg_pct"),
                "PE−CE OI CHG": row.get("pe_minus_ce_oi_chg"),
                "IV CHG %": row.get("iv_chg_pct"),
            }
        )
    return pd.DataFrame(rows)


def _evidence_table(row: pd.Series) -> pd.DataFrame:
    mapping = [
        ("Price Chg %", "price_chg_pct"),
        ("Futures OI Chg %", "oi_chg_pct"),
        ("CE OI Chg %", "ce_oi_chg_pct"),
        ("PE OI Chg %", "pe_oi_chg_pct"),
        ("PE−CE OI Chg", "pe_minus_ce_oi_chg"),
        ("IV Chg %", "iv_chg_pct"),
        ("PCR Chg %", "pcr_chg_pct"),
    ]
    records = []
    for label, key in mapping:
        value = row.get(key) if key in row.index else pd.NA
        records.append(
            {
                "EVIDENCE": label,
                "VALUE": value if pd.notna(value) else "MISSING",
                "STATE": "AVAILABLE" if pd.notna(value) else "MISSING",
            }
        )
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="sdl-header">
        <div class="sdl-title">SDL — Straddle Breakout Decision Center</div>
        <div class="sdl-subtitle">
            Decision-first view · exact trigger timestamp · existing SDL pipeline · no score/probability layer
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Processing / replay controls — reuse existing pipeline only
# ---------------------------------------------------------------------------

c1, c2, c3 = st.columns([1.2, 1.2, 2.0])

with c1:
    if st.button("▶ PROCESS LATEST", type="primary", width="stretch"):
        try:
            latest, new_events, _, note = process_latest_snapshot_for_today()
            if latest is None:
                st.warning(note)
            else:
                st.success(f"Processed {latest.name}")
                st.caption(note)
                st.rerun()
        except Exception as exc:
            st.error(f"Processing failed: {exc}")

available_dates = _available_source_dates()

with c2:
    replay_clicked = False
    if available_dates:
        replay_date = st.selectbox(
            "Replay date",
            available_dates,
            format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y"),
            label_visibility="collapsed",
        )
        replay_clicked = st.button("↻ REPLAY DAY", width="stretch")
    else:
        st.caption("No replay dates discovered.")

with c3:
    if st.button("↻ REPLAY ALL AVAILABLE", width="stretch"):
        try:
            results = replay_all_available()
            files = sum(int(r.get("files", 0)) for r in results)
            events = sum(int(r.get("events", 0)) for r in results)
            st.success(f"Replayed {len(results)} days · {files} files · {events} new first-breakout events")
            st.rerun()
        except Exception as exc:
            st.error(f"Full replay failed: {exc}")

if replay_clicked:
    try:
        result = replay_trading_date(replay_date)
        st.success(
            f"Replayed {result['trading_date']} · {result['files']} files · "
            f"{result['events']} new first-breakout events · "
            f"{result['first_timestamp'] or '—'} → {result['last_timestamp'] or '—'}"
        )
        st.rerun()
    except Exception as exc:
        st.error(f"Replay failed: {exc}")


# ---------------------------------------------------------------------------
# Decision Center
# ---------------------------------------------------------------------------

events = _events()
today = _today_events(events)
latest_source, latest_ts = _latest_source()

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">1. CURRENT DECISION QUEUE</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="card-subtitle">Only first-breakout events are shown here. '
    'The queue is the decision surface; raw evidence is below.</div>',
    unsafe_allow_html=True,
)

if today.empty:
    st.info("No first-breakout events have been recorded for today.")
else:
    q = _decision_queue(today)
    st.dataframe(q, width="stretch", hide_index=True)

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Snapshot status
# ---------------------------------------------------------------------------

up = int((today.get("direction", pd.Series(dtype=str)).astype(str).str.upper() == "UP").sum())
down = int((today.get("direction", pd.Series(dtype=str)).astype(str).str.upper() == "DOWN").sum())

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">2. LIVE STATE</div>', unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(
        f'<div class="metric"><div class="metric-label">TODAY EVENTS</div>'
        f'<div class="metric-value">{len(today)}</div>'
        f'<div class="metric-detail">first-breakout events</div></div>',
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f'<div class="metric"><div class="metric-label">UP</div>'
        f'<div class="metric-value">{up}</div>'
        f'<div class="metric-detail">directional breakout events</div></div>',
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f'<div class="metric"><div class="metric-label">DOWN</div>'
        f'<div class="metric-value">{down}</div>'
        f'<div class="metric-detail">directional breakout events</div></div>',
        unsafe_allow_html=True,
    )
with m4:
    st.markdown(
        f'<div class="metric"><div class="metric-label">LATEST SOURCE</div>'
        f'<div class="metric-value" style="font-size:15px;">{_fmt_ts(latest_ts)}</div>'
        f'<div class="metric-detail">{latest_source.name if latest_source else "—"}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Selected decision / evidence inspector
# ---------------------------------------------------------------------------

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">3. DECISION INSPECTOR</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="card-subtitle">Select a candidate to inspect the exact trigger and the '
    'evidence that was actually present. Missing values are never converted to zero.</div>',
    unsafe_allow_html=True,
)

if today.empty:
    st.info("No candidate is available for inspection.")
else:
    symbols = today["symbol"].astype(str).str.upper().tolist()
    selected_symbol = st.selectbox("Candidate", symbols, key="sdl_selected_candidate")
    matches = today[
        today["symbol"].astype(str).str.upper() == str(selected_symbol).upper()
    ]
    row = matches.sort_values(
        "observation_timestamp", ascending=False
    ).iloc[0]

    label, css = _decision(row)
    evidence, present, total = _evidence_state(row)

    st.markdown(
        f'<div class="decision {css}">'
        f'<div class="decision-main">{label}</div>'
        f'<div class="decision-meta">'
        f'Trigger: {_fmt_ts(row.get("observation_timestamp"))} · '
        f'Evidence: {present}/{total} · '
        f'Strategy: {row.get("strategy_version", "—")}'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    a, b, c, d = st.columns(4)
    with a:
        st.metric("Breakout", row.get("breakout_distance", "—"))
    with b:
        st.metric("Price Chg %", row.get("price_chg_pct", "—"))
    with c:
        st.metric("Fut OI Chg %", row.get("oi_chg_pct", "—"))
    with d:
        st.metric("PE−CE OI Chg", row.get("pe_minus_ce_oi_chg", "—"))

    st.dataframe(_evidence_table(row), width="stretch", hide_index=True)

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Historical evidence — secondary, not the landing surface
# ---------------------------------------------------------------------------

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">4. HISTORICAL EVIDENCE</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="card-subtitle">Historical first-breakout records remain available for validation '
    'and research, but are deliberately kept below the decision queue.</div>',
    unsafe_allow_html=True,
)

if events.empty:
    st.info("No historical events recorded.")
else:
    hist = events.copy()
    hist["observation_timestamp"] = pd.to_datetime(
        hist.get("observation_timestamp"), errors="coerce"
    )
    hist = hist.sort_values("observation_timestamp", ascending=False)

    display_cols = [
        "observation_timestamp", "trading_date", "symbol", "direction",
        "breakout_distance", "price_chg_pct", "oi_chg_pct",
        "ce_oi_chg_pct", "pe_oi_chg_pct", "pe_minus_ce_oi_chg",
        "iv_chg_pct", "pcr_chg_pct",
    ]
    display_cols = [c for c in display_cols if c in hist.columns]
    st.dataframe(hist[display_cols].head(250), width="stretch", hide_index=True)

st.markdown("</div>", unsafe_allow_html=True)


st.markdown(
    '<div class="muted" style="margin-top:10px;">'
    'SDL controlled boundary: source workbooks are read-only. '
    'No derivative-signal module is used by this dashboard. '
    'This UI does not create score, probability, or trade-signal logic.'
    '</div>',
    unsafe_allow_html=True,
)
