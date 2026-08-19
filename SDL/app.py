from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
import re

import numpy as np
import pandas as pd
import streamlit as st

from config import EVENT_CSV, STATE_JSON, REQUIRED_EVIDENCE_DIR
from pipeline import discover_historical_snapshots, process_snapshot
from storage import load_events, load_state
from prediction_engine import (
    EARLY_THRESHOLD,
    TRADEABLE_THRESHOLD,
    build_current_predictions,
    coalesce_source_sheets,
    factor_labels,
)


st.set_page_config(
    page_title="SDL — Straddle Breakout Decision Center",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp{background:#f7f8fc}
    .block-container{max-width:1240px;padding-top:1rem;padding-bottom:1rem}
    .sdl-header{background:linear-gradient(105deg,#0d1830 0%,#17264b 62%,#243a72 100%);
      color:white;padding:17px 20px;border-radius:11px;margin-bottom:11px}
    .sdl-header-title{font-size:23px;font-weight:750}
    .sdl-header-subtitle{font-size:12px;opacity:.88;margin-top:3px}
    .section-card{background:white;border:1px solid #e7eaf2;border-radius:10px;padding:13px;
      margin:9px 0;box-shadow:0 4px 16px rgba(20,34,72,.055)}
    .section-title{color:#17233f;font-size:17px;font-weight:720;margin-bottom:7px}
    .decision-hero{border-radius:10px;padding:12px 15px;margin:7px 0 10px;
      border:1px solid #dfe4ee;background:#fbfcff}
    .decision-hero.good{background:#f1fbf6;border-color:#b9ead2}
    .decision-hero.warn{background:#fff8e8;border-color:#f0d89a}
    .decision-hero.bad{background:#fff4f4;border-color:#f1c4c4}
    .decision-title{font-size:18px;font-weight:780;color:#17233f}
    .decision-sub{font-size:11px;color:#667085;margin-top:3px}
    .factor{display:inline-block;padding:4px 8px;border-radius:999px;font-size:10px;
      font-weight:700;margin:2px 4px 2px 0;border:1px solid rgba(0,0,0,.08)}
    .factor.good{background:#d9f0df;color:#1f6335}
    .factor.bad{background:#ffd8a8;color:#7a3d00}
    .factor.neutral{background:#e9edf3;color:#596273}
    .muted{color:#747d90;font-size:11px}
    .smallnote{color:#5f687a;font-size:11px;margin:2px 0 8px}
    .footer{display:flex;justify-content:space-between;color:#747d90;font-size:11px;
      margin-top:18px;padding-top:10px;border-top:1px solid #e6e9f1}
    div.stButton>button[kind="primary"]{background:linear-gradient(90deg,#5844d8,#6c4ee6);
      border:0;border-radius:10px;font-weight:700;min-height:40px}
    </style>
    """,
    unsafe_allow_html=True,
)


def _events() -> pd.DataFrame:
    value = load_events(EVENT_CSV)
    return pd.DataFrame() if value is None else value.copy()


def _state() -> dict:
    try:
        return load_state(STATE_JSON) or {}
    except Exception:
        return {}


def _date(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _files(trading_date: str | None) -> list[Path]:
    if not trading_date:
        return []
    try:
        return sorted(
            [Path(p) for p in discover_historical_snapshots(trading_date) if Path(p).is_file()],
            key=lambda p: p.stat().st_mtime,
        )
    except Exception:
        return []


def _valid_base_file(path: Path) -> bool:
    try:
        df = pd.read_excel(path)
    except Exception:
        return False
    required = {"Symbol", "Open", "ATM Straddle %"}
    if not required.issubset(df.columns):
        return False
    op = pd.to_numeric(df["Open"], errors="coerce")
    atm = pd.to_numeric(df["ATM Straddle %"], errors="coerce")
    return bool((op.gt(0) & atm.notna()).any())


def _first_valid_file(trading_date: str | None) -> Path | None:
    for path in _files(trading_date):
        if _valid_base_file(path):
            return path
    return None


def _process_latest_first_valid() -> tuple[Path | None, object, object, str]:
    trading_date = datetime.now().date().isoformat()
    files = _files(trading_date)
    if not files:
        return None, None, None, "No Daywise snapshot found for today."

    state = _state()
    base = state.get("daily_opening_straddles", {}).get(trading_date)
    first_valid = _first_valid_file(trading_date)

    if not base:
        if first_valid is None:
            return None, None, None, "No valid opening snapshot found; frozen base remains unchanged."
        observed = datetime.fromtimestamp(first_valid.stat().st_mtime)
        process_snapshot(first_valid, observed)
        state = _state()
        base = state.get("daily_opening_straddles", {}).get(trading_date)
        if not base:
            return None, None, None, "Valid opening snapshot found, but frozen daily base was not persisted."

    latest = files[-1]
    if first_valid is not None and latest == first_valid:
        return latest, None, None, "First valid snapshot processed and frozen base established; no later snapshot is available."

    observed = datetime.fromtimestamp(latest.stat().st_mtime)
    events, df, processed_at = process_snapshot(latest, observed)
    return latest, events, df, "Frozen first-valid base preserved; latest snapshot processed against that base."


def _latest_session(events: pd.DataFrame) -> str | None:
    dates = []
    if not events.empty and "trading_date" in events.columns:
        dates.extend(events["trading_date"].map(_date).tolist())
    bases = _state().get("daily_opening_straddles", {})
    if isinstance(bases, dict):
        dates.extend(_date(x) for x in bases.keys())
    dates = sorted({x for x in dates if x}, reverse=True)
    return dates[0] if dates else None


def _latest_source(trading_date: str | None) -> Path | None:
    files = _files(trading_date)
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def _timestamp_from_path(path: Path) -> pd.Timestamp:
    match = re.search(r"_(\d{2})(\d{2})(\d{2})$", path.stem)
    if match:
        return pd.Timestamp.combine(
            pd.Timestamp(path.parent.name).date() if re.match(r"^\d{4}-\d{2}-\d{2}$", path.parent.name) else pd.Timestamp.fromtimestamp(path.stat().st_mtime).date(),
            time(int(match.group(1)), int(match.group(2)), int(match.group(3))),
        )
    return pd.Timestamp.fromtimestamp(path.stat().st_mtime)


def _orb_map(trading_date: str | None, latest_source: Path | None) -> dict[str, str]:
    """Return 15-minute ORB status. Partial ranges are displayed but never scored."""
    if not trading_date:
        return {}

    # Prefer explicit ORB fields if the source contract supplies them.
    latest = coalesce_source_sheets(latest_source)
    if not latest.empty:
        lower = {str(c).strip().lower(): c for c in latest.columns}
        hi = next((c for k, c in lower.items() if ("orb" in k or "opening range" in k) and "high" in k), None)
        lo = next((c for k, c in lower.items() if ("orb" in k or "opening range" in k) and "low" in k), None)
        px = next((c for k, c in lower.items() if k in {"close", "current price", "cmp"}), None)
        if hi and lo and px:
            result = {}
            for _, row in latest.iterrows():
                h = pd.to_numeric(row.get(hi), errors="coerce")
                l = pd.to_numeric(row.get(lo), errors="coerce")
                p = pd.to_numeric(row.get(px), errors="coerce")
                if pd.notna(h) and pd.notna(l) and pd.notna(p):
                    result[str(row["Symbol"]).upper()] = "ORB ↑" if p > h else "ORB ↓" if p < l else "ORB —"
            if result:
                return result

    # Build the observed opening range from snapshots in the 09:15–09:30 window.
    # If the first valid snapshot starts after 09:15, mark the result PARTIAL and
    # do not award it as a scoring factor.
    rows = []
    for path in _files(trading_date):
        ts = _timestamp_from_path(path)
        if time(9, 15) <= ts.time() <= time(9, 30):
            try:
                raw = coalesce_source_sheets(path)
            except Exception:
                raw = pd.DataFrame()
            if raw.empty or "Symbol" not in raw.columns:
                continue
            raw["_ts"] = ts
            rows.append(raw)

    if not rows:
        return {}

    opening = pd.concat(rows, ignore_index=True, sort=False)
    if "High" not in opening.columns or "Low" not in opening.columns:
        return {}

    opening["High"] = pd.to_numeric(opening["High"], errors="coerce")
    opening["Low"] = pd.to_numeric(opening["Low"], errors="coerce")
    opening["Symbol"] = opening["Symbol"].astype(str).str.strip().str.upper()

    earliest = opening["_ts"].min()
    partial = earliest.time() > time(9, 15)

    # Latest available price is taken from the actual latest source.
    latest_df = coalesce_source_sheets(latest_source)
    if latest_df.empty or "Close" not in latest_df.columns:
        return {}
    latest_df["Close"] = pd.to_numeric(latest_df["Close"], errors="coerce")
    latest_df["Symbol"] = latest_df["Symbol"].astype(str).str.strip().str.upper()

    result = {}
    ranges = opening.groupby("Symbol").agg(orb_high=("High", "max"), orb_low=("Low", "min"))
    prices = latest_df.set_index("Symbol")["Close"]

    for symbol, bounds in ranges.iterrows():
        price = prices.get(symbol)
        if pd.isna(price):
            continue
        if price > bounds["orb_high"]:
            status = "ORB ↑"
        elif price < bounds["orb_low"]:
            status = "ORB ↓"
        else:
            status = "ORB —"
        if partial:
            status = "ORB PARTIAL"
        result[symbol] = status
    return result


def _factor_html(result: dict) -> str:
    parts = []
    for label in factor_labels(result):
        if label.startswith("✓"):
            cls = "good"
        elif label.startswith("✕"):
            cls = "bad"
        else:
            cls = "neutral"
        parts.append(f'<span class="factor {cls}">{label}</span>')
    return "".join(parts)


def _milestone(progress: float) -> str:
    if progress >= 100:
        return "100% CONFIRMED"
    if progress >= 70:
        return "70% REACHED"
    if progress >= 50:
        return "50% REACHED"
    return "22%+ EARLY ZONE"


def _confirmed(events: pd.DataFrame, trading_date: str | None) -> pd.DataFrame:
    if not trading_date or events.empty or "trading_date" not in events.columns:
        return pd.DataFrame()
    return events.loc[events["trading_date"].map(_date) == trading_date].copy()


def _historical_early_replay(evidence: pd.DataFrame, events: pd.DataFrame, trading_date: str) -> pd.DataFrame:
    if evidence.empty or "Symbol" not in evidence.columns:
        return pd.DataFrame()

    df = evidence.copy()
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    ts_col = "observation_timestamp"
    if ts_col not in df.columns:
        return pd.DataFrame()
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
    df["current_price"] = pd.to_numeric(df.get("current_price"), errors="coerce")
    df["daily_open_reference"] = pd.to_numeric(df.get("daily_open_reference"), errors="coerce")
    df["opening_straddle_premium"] = pd.to_numeric(df.get("opening_straddle_premium"), errors="coerce")
    df["progress"] = (df["current_price"] - df["daily_open_reference"]).abs() / df["opening_straddle_premium"] * 100
    df = df.sort_values(ts_col)

    rows = []
    for symbol, group in df.groupby("Symbol", sort=True):
        early = group.loc[group["progress"].gt(EARLY_THRESHOLD)]
        if early.empty:
            continue
        first = early.iloc[0]
        event_match = events.loc[
            (events["trading_date"].map(_date) == trading_date)
            & (events["symbol"].astype(str).str.upper() == symbol)
        ] if not events.empty and {"trading_date", "symbol"}.issubset(events.columns) else pd.DataFrame()
        confirmed = not event_match.empty
        confirmed_time = pd.to_datetime(event_match["observation_timestamp"], errors="coerce").min() if confirmed else pd.NaT
        rows.append({
            "Symbol": symbol,
            "Early Time": first[ts_col],
            "Direction": "UP" if first["current_price"] > first["daily_open_reference"] else "DOWN",
            "Early Progress": round(float(first["progress"]), 1),
            "100% Confirmed": "YES" if confirmed else "NO",
            "Confirmation Time": confirmed_time,
        })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["100% Confirmed", "Early Progress"], ascending=[False, False]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Header / processing
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="sdl-header"><div class="sdl-header-title">SDL — Straddle Breakout Decision Center</div>'
    '<div class="sdl-header-subtitle">Prediction first • actionable evidence only • frozen Phase-1 breakout rule preserved</div></div>',
    unsafe_allow_html=True,
)

action_col, info_col = st.columns([1, 2.3])
with action_col:
    process_clicked = st.button("▶ Process Latest Snapshot", type="primary", width="stretch")
with info_col:
    st.markdown(
        '<div class="muted" style="padding-top:11px;">'
        "Processes today's newest Daywise workbook. The first valid snapshot freezes the opening base; "
        "later snapshots cannot overwrite it."
        "</div>",
        unsafe_allow_html=True,
    )

if process_clicked:
    try:
        latest, _, _, note = _process_latest_first_valid()
        if latest is None:
            st.warning(note)
        else:
            st.success(f"Processed: {latest.name}")
            st.caption(note)
            st.rerun()
    except Exception as exc:
        st.error(f"Processing failed: {exc}")


# ---------------------------------------------------------------------------
# Current decision center
# ---------------------------------------------------------------------------

events = _events()
latest_session = _latest_session(events)
source_path = _latest_source(latest_session)
source_df = coalesce_source_sheets(source_path)
state = _state()
frozen_base = state.get("daily_opening_straddles", {}).get(latest_session, {}) if latest_session else {}
orb = _orb_map(latest_session, source_path)
predictions = build_current_predictions(source_df, frozen_base, orb)
confirmed = _confirmed(events, latest_session)

st.markdown('<div class="section-card"><div class="section-title">◆ Current Decision</div>', unsafe_allow_html=True)

if latest_session:
    first_valid = _first_valid_file(latest_session)
    base_time = pd.Timestamp.fromtimestamp(first_valid.stat().st_mtime).strftime("%H:%M:%S") if first_valid else "—"
    st.markdown(
        f'<div class="decision-hero good"><div class="decision-title">'
        f'{pd.Timestamp(latest_session).strftime("%d %b %Y")} • BASE FROZEN • {base_time}</div>'
        f'<div class="decision-sub">The first valid opening snapshot is shown once. It is the immutable reference for today.</div></div>',
        unsafe_allow_html=True,
    )
else:
    st.info("No processed trading session is available yet.")

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("TRADEABLE EARLY", int(predictions["tradeable"].sum()) if not predictions.empty else 0)
with m2:
    st.metric("CONFIRMED 100%", len(confirmed))
with m3:
    st.metric("ENTRY GATE", f">{EARLY_THRESHOLD:.0f}%")
with m4:
    last = pd.to_datetime(state.get("last_observation_timestamp"), errors="coerce")
    st.metric("LAST PROCESSED", last.strftime("%d %b %Y, %H:%M:%S") if pd.notna(last) else "—")

tradeable = predictions.loc[predictions["tradeable"]].copy() if not predictions.empty else pd.DataFrame()

if not tradeable.empty:
    st.markdown("**EARLY TRADEABLE SETUPS**")
    for _, row in tradeable.head(10).iterrows():
        milestone = _milestone(float(row["progress"]))
        st.markdown(
            f'<div class="decision-hero good"><div class="decision-title">'
            f'{row["symbol"]} — {row["direction"]} • TRADEABLE</div>'
            f'<div class="decision-sub">Progress {row["progress"]:.1f}% • Evidence strength {row["strength"]:.0f}/100 • {milestone}</div>'
            f'{_factor_html(row.to_dict())}</div>',
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        '<div class="decision-hero warn"><div class="decision-title">NO EARLY TRADEABLE SETUP</div>'
        f'<div class="decision-sub">Only stocks above {EARLY_THRESHOLD:.0f}% are evaluated. '
        "A price move alone is never sufficient; the secondary evidence gate must also pass. "
        "Lower-strength stocks are intentionally suppressed.</div></div>",
        unsafe_allow_html=True,
    )

if not confirmed.empty:
    st.markdown("**CONFIRMED PHASE-1 BREAKOUTS**")
    for _, row in confirmed.sort_values("observation_timestamp").iterrows():
        ts = pd.to_datetime(row.get("observation_timestamp"), errors="coerce")
        ts_text = ts.strftime("%H:%M:%S") if pd.notna(ts) else "—"
        st.markdown(
            f'<div class="decision-hero good"><div class="decision-title">'
            f'{str(row.get("symbol","")).upper()} — {str(row.get("direction","")).upper()} BREAKOUT CONFIRMED</div>'
            f'<div class="decision-sub">Confirmed at {ts_text}. Frozen Phase-1 factual signal.</div></div>',
            unsafe_allow_html=True,
        )

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Historical replay — early prediction + factual confirmation
# ---------------------------------------------------------------------------

st.markdown('<div class="section-card"><div class="section-title">▣ Historical Replay — Decision Evidence</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="smallnote">Replay shows the first >22% decision point and the later factual 100% result. '
    'It does not turn the historical result into a probability or hindsight forecast.</div>',
    unsafe_allow_html=True,
)

history_dates = []
if not events.empty and "trading_date" in events.columns:
    history_dates.extend(events["trading_date"].map(_date).tolist())
history_dates.extend(_date(x) for x in _state().get("daily_opening_straddles", {}).keys())
history_dates = sorted({x for x in history_dates if x}, reverse=True)

if not history_dates:
    st.info("No historical sessions are available.")
else:
    selected_date = st.selectbox(
        "Trading Session",
        history_dates,
        format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y"),
        key="replay_session_date",
    )
    evidence_files = [
        Path(REQUIRED_EVIDENCE_DIR) / f"{selected_date}.csv",
        Path(REQUIRED_EVIDENCE_DIR) / selected_date / "evidence.csv",
    ]
    frames = []
    for path in evidence_files:
        if path.exists():
            try:
                frames.append(pd.read_csv(path))
            except Exception:
                pass
    evidence = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    hist_events = _confirmed(events, selected_date)
    replay = _historical_early_replay(evidence, hist_events, selected_date)

    if replay.empty:
        st.info("No persisted >22% early-entry evidence is available for this session.")
    else:
        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("EARLY ZONE STOCKS", len(replay))
        with r2:
            st.metric("LATER 100% CONFIRMED", int((replay["100% Confirmed"] == "YES").sum()))
        with r3:
            st.metric("FIRST VALID", pd.to_datetime(evidence["observation_timestamp"], errors="coerce").min().strftime("%H:%M:%S"))

        st.dataframe(replay, width="stretch", hide_index=True)

st.markdown(
    '<div class="footer"><span>SDL • predictive decision layer • Phase-1 breakout detection preserved</span>'
    '<span>Evidence strength is a heuristic ranking, not a calibrated probability</span></div>',
    unsafe_allow_html=True,
)
