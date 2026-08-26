from __future__ import annotations

from pathlib import Path
import time

import pandas as pd
import streamlit as st

from config import EVENT_CSV, STATE_JSON
from pipeline import (
    discover_historical_snapshots,
    process_snapshot,
    replay_trading_date,
)
from prediction_engine import build_current_predictions
from source_loader import parse_observation_timestamp, load_primary_snapshot
from storage import load_events, load_state


st.set_page_config(
    page_title="SDL — Straddle Breakout Decision Center",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
<style>
.stApp{background:#f6f8fc}
.block-container{max-width:1460px;padding-top:1rem;padding-bottom:1.2rem}
.sdl-header{background:linear-gradient(105deg,#0b1730,#1a2b55 65%,#293f7a);color:#fff;padding:18px 22px;border-radius:12px;margin-bottom:12px}
.sdl-title{font-size:25px;font-weight:780;margin:0}
.sdl-subtitle{font-size:12px;opacity:.9;margin-top:4px}
.card{background:#fff;border:1px solid #e3e7ef;border-radius:11px;padding:13px 15px;margin:9px 0;box-shadow:0 3px 12px rgba(20,34,72,.045)}
.card-title{color:#17233f;font-size:17px;font-weight:760;margin-bottom:4px}
.card-subtitle{color:#707a8f;font-size:11px;margin-bottom:9px}
.metric{background:#fbfcff;border:1px solid #e3e7ef;border-radius:9px;padding:9px 11px;min-height:64px}
.metric-label{color:#737d90;font-size:9px;font-weight:760;letter-spacing:.06em;text-transform:uppercase}
.metric-value{color:#17233f;font-size:19px;font-weight:780;margin-top:3px}
.live-pill{display:inline-block;padding:4px 9px;border-radius:999px;background:#e5f7ec;color:#116b38;font-size:10px;font-weight:800;letter-spacing:.05em}
.replay-pill{display:inline-block;padding:4px 9px;border-radius:999px;background:#eeeaff;color:#5540c9;font-size:10px;font-weight:800;letter-spacing:.05em}
.dir-up{background:#e8f7ee!important;color:#116b38!important;border-color:#a9dfbf!important}
.dir-up-strong{background:#bfe8ce!important;color:#084f28!important;border-color:#75c995!important}
.dir-up-break{background:#72c58e!important;color:#06391c!important;border-color:#4ba96a!important}
.dir-down{background:#fff0f0!important;color:#a11e25!important;border-color:#efbcbc!important}
.dir-down-strong{background:#f5c9ca!important;color:#761219!important;border-color:#e79598!important}
.dir-down-break{background:#e78a8d!important;color:#5c0a10!important;border-color:#cf6266!important}
.wait{background:#eef2f7!important;color:#536174!important;border-color:#d6dde7!important}
.developing{background:#fff5d9!important;color:#8a5b00!important;border-color:#edd49a!important}
.breakout{font-weight:850!important}
.small-note{color:#737d90;font-size:10px}
</style>
""", unsafe_allow_html=True)


def source_ts(path: Path) -> pd.Timestamp:
    try:
        return parse_observation_timestamp(path)
    except Exception:
        try:
            return pd.Timestamp.fromtimestamp(path.stat().st_mtime)
        except Exception:
            return pd.NaT


def source_files(trading_date: str | None = None) -> list[Path]:
    try:
        files = [Path(p) for p in discover_historical_snapshots(trading_date)]
    except Exception:
        return []
    valid = [(p, source_ts(p)) for p in files]
    valid = [(p, ts) for p, ts in valid if pd.notna(ts)]
    valid.sort(key=lambda x: (x[1], str(x[0]).lower()))
    return [p for p, _ in valid]


def source_bundles(files: list[Path], tolerance_seconds: int = 60) -> list[list[Path]]:
    """Group source files that belong to one observation window."""
    if not files:
        return []
    groups: list[list[Path]] = [[files[0]]]
    for p in files[1:]:
        prev = source_ts(groups[-1][-1])
        cur = source_ts(p)
        if pd.notna(prev) and pd.notna(cur) and (cur - prev).total_seconds() <= tolerance_seconds:
            groups[-1].append(p)
        else:
            groups.append([p])
    return groups


def latest_file(files: list[Path]) -> tuple[Path | None, pd.Timestamp | None]:
    if not files:
        return None, None
    p = max(files, key=source_ts)
    return p, source_ts(p)


def frozen_base(snapshot: pd.DataFrame) -> dict:
    if snapshot.empty or "Symbol" not in snapshot.columns:
        return {}
    result = {}
    for _, r in snapshot.drop_duplicates("Symbol").iterrows():
        symbol = str(r.get("Symbol","")).strip().upper()
        op = pd.to_numeric(r.get("daily_open_reference"), errors="coerce")
        prem = pd.to_numeric(r.get("opening_straddle_premium"), errors="coerce")
        if symbol and pd.notna(op) and pd.notna(prem) and prem > 0:
            result[symbol] = {"open_price": float(op), "opening_straddle_premium": float(prem)}
    return result


def candidates(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame()
    return build_current_predictions(snapshot, frozen_base(snapshot))


def decision_class(row: pd.Series) -> str:
    d = str(row.get("direction_label","")).upper()
    strength = str(row.get("strength_label","")).upper()
    progress = float(row.get("progress",0) or 0)
    if "WAIT" in strength:
        return "wait"
    if progress >= 100:
        return "dir-up-break" if d == "BULLISH" else "dir-down-break"
    if strength == "STRONG":
        return "dir-up-strong" if d == "BULLISH" else "dir-down-strong"
    if strength == "DEVELOPING":
        return "developing"
    return "dir-up" if d == "BULLISH" else "dir-down"


def filter_queue(df: pd.DataFrame, key: str) -> pd.DataFrame:
    if df.empty:
        return df
    opts = ["All","Bullish","Bearish","Developing","Wait","Approaching","Breakout"]
    selected = st.radio("Filter", opts, horizontal=True, key=key)
    out = df.copy()
    if selected == "Bullish":
        out = out[out.direction_label.eq("BULLISH")]
    elif selected == "Bearish":
        out = out[out.direction_label.eq("BEARISH")]
    elif selected == "Developing":
        out = out[out.strength_label.eq("DEVELOPING")]
    elif selected == "Wait":
        out = out[out.strength_label.str.contains("WAIT", na=False)]
    elif selected == "Approaching":
        out = out[out.progress.ge(75) & out.progress.lt(100)]
    elif selected == "Breakout":
        out = out[out.factual_breakout]
    return out


def queue_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return pd.DataFrame({
        "SYMBOL": df.symbol,
        "DECISION": df.decision,
        "PRICE MOVE": df.signed_price_move_pct.map(lambda x:f"{x:+.2f}%"),
        "STRADDLE MOVE": df.progress.map(lambda x:f"{x:.1f}%"),
        "STAGE": df.stage,
        "CONFIRMATION": df.strength_label,
        "STRENGTH": df.strength.map(lambda x:f"{x:.0f}"),
        "BREAKOUT": df.factual_breakout.map(lambda x:"YES" if x else "—"),
    })


def styled_queue(df: pd.DataFrame):
    table = queue_table(df)
    if table.empty:
        return
    def style_row(row):
        d = str(row.get("DECISION","")).upper()
        if "BULLISH" in d:
            cls = "background-color:#bfe8ce;color:#084f28;font-weight:750;"
        elif "BEARISH" in d:
            cls = "background-color:#f5c9ca;color:#761219;font-weight:750;"
        elif "WAIT" in d:
            cls = "background-color:#eef2f7;color:#536174;font-weight:700;"
        else:
            cls = "background-color:#fff5d9;color:#8a5b00;font-weight:700;"
        return [cls if c in {"DECISION","STAGE","CONFIRMATION"} else "" for c in row.index]
    st.dataframe(table.style.apply(style_row, axis=1), width="stretch", hide_index=True)


def counts(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"bull":0,"bear":0,"strong":0,"dev":0,"wait":0,"break":0}
    return {
        "bull":int(df.direction_label.eq("BULLISH").sum()),
        "bear":int(df.direction_label.eq("BEARISH").sum()),
        "strong":int(df.strength_label.eq("STRONG").sum()),
        "dev":int(df.strength_label.eq("DEVELOPING").sum()),
        "wait":int(df.strength_label.str.contains("WAIT", na=False).sum()),
        "break":int(df.factual_breakout.sum()),
    }


def historical_table(events: pd.DataFrame, trading_date: str | None):
    if events.empty:
        return
    h = events.copy()
    h["observation_timestamp"] = pd.to_datetime(h.get("observation_timestamp"), errors="coerce")
    h["trading_date"] = h.get("trading_date","").astype(str).str[:10]
    h["straddle_progress_pct"] = (
        (pd.to_numeric(h["current_price"], errors="coerce") -
         pd.to_numeric(h["open_price"], errors="coerce")).abs()
        / pd.to_numeric(h["opening_straddle_premium"], errors="coerce").replace(0,pd.NA)
        * 100
    )
    if trading_date:
        h = h[h.trading_date.eq(trading_date)]
    if h.empty:
        st.info("No factual first-breakout events recorded for this day.")
        return
    h = h.sort_values(["observation_timestamp","straddle_progress_pct"], ascending=[False,False])
    display = pd.DataFrame({
        "TIME": h.observation_timestamp.dt.strftime("%H:%M:%S").fillna("—"),
        "SYMBOL": h.symbol,
        "DIRECTION": h.direction.map({"UP":"🟢 UP","DOWN":"🔴 DOWN"}).fillna(h.direction),
        "STRADDLE": h.straddle_progress_pct.map(lambda x:f"{x:.1f}%" if pd.notna(x) else "—"),
        "PRICE MOVE": pd.to_numeric(h.price_chg_pct, errors="coerce").map(lambda x:f"{x:+.2f}%" if pd.notna(x) else "—"),
        "BREAKOUT DIST": pd.to_numeric(h.breakout_distance, errors="coerce").map(lambda x:f"{x:+.2f}" if pd.notna(x) else "—"),
    })
    st.dataframe(display, width="stretch", hide_index=True)


st.markdown("""
<div class="sdl-header">
<div class="sdl-title">SDL — Straddle Breakout Decision Center</div>
<div class="sdl-subtitle">±0.75% price gate → 25/50/75/100% of frozen straddle → confirmation → strength priority</div>
</div>
""", unsafe_allow_html=True)

# ---------- live processing ----------
today = pd.Timestamp.now().date().isoformat()
files = source_files(today)
bundles = source_bundles(files)
live_path, live_ts = latest_file(files)

state = load_state(STATE_JSON)
last_state_ts = pd.to_datetime(state.get("last_observation_timestamp"), errors="coerce")

# Automatically advance one unprocessed observation bundle at a time.
if bundles:
    bundle_meta = []
    for group in bundles:
        ts = source_ts(group[-1])
        bundle_meta.append((ts, group))
    pending = [x for x in bundle_meta if pd.notna(x[0]) and (pd.isna(last_state_ts) or x[0] > last_state_ts)]
    if pending and st.session_state.get("sdl_auto_enabled", True):
        ts, group = pending[0]
        # The Daywise workbook is the canonical complete snapshot. When several
        # files fall into one observation window, process the latest complete
        # workbook once; they do not become separate decision states.
        try:
            process_snapshot(group[-1], ts)
            st.session_state["sdl_last_auto_bundle"] = ts.isoformat()
            st.rerun()
        except Exception as exc:
            st.session_state["sdl_auto_error"] = str(exc)

# ---------- header/status ----------
mode = "LIVE"
if st.session_state.get("sdl_replay_timestamp"):
    mode = "REPLAY"

c1,c2,c3,c4 = st.columns([1.0,1.3,1.1,1.1])
with c1:
    st.markdown('<span class="live-pill">● LIVE</span>' if mode=="LIVE" else '<span class="replay-pill">● REPLAY</span>', unsafe_allow_html=True)
with c2:
    st.markdown(f"**As of:** {live_ts.strftime('%d %b %Y, %H:%M:%S') if pd.notna(live_ts) else '—'}")
with c3:
    st.markdown(f"**Bundles today:** {len(bundles)}")
with c4:
    if st.button("↻ Refresh", width="stretch"):
        st.rerun()

# ---------- live decision queue ----------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">1. LIVE DECISION QUEUE</div>', unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">Automatically advances through completed observation bundles. Previous per-stock state remains the processing state. This queue is the current system output, not a historical table.</div>', unsafe_allow_html=True)

live_df = pd.DataFrame()
if live_path is not None:
    try:
        _, live_df, _ = __import__("pipeline").process_snapshot(live_path, live_ts)
    except Exception:
        pass
live_candidates = candidates(live_df)
lc = counts(live_candidates)
if live_candidates.empty:
    st.info("No currently qualified live decision candidates.")
else:
    st.caption(f"Current evidence bundle: **{live_ts.strftime('%d %b %Y, %H:%M:%S')}**")
    q = filter_queue(live_candidates, "sdl_live_filter")
    styled_queue(q)
st.markdown('</div>', unsafe_allow_html=True)

# ---------- top priority ----------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">2. TOP PRIORITY NOW</div>', unsafe_allow_html=True)
st.markdown(f'<div class="card-subtitle">Ranked strongest current opportunities · Snapshot: {live_ts.strftime("%d %b %Y, %H:%M:%S") if pd.notna(live_ts) else "—"}</div>', unsafe_allow_html=True)
if live_candidates.empty:
    st.info("No priority candidate at the current live snapshot.")
else:
    priority = live_candidates.sort_values(
        ["factual_breakout","strength","progress"], ascending=[False,False,False]
    ).head(10)
    styled_queue(priority)
st.markdown('</div>', unsafe_allow_html=True)

# ---------- state metrics ----------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">3. CURRENT DECISION STATE</div>', unsafe_allow_html=True)
items = [
    ("LIVE CANDIDATES",len(live_candidates)),("BULLISH",lc["bull"]),("BEARISH",lc["bear"]),
    ("STRONG",lc["strong"]),("DEVELOPING",lc["dev"]),("WAIT",lc["wait"]),
    ("BREAKOUT",lc["break"]),("AS OF",live_ts.strftime("%H:%M:%S") if pd.notna(live_ts) else "—")
]
cols=st.columns(8)
for col,(label,value) in zip(cols,items):
    with col:
        st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>',unsafe_allow_html=True)
st.markdown('</div>',unsafe_allow_html=True)

# ---------- replay ----------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">4. REPLAY / SNAPSHOT CHECK</div>', unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">Manual investigation only. Select a historical snapshot; no future evidence is used.</div>', unsafe_allow_html=True)
dates=sorted({source_ts(p).date().isoformat() for p in source_files() if pd.notna(source_ts(p))}, reverse=True)
if dates:
    rdate=st.selectbox("Trading date",dates,format_func=lambda x:pd.Timestamp(x).strftime("%d %b %Y"),key="sdl_replay_date")
    rfiles=source_files(rdate)
    if rfiles:
        selected=st.selectbox("Snapshot",rfiles,format_func=lambda p:f"{source_ts(p).strftime('%d %b %Y, %H:%M:%S')} | {p.name}",key="sdl_replay_snapshot")
        if st.button("Replay selected snapshot",type="primary"):
            try:
                # Rebuild the selected day chronologically, then expose the selected
                # source state for inspection.
                replay_trading_date(rdate)
                from pipeline import process_snapshot as _ps
                _, replay_df, replay_ts = _ps(selected, source_ts(selected))
                st.session_state["sdl_replay_df"] = replay_df
                st.session_state["sdl_replay_timestamp"] = source_ts(selected)
                st.rerun()
            except Exception as exc:
                st.error(f"Replay failed: {exc}")
else:
    st.info("No source snapshots available.")
if st.session_state.get("sdl_replay_timestamp"):
    rts=pd.to_datetime(st.session_state["sdl_replay_timestamp"])
    rdf=st.session_state.get("sdl_replay_df",pd.DataFrame())
    rc=candidates(rdf)
    st.markdown(f'<span class="replay-pill">REPLAY · {rts.strftime("%d %b %Y, %H:%M:%S")}</span>',unsafe_allow_html=True)
    if not rc.empty:
        styled_queue(filter_queue(rc,"sdl_replay_filter"))
    else:
        st.info("No qualified candidates at the selected replay snapshot.")
st.markdown('</div>',unsafe_allow_html=True)

# ---------- inspector ----------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">5. DECISION INSPECTOR</div>', unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">Inspect the evidence behind a qualified current or replay decision. This does not change selection.</div>', unsafe_allow_html=True)
inspect=live_candidates
if st.session_state.get("sdl_replay_timestamp") and not st.session_state.get("sdl_replay_df",pd.DataFrame()).empty:
    inspect=candidates(st.session_state["sdl_replay_df"])
if inspect.empty:
    st.info("No candidate available.")
else:
    sym=st.selectbox("Stock",inspect.symbol.tolist(),key="sdl_inspect")
    row=inspect[inspect.symbol.eq(sym)].iloc[0]
    css=decision_class(row)
    st.markdown(f'<div class="card {css}"><div style="font-size:18px;font-weight:800">{row.decision}</div><div style="font-size:11px;margin-top:4px">Progress {row.progress:.1f}% of frozen S · Price {row.signed_price_move_pct:+.2f}% · Frozen S ₹{row.frozen_straddle:.2f}</div></div>',unsafe_allow_html=True)
    a,b,c,d,e=st.columns(5)
    a.metric("Open",f"{row.opening_price:.2f}")
    b.metric("Current",f"{row.current_price:.2f}")
    c.metric("Frozen S",f"{row.frozen_straddle:.2f}")
    d.metric("Upper",f"{row.upper_breakout:.2f}")
    e.metric("Lower",f"{row.lower_breakout:.2f}")
    factors=[{"FACTOR":f.label,"STATE":f.state,"WEIGHT":f.weight} for f in row.factors]
    st.dataframe(pd.DataFrame(factors),width="stretch",hide_index=True)
st.markdown('</div>',unsafe_allow_html=True)

# ---------- historical evidence ----------
events=load_events(EVENT_CSV)
st.markdown('<div class="card">',unsafe_allow_html=True)
st.markdown('<div class="card-title">6. HISTORICAL EVIDENCE</div>',unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">Factual first-breakout history only. Reference/audit view; it does not create the current decision.</div>',unsafe_allow_html=True)
historical_table(events,today)
st.markdown('</div>',unsafe_allow_html=True)

st.markdown('<div class="small-note">Frozen decision logic is unchanged: ±0.75% primary price gate → 25/50/75/100% of frozen opening straddle → secondary confirmation → strength priority. Source files remain read-only.</div>',unsafe_allow_html=True)
