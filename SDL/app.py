
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from config import EVENT_CSV, STATE_JSON, REQUIRED_EVIDENCE_DIR
from pipeline import discover_historical_snapshots, process_latest_snapshot_for_today
from storage import load_events, load_state
from approaching_breakout import load_latest_approaching_breakouts


st.set_page_config(
    page_title="SDL — Straddle Breakout Decision Center",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background:#f7f8fc; }
    .block-container { max-width:1240px; padding-top:1rem; padding-bottom:1rem; }
    .sdl-header {
        background:linear-gradient(105deg,#0d1830 0%,#17264b 62%,#243a72 100%);
        color:white; padding:17px 20px; border-radius:11px; margin-bottom:11px;
    }
    .sdl-header-title { font-size:23px; font-weight:750; }
    .sdl-header-subtitle { font-size:12px; opacity:.88; margin-top:3px; }
    .section-card {
        background:white; border:1px solid #e7eaf2; border-radius:10px;
        padding:13px; margin:9px 0; box-shadow:0 4px 16px rgba(20,34,72,.055);
    }
    .section-title { color:#17233f; font-size:17px; font-weight:720; margin-bottom:7px; }
    .decision-hero {
        border-radius:10px; padding:12px 15px; margin:7px 0 10px 0;
        border:1px solid #dfe4ee; background:#fbfcff;
    }
    .decision-hero.good { background:#f1fbf6; border-color:#b9ead2; }
    .decision-hero.warn { background:#fff8e8; border-color:#f0d89a; }
    .decision-hero.bad { background:#fff4f4; border-color:#f1c4c4; }
    .decision-title { font-size:18px; font-weight:780; color:#17233f; }
    .decision-sub { font-size:11px; color:#667085; margin-top:3px; }
    .pill {
        display:inline-block; padding:4px 8px; border-radius:999px;
        font-size:10px; font-weight:750; margin-right:5px; border:1px solid rgba(0,0,0,.08);
    }
    .green { background:#b7e4c7; color:#12552d; }
    .lightgreen { background:#d9f0df; color:#1f6335; }
    .yellow { background:#fff1b8; color:#705800; }
    .orange { background:#ffd8a8; color:#7a3d00; }
    .grey { background:#e9edf3; color:#596273; }
    .muted { color:#747d90; font-size:11px; }
    .smallnote { color:#5f687a; font-size:11px; margin:2px 0 8px 0; }
    div.stButton > button[kind="primary"] {
        background:linear-gradient(90deg,#5844d8,#6c4ee6);
        border:0; border-radius:10px; font-weight:700; min-height:40px;
    }
    [data-testid="stDataFrame"] { border:1px solid #e6e9f1; border-radius:8px; overflow:hidden; }
    .footer {
        display:flex; justify-content:space-between; color:#747d90; font-size:11px;
        margin-top:18px; padding-top:10px; border-top:1px solid #e6e9f1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _events() -> pd.DataFrame:
    value = load_events(EVENT_CSV)
    return pd.DataFrame() if value is None else value.copy()


def _normalise_date(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _state() -> dict:
    try:
        return load_state(STATE_JSON) or {}
    except Exception:
        return {}


def _all_session_dates(events: pd.DataFrame, approaching: pd.DataFrame) -> list[str]:
    values = []
    for df in (events, approaching):
        if not df.empty and "trading_date" in df.columns:
            values.extend(
                df["trading_date"].map(_normalise_date).replace("", np.nan).dropna().tolist()
            )
    state = _state()
    state_dates = state.get("daily_opening_straddles", {})
    if isinstance(state_dates, dict):
        values.extend([_normalise_date(x) for x in state_dates.keys()])
    return sorted(set(x for x in values if x), reverse=True)


def _latest_session_date(events: pd.DataFrame, approaching: pd.DataFrame) -> str | None:
    dates = _all_session_dates(events, approaching)
    return dates[0] if dates else None


def _today_events(events: pd.DataFrame) -> pd.DataFrame:
    today = pd.Timestamp.now().date().isoformat()
    if events.empty or "trading_date" not in events.columns:
        return pd.DataFrame()
    return events.loc[events["trading_date"].map(_normalise_date) == today].copy()


def _discover_for_date(trading_date: str | None):
    if not trading_date:
        return []
    try:
        return [Path(p) for p in discover_historical_snapshots(trading_date) if Path(p).is_file()]
    except Exception:
        return []


def _latest_workbook_for_date(trading_date: str | None) -> Path | None:
    files = _discover_for_date(trading_date)
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _last_processed() -> str:
    state = _state()
    value = pd.to_datetime(state.get("last_observation_timestamp"), errors="coerce")
    if pd.notna(value):
        return value.strftime("%d %b %Y, %H:%M:%S")
    return "—"


def _safe_num(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _load_source_features(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    try:
        raw = pd.read_excel(path)
    except Exception:
        return pd.DataFrame()
    if "Symbol" not in raw.columns:
        return pd.DataFrame()
    raw["Symbol"] = raw["Symbol"].astype(str).str.strip().str.upper()
    wanted = [
        "Symbol", "Price Chg %", "OI Chg %", "IV Chg %",
        "PCR Chg %", "Tot CE OI Chg %", "Tot PE OI Chg %",
        "Tot PE-CE OI Chg",
    ]
    keep = [c for c in wanted if c in raw.columns]
    out = raw[keep].copy()
    for c in keep:
        if c != "Symbol":
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.drop_duplicates("Symbol", keep="last")


def _rank_abs(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() <= 1:
        return pd.Series(np.where(s.notna(), .5, np.nan), index=s.index, dtype=float)
    return s.abs().rank(method="average", pct=True).clip(0, 1)


def _evidence_score(df: pd.DataFrame) -> pd.Series:
    progress = _safe_num(df, "approach_progress_pct").clip(50, 100)
    progress_component = ((progress - 50) / 50).clip(0, 1) * 45
    direction = df.get("direction", pd.Series("", index=df.index)).astype(str).str.upper()
    price = _safe_num(df, "Price Chg %")
    aligned = ((direction == "UP") & (price > 0)) | ((direction == "DOWN") & (price < 0))
    price_component = np.where(price.isna(), 7.5, np.where(aligned, 15, 0))
    return pd.Series(
        progress_component.fillna(0) +
        pd.Series(price_component, index=df.index) +
        _rank_abs(df.get("OI Chg %", pd.Series(index=df.index))).fillna(.5) * 12 +
        _rank_abs(df.get("IV Chg %", pd.Series(index=df.index))).fillna(.5) * 8 +
        _rank_abs(df.get("PCR Chg %", pd.Series(index=df.index))).fillna(.5) * 8 +
        _rank_abs(df.get("Tot PE-CE OI Chg", pd.Series(index=df.index))).fillna(.5) * 12,
        index=df.index,
    ).round(1)


def _band(score) -> str:
    if pd.isna(score):
        return "NEUTRAL"
    if score >= 80:
        return "VERY STRONG"
    if score >= 65:
        return "STRONG"
    if score >= 50:
        return "MODERATE"
    return "CAUTION"


def _decision(progress, score, align) -> str:
    if pd.isna(progress):
        return "INSUFFICIENT DATA"
    if progress >= 100:
        return "CONFIRMED BREAKOUT"
    if score >= 80 and progress >= 75 and align == "✓":
        return "HIGH PRIORITY"
    if score >= 65 and progress >= 65:
        return "WATCH CLOSELY"
    if score >= 50:
        return "WATCH"
    return "WAIT"


def _build_current_decisions(approaching: pd.DataFrame, source: Path | None) -> pd.DataFrame:
    if approaching.empty or "symbol" not in approaching.columns:
        return pd.DataFrame()
    base = approaching.copy()
    base["symbol"] = base["symbol"].astype(str).str.strip().str.upper()
    if "observation_timestamp" in base.columns:
        ts = pd.to_datetime(base["observation_timestamp"], errors="coerce")
        base["_ts"] = ts
        base = base.sort_values(["symbol", "_ts"]).drop_duplicates("symbol", keep="last")
    features = _load_source_features(source)
    if not features.empty:
        base = base.merge(features, left_on="symbol", right_on="Symbol", how="left")
        base = base.drop(columns=["Symbol"], errors="ignore")
    base["score"] = _evidence_score(base)
    base["priority"] = base["score"].map(_band)
    progress = _safe_num(base, "approach_progress_pct")
    direction = base.get("direction", pd.Series("", index=base.index)).astype(str).str.upper()
    price = _safe_num(base, "Price Chg %")
    align = pd.Series(
        np.where(
            (direction == "UP") & (price > 0), "✓",
            np.where((direction == "DOWN") & (price < 0), "✓",
                     np.where(price.isna(), "—", "×"))
        ),
        index=base.index,
    )
    base["decision"] = [_decision(p, s, a) for p, s, a in zip(progress, base["score"], align)]
    base["alignment"] = align

    out = pd.DataFrame({
        "Rank": range(1, len(base) + 1),
        "Symbol": base["symbol"],
        "Direction": direction,
        "Progress": progress.round(1),
        "Remaining": (100 - progress).clip(lower=0).round(1),
        "Priority": base["priority"],
        "Decision": base["decision"],
        "Align": align,
        "Score": base["score"],
        "Time": base.get("observation_timestamp", ""),
    })
    return out.sort_values(["Score", "Progress", "Symbol"], ascending=[False, False, True]).reset_index(drop=True).assign(
        Rank=lambda x: range(1, len(x) + 1)
    )


def _style_priority(v):
    return {
        "VERY STRONG": "background-color:#b7e4c7;color:#12552d;font-weight:700;",
        "STRONG": "background-color:#d9f0df;color:#1f6335;font-weight:700;",
        "MODERATE": "background-color:#fff1b8;color:#705800;font-weight:700;",
        "CAUTION": "background-color:#ffd8a8;color:#7a3d00;font-weight:700;",
    }.get(v, "background-color:#e9edf3;color:#596273;font-weight:700;")


def _style_decision(v):
    if v in {"CONFIRMED BREAKOUT", "HIGH PRIORITY"}:
        return "background-color:#b7e4c7;color:#12552d;font-weight:700;"
    if v == "WATCH CLOSELY":
        return "background-color:#fff1b8;color:#705800;font-weight:700;"
    if v == "WATCH":
        return "background-color:#e9edf3;color:#3f4a5d;font-weight:700;"
    return "color:#6b7280;"


def _evidence_files(trading_date: str) -> list[Path]:
    root = Path(REQUIRED_EVIDENCE_DIR)
    candidates = [root / f"{trading_date}.csv", root / trading_date / "evidence.csv"]
    return [p for p in candidates if p.exists()]


def _load_historical_evidence(trading_date: str) -> pd.DataFrame:
    files = _evidence_files(trading_date)
    if not files:
        return pd.DataFrame()
    frames = []
    for path in files:
        try:
            frames.append(pd.read_csv(path))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "observation_timestamp" in df.columns:
        df["observation_timestamp"] = pd.to_datetime(df["observation_timestamp"], errors="coerce")
    if "Symbol" in df.columns:
        df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    return df


def _replay_progress(df: pd.DataFrame) -> pd.Series:
    current = _safe_num(df, "current_price")
    opening = _safe_num(df, "Open")
    straddle = _safe_num(df, "opening_straddle_premium")
    valid = straddle.gt(0) & current.notna() & opening.notna()
    progress = (current - opening).abs() / straddle.replace(0, np.nan) * 100
    return progress.where(valid)


def _historical_replay(evidence: pd.DataFrame, events: pd.DataFrame, trading_date: str) -> tuple[pd.DataFrame, dict]:
    if evidence.empty or "Symbol" not in evidence.columns or "observation_timestamp" not in evidence.columns:
        return pd.DataFrame(), {}

    df = evidence.copy()
    df["progress"] = _replay_progress(df)

    # Direction is factual from the first direction implied by the frozen opening levels.
    upper = _safe_num(df, "upper_straddle_breakout_level")
    lower = _safe_num(df, "lower_straddle_breakout_level")
    price = _safe_num(df, "current_price")
    df["direction"] = np.where(
        price.gt(upper), "UP",
        np.where(price.lt(lower), "DOWN", "")
    )

    # The 50% reach point is the first observed point >= 50%.
    rows = []
    for symbol, group in df.sort_values("observation_timestamp").groupby("Symbol", sort=True):
        group = group.sort_values("observation_timestamp").copy()
        first = group.iloc[0]
        reaches = group.loc[group["progress"].ge(50)]
        first50 = reaches.iloc[0] if not reaches.empty else None

        event_match = events.loc[
            (events["trading_date"].map(_normalise_date) == trading_date)
            & (events["symbol"].astype(str).str.upper() == symbol)
        ] if not events.empty and {"trading_date", "symbol"}.issubset(events.columns) else pd.DataFrame()

        first100_time = None
        if not event_match.empty and "observation_timestamp" in event_match.columns:
            first100_time = pd.to_datetime(event_match["observation_timestamp"], errors="coerce").min()
        else:
            crossings = group.loc[
                (group["upper_straddle_breakout_level"].notna() & group["current_price"].ge(group["upper_straddle_breakout_level"]))
                | (group["lower_straddle_breakout_level"].notna() & group["current_price"].le(group["lower_straddle_breakout_level"]))
            ]
            if not crossings.empty:
                first100_time = crossings["observation_timestamp"].min()

        if first50 is None:
            status = "DID NOT REACH 50%"
            decision = "NO ACTION"
            first50_time = None
        elif pd.notna(first100_time) and pd.notna(first50["observation_timestamp"]) and first100_time > first50["observation_timestamp"]:
            status = "50% → 100% CONFIRMED"
            decision = "FOLLOW-THROUGH"
            first50_time = first50["observation_timestamp"]
        elif pd.notna(first100_time):
            status = "100% CONFIRMED"
            decision = "BREAKOUT"
            first50_time = first50["observation_timestamp"]
        else:
            status = "50% REACHED — NO 100% YET"
            decision = "NO FOLLOW-THROUGH OBSERVED"
            first50_time = first50["observation_timestamp"]

        progress_at_50 = float(first50["progress"]) if first50 is not None and pd.notna(first50["progress"]) else np.nan
        last = group.iloc[-1]
        rows.append({
            "Symbol": symbol,
            "Direction": "UP" if first50 is None and float(last.get("progress", 0) or 0) >= 50 and last.get("direction") == "UP" else (
                first50.get("direction") if first50 is not None and first50.get("direction") else (
                    "UP" if float(last.get("progress", 0) or 0) >= 50 and price.loc[last.name] > _safe_num(group, "Open").loc[last.name] else "—"
                )
            ),
            "50% Time": first50_time,
            "50% Progress": round(progress_at_50, 1) if pd.notna(progress_at_50) else None,
            "100% Time": first100_time,
            "Session End Progress": round(float(last["progress"]), 1) if pd.notna(last["progress"]) else None,
            "Status": status,
            "Decision": decision,
        })

    result = pd.DataFrame(rows)
    if result.empty:
        return result, {}

    result["_50"] = pd.to_datetime(result["50% Time"], errors="coerce")
    result["_100"] = pd.to_datetime(result["100% Time"], errors="coerce")
    result["Time to 100%"] = (
        result["_100"] - result["_50"]
    ).map(lambda x: f"{x.total_seconds()/60:.1f} min" if pd.notna(x) else "—")

    summary = {
        "first_snapshot": df["observation_timestamp"].min(),
        "last_snapshot": df["observation_timestamp"].max(),
        "snapshots": int(df["observation_timestamp"].nunique()),
        "symbols": int(df["Symbol"].nunique()),
        "reached_50": int(result["50% Time"].notna().sum()),
        "confirmed_100": int(result["100% Time"].notna().sum()),
        "follow_through": int((result["Decision"] == "FOLLOW-THROUGH").sum()),
    }

    return result.sort_values(
        ["Decision", "50% Progress", "Symbol"],
        key=lambda s: s if s.name != "50% Progress" else -pd.to_numeric(s, errors="coerce"),
        na_position="last",
    ).drop(columns=["_50", "_100"], errors="ignore").reset_index(drop=True), summary


def _historical_stock_detail(evidence: pd.DataFrame, symbol: str) -> pd.DataFrame:
    group = evidence.loc[evidence["Symbol"] == symbol].copy().sort_values("observation_timestamp")
    if group.empty:
        return pd.DataFrame()
    group["Progress"] = _replay_progress(group).round(1)
    out = pd.DataFrame({
        "Time": group["observation_timestamp"].dt.strftime("%H:%M:%S"),
        "Progress": group["Progress"],
        "Price": _safe_num(group, "current_price").round(2),
        "50%": np.where(group["Progress"].ge(50), "✓", ""),
        "100%": np.where(
            (_safe_num(group, "upper_straddle_breakout_level").notna() & _safe_num(group, "current_price").ge(_safe_num(group, "upper_straddle_breakout_level")))
            | (_safe_num(group, "lower_straddle_breakout_level").notna() & _safe_num(group, "current_price").le(_safe_num(group, "lower_straddle_breakout_level"))),
            "✓", ""
        ),
    })
    return out


def _historical_decision_text(row) -> str:
    status = str(row.get("Status", ""))
    if status == "50% → 100% CONFIRMED":
        return "FOLLOW-THROUGH CONFIRMED"
    if status == "100% CONFIRMED":
        return "BREAKOUT CONFIRMED"
    if status == "50% REACHED — NO 100% YET":
        return "REACHED 50% — NO BREAKOUT CONFIRMED"
    return "DID NOT REACH 50% — NO SIGNAL"


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="sdl-header">
        <div class="sdl-header-title">SDL — Straddle Breakout Decision Center</div>
        <div class="sdl-header-subtitle">
            Decision first • factual evidence underneath • frozen Phase-1 breakout rule preserved
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

action_col, info_col = st.columns([1, 2.3])
with action_col:
    process_clicked = st.button("▶ Process Latest Snapshot", type="primary", width="stretch")
with info_col:
    st.markdown(
        '<div class="muted" style="padding-top:11px;">'
        "Process today's newest Daywise workbook. Empty early-open files are allowed; "
        "the first valid snapshot freezes the daily base."
        "</div>",
        unsafe_allow_html=True,
    )

if process_clicked:
    try:
        latest_processed, new_events, _, note = process_latest_snapshot_for_today()
        if latest_processed is None:
            st.warning(note)
        else:
            st.success(f"Processed: {Path(latest_processed).name}")
            st.caption(note)
            st.rerun()
    except Exception as exc:
        st.error(f"Processing failed: {exc}")

# ---------------------------------------------------------------------------
# Current/latest session decision center
# ---------------------------------------------------------------------------

events = _events()
approaching_path = Path(EVENT_CSV).parent / "approaching_breakouts.csv"
approaching = load_latest_approaching_breakouts(approaching_path)
if approaching is None:
    approaching = pd.DataFrame()

latest_session = _latest_session_date(events, approaching)
current_source = _latest_workbook_for_date(latest_session)
today_events = _today_events(events)

if latest_session and not approaching.empty and "trading_date" in approaching.columns:
    active_approaching = approaching.loc[
        approaching["trading_date"].map(_normalise_date) == latest_session
    ].copy()
else:
    active_approaching = pd.DataFrame()

decision_table = _build_current_decisions(active_approaching, current_source)

confirmed_events = events.loc[
    events["trading_date"].map(_normalise_date) == latest_session
].copy() if latest_session and not events.empty and "trading_date" in events.columns else pd.DataFrame()

strong = int((decision_table["Priority"] == "VERY STRONG").sum()) if not decision_table.empty else 0
strong2 = int((decision_table["Priority"] == "STRONG").sum()) if not decision_table.empty else 0
high = int((decision_table["Decision"] == "HIGH PRIORITY").sum()) if not decision_table.empty else 0

st.markdown('<div class="section-card"><div class="section-title">◆ Current Decision</div>', unsafe_allow_html=True)

if latest_session:
    st.markdown(
        f'<div class="decision-hero good">'
        f'<div class="decision-title">Latest Trading Session: {pd.Timestamp(latest_session).strftime("%d %b %Y")}</div>'
        f'<div class="decision-sub">This session is shown until a newer trading session is actually processed. '
        f'It is not relabelled as today after midnight.</div></div>',
        unsafe_allow_html=True,
    )
else:
    st.info("No processed trading session is available yet.")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Confirmed 100%", len(confirmed_events))
with c2:
    st.metric("50% Candidates", len(decision_table))
with c3:
    st.metric("High Priority", high)
with c4:
    st.metric("Last Processed", _last_processed())

if not confirmed_events.empty:
    st.markdown("**CONFIRMED ACTIONS**")
    for _, row in confirmed_events.sort_values("observation_timestamp").iterrows():
        direction = str(row.get("direction", "")).upper()
        symbol = str(row.get("symbol", ""))
        ts = pd.to_datetime(row.get("observation_timestamp"), errors="coerce")
        ts_text = ts.strftime("%H:%M:%S") if pd.notna(ts) else "—"
        st.markdown(
            f'<div class="decision-hero good"><div class="decision-title">'
            f'{symbol} — {direction} BREAKOUT CONFIRMED</div>'
            f'<div class="decision-sub">Confirmed at {ts_text}. '
            f'This is the factual Phase-1 signal.</div></div>',
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        '<div class="decision-hero warn"><div class="decision-title">NO CONFIRMED 100% BREAKOUT</div>'
        '<div class="decision-sub">No Phase-1 breakout/breakdown has been recorded for the latest session.</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("**50%–99% ACTION QUEUE**")
if decision_table.empty:
    st.info("No 50% candidates are available for the latest processed session.")
else:
    labels = [
        f"ALL ({len(decision_table)})",
        f"VERY STRONG ({strong})",
        f"STRONG ({strong2})",
        f"MODERATE ({int((decision_table['Priority']=='MODERATE').sum())})",
        f"CAUTION ({int((decision_table['Priority']=='CAUTION').sum())})",
    ]
    tabs = st.tabs(labels)
    groups = [
        decision_table,
        decision_table[decision_table["Priority"] == "VERY STRONG"],
        decision_table[decision_table["Priority"] == "STRONG"],
        decision_table[decision_table["Priority"] == "MODERATE"],
        decision_table[decision_table["Priority"] == "CAUTION"],
    ]
    for tab, group in zip(tabs, groups):
        with tab:
            if group.empty:
                st.info("No candidate in this decision band.")
            else:
                view = group[
                    ["Rank", "Symbol", "Direction", "Progress", "Remaining",
                     "Priority", "Decision", "Align", "Score", "Time"]
                ].copy()
                styled = (
                    view.style
                    .map(_style_priority, subset=["Priority"])
                    .map(_style_decision, subset=["Decision"])
                )
                st.dataframe(styled, width="stretch", hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Historical replay — decision view, not raw-data view
# ---------------------------------------------------------------------------

st.markdown('<div class="section-card"><div class="section-title">▣ Historical Replay — Decision Evidence</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="smallnote">'
    "Select a completed trading session. The dashboard reconstructs the sequence from the persisted "
    "snapshot evidence: first valid observation → 50% reach → later 100% crossing. "
    "The result is factual replay, not a probability model."
    "</div>",
    unsafe_allow_html=True,
)

history_dates = _all_session_dates(events, approaching)
if not history_dates:
    st.info("No historical sessions are available.")
else:
    default_index = 0
    selected_date = st.selectbox(
        "Trading Session",
        history_dates,
        index=default_index,
        format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y"),
        key="replay_session_date",
    )

    evidence = _load_historical_evidence(selected_date)
    hist_events = events.loc[
        events["trading_date"].map(_normalise_date) == selected_date
    ].copy() if not events.empty and "trading_date" in events.columns else pd.DataFrame()

    replay, summary = _historical_replay(evidence, hist_events, selected_date)

    if replay.empty:
        st.warning(
            "Replay evidence is not available for this session. "
            "The dashboard will not manufacture a historical conclusion from the 50% summary alone."
        )
    else:
        s1, s2, s3, s4, s5 = st.columns(5)
        with s1:
            st.metric("Snapshots", summary["snapshots"])
        with s2:
            st.metric("Reached 50%", summary["reached_50"])
        with s3:
            st.metric("Confirmed 100%", summary["confirmed_100"])
        with s4:
            st.metric("Follow-through", summary["follow_through"])
        with s5:
            first_text = pd.Timestamp(summary["first_snapshot"]).strftime("%H:%M:%S")
            st.metric("First Valid", first_text)

        st.markdown(
            f'<div class="decision-hero">'
            f'<div class="decision-title">Session Decision Summary</div>'
            f'<div class="decision-sub">'
            f'{summary["reached_50"]} stocks reached the 50% evidence threshold; '
            f'{summary["confirmed_100"]} later crossed the frozen 100% breakout level; '
            f'{summary["follow_through"]} have a confirmed 50% → 100% sequence.'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        replay_view = replay[
            ["Symbol", "Direction", "50% Time", "50% Progress",
             "100% Time", "Time to 100%", "Session End Progress",
             "Status", "Decision"]
        ].copy()

        def _status_style(v):
            if v == "50% → 100% CONFIRMED":
                return "background-color:#b7e4c7;color:#12552d;font-weight:700;"
            if v == "100% CONFIRMED":
                return "background-color:#d9f0df;color:#1f6335;font-weight:700;"
            if v == "50% REACHED — NO 100% YET":
                return "background-color:#fff1b8;color:#705800;font-weight:700;"
            return "color:#6b7280;"

        st.dataframe(
            replay_view.style.map(_status_style, subset=["Status"]),
            width="stretch",
            hide_index=True,
        )

        eligible = replay.loc[replay["50% Time"].notna(), "Symbol"].tolist()
        if eligible:
            selected_symbol = st.selectbox(
                "Inspect one replay decision",
                eligible,
                key="replay_symbol",
            )
            selected_row = replay.loc[replay["Symbol"] == selected_symbol].iloc[0]
            text = _historical_decision_text(selected_row)
            if text == "FOLLOW-THROUGH CONFIRMED":
                cls = "good"
            elif "NO BREAKOUT" in text:
                cls = "warn"
            else:
                cls = "good"
            st.markdown(
                f'<div class="decision-hero {cls}">'
                f'<div class="decision-title">{selected_symbol}: {text}</div>'
                f'<div class="decision-sub">'
                f'50% reached at {pd.Timestamp(selected_row["50% Time"]).strftime("%H:%M:%S")}. '
                f'100% crossing: {pd.Timestamp(selected_row["100% Time"]).strftime("%H:%M:%S") if pd.notna(selected_row["100% Time"]) else "not observed"}. '
                f'This is a historical fact, not a forecast.'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            timeline = _historical_stock_detail(evidence, selected_symbol)
            if not timeline.empty:
                st.markdown("**Replay timeline — decision markers only**")
                st.dataframe(timeline, width="stretch", hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="footer"><span>SDL Phase-1 • frozen production logic preserved</span>'
    '<span>Dashboard purpose: decision, not data display</span></div>',
    unsafe_allow_html=True,
)
