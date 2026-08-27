from __future__ import annotations

from pathlib import Path
import time

import pandas as pd
import streamlit as st

import config as sdl_config
import pipeline as sdl_pipeline
from config import EVENT_CSV, STATE_JSON
from pipeline import discover_historical_snapshots, process_snapshot, replay_trading_date
from prediction_engine import build_current_predictions
from source_loader import parse_observation_timestamp
from storage import load_events, load_state


st.set_page_config(
    page_title="NTIS SDL — Intraday Decision Centre",
    page_icon="SDL",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# VISUAL SYSTEM
# The structure intentionally mirrors the approved Decision Centre reference:
# admin strip -> header -> control row -> processing state -> top priority ->
# live queue -> current decision state -> collapsed inspector/history -> footer
# -> fixed mobile navigation.
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
:root{
  --navy:#06132e;
  --navy2:#163b78;
  --navy3:#213f7a;
  --ink:#13213b;
  --muted:#68748a;
  --page:#f6f8fb;
  --panel:#ffffff;
  --line:#dfe5ee;
  --green:#e5f7ec;
  --green2:#bfe8ce;
  --green-ink:#087238;
  --red:#fde8e9;
  --red2:#f4c4c7;
  --red-ink:#a51e27;
  --amber:#fff6dc;
  --amber-ink:#8b5d00;
  --purple:#6537d6;
  --purple-soft:#eee9ff;
}

html { scroll-behavior:smooth; }
.stApp { background:var(--page); color:var(--ink); }
.block-container{
  max-width:1180px;
  padding:10px 18px 92px;
}
header[data-testid="stHeader"]{background:transparent;}
section[data-testid="stSidebar"]{display:none;}

.sdl-admin{
  background:#fff;
  border:1px solid var(--line);
  border-radius:9px;
  padding:8px 12px;
  margin:2px 0 8px;
}
.sdl-admin-title{
  font-size:12px;font-weight:750;color:var(--ink);
}
.sdl-admin-help{
  font-size:9px;color:var(--muted);margin-top:2px;
}

.sdl-hero{
  background:linear-gradient(105deg,var(--navy) 0%, #0c2b60 58%, var(--navy3) 100%);
  border-radius:12px;
  color:#fff;
  padding:12px 16px;
  box-shadow:0 7px 22px rgba(6,19,46,.15);
  margin-bottom:8px;
}
.sdl-hero-row{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
}
.sdl-brand{
  display:flex;align-items:center;gap:10px;min-width:0;
}
.sdl-logo{
  width:40px;height:40px;border-radius:10px;background:#fff;
  display:flex;align-items:center;justify-content:center;
  color:#122f6a;font-weight:950;font-size:14px;letter-spacing:-.04em;
  box-shadow:0 2px 9px rgba(0,0,0,.15);flex:0 0 auto;
}
.sdl-name{
  font-size:19px;font-weight:850;line-height:1.05;white-space:nowrap;
}
.sdl-sub{
  font-size:9px;opacity:.88;margin-top:4px;
}
.sdl-live{
  display:flex;flex-direction:column;align-items:flex-end;gap:2px;
  white-space:nowrap;
}
.sdl-live-pill{
  display:inline-flex;align-items:center;gap:5px;
  background:#064b32;color:#d9ffe9;border-radius:999px;
  padding:5px 9px;font-size:9px;font-weight:850;
}
.sdl-live-dot{width:7px;height:7px;border-radius:50%;background:#21d07a;}
.sdl-asof{font-size:9px;font-weight:750;}
.sdl-date{font-size:9px;opacity:.9;}
.sdl-processing{font-size:8px;color:#64e3a1;}

.control-grid{
  display:grid;
  grid-template-columns:1.05fr 1.55fr .95fr;
  gap:8px;
  margin-bottom:8px;
}
.control-card{
  background:#fff;border:1px solid var(--line);border-radius:10px;
  padding:10px 11px;min-height:70px;
}
.control-title{
  font-size:10px;font-weight:850;letter-spacing:.04em;color:var(--ink);
}
.control-copy{
  font-size:8px;line-height:1.35;color:var(--muted);margin-top:6px;
}
.control-row{
  display:flex;align-items:center;gap:8px;margin-top:8px;
}
.mode-chip{
  border:1px solid var(--line);border-radius:8px;padding:8px 9px;
  font-size:9px;min-width:74px;background:#fff;
}
.mode-chip.live-active{border-color:#55b77e;background:#f0fbf5;}
.mode-dot{
  width:7px;height:7px;border-radius:50%;display:inline-block;
  border:1px solid #b7bec9;margin-right:5px;
}
.mode-dot.live{background:#19a866;border-color:#19a866;}
.mode-caption{font-size:8px;color:var(--muted);margin-top:3px;}

.replay-row{
  display:grid;grid-template-columns:1fr 1.05fr .65fr;gap:8px;
  margin-bottom:8px;
}
.replay-card{
  background:#fff;border:1px solid var(--line);border-radius:10px;
  padding:7px 9px;
}
.replay-label{
  font-size:8px;font-weight:800;color:var(--muted);margin-bottom:3px;
}
.replay-value{
  font-size:10px;font-weight:750;color:var(--ink);
}
.replay-action{
  background:#ff4f57;color:#fff;border-radius:8px;padding:9px 12px;
  text-align:center;font-size:9px;font-weight:850;
  min-height:37px;display:flex;align-items:center;justify-content:center;
}

.process-banner{
  background:var(--amber);border:1px solid #f0d47d;border-radius:9px;
  padding:8px 11px;margin:4px 0 9px;
  display:flex;align-items:center;justify-content:space-between;gap:10px;
}
.process-main{font-size:9px;font-weight:850;color:#6d4a00;}
.process-sub{font-size:8px;color:#8b6b24;margin-top:2px;}
.process-time{font-size:8px;color:#795a14;text-align:right;}

.section{
  background:#fff;border:1px solid var(--line);border-radius:11px;
  margin:8px 0;overflow:hidden;
}
.section-head{
  padding:9px 12px;
  border-bottom:1px solid var(--line);
}
.section-title{
  font-size:12px;font-weight:900;color:var(--ink);
}
.section-sub{
  font-size:8px;color:var(--muted);margin-top:3px;
}
.priority-head{
  background:linear-gradient(105deg,var(--navy),#173d7d);
  color:#fff;border-bottom:none;padding:10px 12px;
}
.priority-head .section-title{color:#fff;}
.priority-head .section-sub{color:#dbe6fb;}
.snapshot-pill{
  float:right;background:#2c206e;color:#e9e1ff;border-radius:999px;
  padding:4px 8px;font-size:7px;font-weight:800;
}

.table-wrap{overflow-x:auto;padding:0 8px 5px;}
.sdl-table{
  width:100%;border-collapse:collapse;font-size:8px;min-width:760px;
}
.sdl-table th{
  text-align:left;color:#667289;font-size:7px;letter-spacing:.04em;
  font-weight:850;padding:7px 6px;border-bottom:1px solid var(--line);
  white-space:nowrap;
}
.sdl-table td{
  padding:7px 6px;border-bottom:1px solid #edf0f5;vertical-align:middle;
  white-space:nowrap;
}
.decision-pill{
  display:inline-block;padding:4px 6px;border-radius:6px;
  font-size:7px;font-weight:900;white-space:normal;line-height:1.25;
}
.bull{background:var(--green);color:var(--green-ink);border:1px solid #b7e8ca;}
.bear{background:var(--red);color:var(--red-ink);border:1px solid #f1c2c5;}
.wait{background:#f0f3f7;color:#59677d;border:1px solid #dce2ea;}
.dev{background:var(--amber);color:var(--amber-ink);border:1px solid #efd99c;}
.pos{color:#087238;font-weight:850;}
.neg{color:#a51e27;font-weight:850;}
.neutral{color:#68748a;}
.strength-box{
  display:inline-block;min-width:24px;text-align:center;padding:3px 5px;
  border-radius:5px;background:#f0f7f2;color:#087238;font-weight:850;
}
.break-yes{font-weight:900;color:#087238;}

.filter-wrap{
  padding:7px 10px 9px;border-top:1px solid var(--line);
}
.filter-title{
  font-size:8px;font-weight:850;color:var(--ink);margin-bottom:5px;
}
.filter-note{font-weight:500;color:var(--muted);}
.state-grid{
  display:grid;grid-template-columns:repeat(6,1fr);gap:7px;
  padding:8px 10px 10px;
}
.state-box{
  background:#fbfcfe;border:1px solid var(--line);padding:8px 5px;
  text-align:center;border-radius:6px;
}
.state-label{font-size:6px;color:#68748a;font-weight:850;}
.state-value{font-size:14px;font-weight:900;color:var(--ink);margin-top:2px;}

.collapsed-section{
  background:#fff;border:1px solid var(--line);border-radius:9px;
  margin:7px 0;padding:10px 12px;font-size:9px;font-weight:850;
  color:var(--ink);
}
.collapsed-section span{color:var(--muted);font-weight:500;}

.footer{
  text-align:center;color:#778297;font-size:7px;padding:9px 0 2px;
}
.bottom-nav{
  position:fixed;left:0;right:0;bottom:0;z-index:9999;
  background:var(--navy);border-top:1px solid #274272;
  display:flex;justify-content:center;gap:0;
  box-shadow:0 -5px 18px rgba(6,19,46,.16);
}
.bottom-nav a{
  color:#e5ecfa;text-decoration:none;font-size:8px;
  padding:9px 18px 8px;text-align:center;min-width:86px;
}
.bottom-nav a:hover{background:#10244a;}
.bottom-icon{display:block;font-size:12px;line-height:1;margin-bottom:3px;}

@media (max-width:800px){
  .block-container{max-width:760px;padding:6px 10px 78px;}
  .control-grid{grid-template-columns:1fr 1.35fr .9fr;gap:5px;}
  .control-card{min-height:64px;padding:8px;}
  .replay-row{grid-template-columns:1fr 1.05fr .72fr;gap:5px;}
  .sdl-name{font-size:15px;}
  .sdl-logo{width:34px;height:34px;font-size:12px;}
  .sdl-hero{padding:9px 11px;}
  .state-grid{grid-template-columns:repeat(3,1fr);}
  .bottom-nav a{min-width:20%;padding:8px 3px;font-size:7px;}
  .bottom-icon{font-size:11px;}
}

@media (max-width:560px){
  .block-container{padding-left:6px;padding-right:6px;}
  .sdl-live{display:none;}
  .control-grid{grid-template-columns:1fr 1.25fr .8fr;}
  .control-copy{font-size:7px;}
  .control-title{font-size:8px;}
  .replay-row{grid-template-columns:1fr 1fr .85fr;}
  .state-grid{grid-template-columns:repeat(3,1fr);gap:5px;}
  .sdl-table{font-size:7px;}
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data helpers — intentionally reuse the existing SDL pipeline.
# ---------------------------------------------------------------------------
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
    vals = [(p, source_ts(p)) for p in files]
    vals = [(p, ts) for p, ts in vals if pd.notna(ts)]
    vals.sort(key=lambda x: (x[1], str(x[0]).lower()))
    return [p for p, _ in vals]


def source_bundles(files: list[Path], tolerance_seconds: int = 60) -> list[list[Path]]:
    if not files:
        return []
    groups = [[files[0]]]
    for p in files[1:]:
        prev = source_ts(groups[-1][-1])
        cur = source_ts(p)
        if pd.notna(prev) and pd.notna(cur) and (cur - prev).total_seconds() <= tolerance_seconds:
            groups[-1].append(p)
        else:
            groups.append([p])
    return groups


def latest_file(files: list[Path]):
    if not files:
        return None, None
    p = max(files, key=source_ts)
    return p, source_ts(p)


def frozen_base(snapshot: pd.DataFrame) -> dict:
    if snapshot.empty or "Symbol" not in snapshot.columns:
        return {}
    result = {}
    for _, r in snapshot.drop_duplicates("Symbol").iterrows():
        symbol = str(r.get("Symbol", "")).strip().upper()
        op = pd.to_numeric(r.get("daily_open_reference"), errors="coerce")
        prem = pd.to_numeric(r.get("opening_straddle_premium"), errors="coerce")
        if symbol and pd.notna(op) and pd.notna(prem) and prem > 0:
            result[symbol] = {
                "open_price": float(op),
                "opening_straddle_premium": float(prem),
            }
    return result


def candidates(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame()
    return build_current_predictions(snapshot, frozen_base(snapshot))


def decision_pill(decision: str) -> tuple[str, str]:
    text = str(decision or "")
    upper = text.upper()
    if "WAIT" in upper:
        return "wait", text
    if "BULLISH" in upper:
        return "bull", text
    if "BEARISH" in upper:
        return "bear", text
    return "dev", text


def priority_sort(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["_break"] = out["factual_breakout"].fillna(False).astype(int)
    out["_strength"] = pd.to_numeric(out["strength"], errors="coerce").fillna(0)
    out["_progress"] = pd.to_numeric(out["progress"], errors="coerce").fillna(0)
    return out.sort_values(
        ["_break", "_strength", "_progress"],
        ascending=[False, False, False],
    ).drop(columns=["_break", "_strength", "_progress"])


def html_table(df: pd.DataFrame, limit: int | None = None) -> str:
    if df.empty:
        return '<div style="padding:12px;color:#68748a;font-size:9px;">No qualified decisions.</div>'
    rows = []
    view = priority_sort(df).head(limit) if limit else df
    for i, (_, r) in enumerate(view.iterrows(), 1):
        cls, decision = decision_pill(r.get("decision"))
        move = pd.to_numeric(r.get("signed_price_move_pct"), errors="coerce")
        move_txt = f"{move:+.2f}%" if pd.notna(move) else "—"
        move_cls = "pos" if pd.notna(move) and move > 0 else "neg" if pd.notna(move) and move < 0 else "neutral"
        prog = pd.to_numeric(r.get("progress"), errors="coerce")
        prog_txt = f"{prog:.1f}%" if pd.notna(prog) else "—"
        strength = pd.to_numeric(r.get("strength"), errors="coerce")
        strength_txt = f"{strength:.0f}" if pd.notna(strength) else "—"
        breakout = "YES" if bool(r.get("factual_breakout", False)) else "—"
        stage = str(r.get("stage", "—"))
        confirmation = str(r.get("strength_label", "—"))
        symbol = str(r.get("symbol", "—"))
        next_level = "NEXT 100%" if pd.notna(prog) and prog >= 75 else "NEXT 75%" if pd.notna(prog) and prog >= 50 else "NEXT 50%"
        rows.append(
            f"""
<tr>
<td>{i}</td>
<td><b>{symbol}</b></td>
<td><span class="decision-pill {cls}">{decision}</span></td>
<td class="{move_cls}">{move_txt}</td>
<td>{prog_txt}</td>
<td>{stage}</td>
<td>{confirmation}</td>
<td><span class="strength-box">{strength_txt}</span></td>
<td class="break-yes">{breakout}</td>
<td>{next_level if breakout != "YES" else "—"}</td>
</tr>"""
        )
    return f"""
<div class="table-wrap">
<table class="sdl-table">
<thead><tr>
<th>#</th><th>SYMBOL</th><th>DECISION</th><th>PRICE MOVE</th>
<th>STRADDLE MOVE</th><th>STAGE</th><th>CONFIRMATION</th>
<th>STRENGTH</th><th>BREAKOUT</th><th>NEXT LEVEL</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</div>
"""


def counts(df: pd.DataFrame) -> dict[str, int]:
    if df.empty:
        return dict(candidates=0, bullish=0, bearish=0, strong=0, developing=0, wait=0, breakout=0)
    return dict(
        candidates=len(df),
        bullish=int(df.direction_label.eq("BULLISH").sum()),
        bearish=int(df.direction_label.eq("BEARISH").sum()),
        strong=int(df.strength_label.eq("STRONG").sum()),
        developing=int(df.strength_label.eq("DEVELOPING").sum()),
        wait=int(df.strength_label.str.contains("WAIT", na=False).sum()),
        breakout=int(df.factual_breakout.fillna(False).sum()),
    )


def apply_source_root(root_text: str):
    root = Path(root_text).expanduser().resolve()
    sdl_pipeline.INTRADAY_SOURCE_ROOT = root
    sdl_config.INTRADAY_SOURCE_ROOT = root
    st.session_state["sdl_source_root"] = str(root)
    return root


if "sdl_source_root" not in st.session_state:
    st.session_state["sdl_source_root"] = str(sdl_pipeline.INTRADAY_SOURCE_ROOT)

# ---------------------------------------------------------------------------
# ADMIN — source path exists here but is not part of the normal decision view.
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class="sdl-admin" id="settings">
  <div class="sdl-admin-title">› &nbsp;⚙ Admin Settings</div>
  <div class="sdl-admin-help">Operational settings are intentionally kept out of the decision surface.</div>
</div>
""",
    unsafe_allow_html=True,
)
with st.expander("Admin Settings", expanded=False):
    source_text = st.text_input(
        "Source data folder",
        value=st.session_state["sdl_source_root"],
        key="preview_source_input",
    )
    if st.button("Save source folder", key="preview_save_source"):
        root = apply_source_root(source_text)
        st.success("Source folder saved." if root.exists() else "Source folder saved; path is not currently accessible.")

# ---------------------------------------------------------------------------
# Resolve current state.
# ---------------------------------------------------------------------------
today = pd.Timestamp.now().date().isoformat()
files = source_files(today)
bundles = source_bundles(files)
live_path, live_ts = latest_file(files)
state = load_state(STATE_JSON)
last_state_ts = pd.to_datetime(state.get("last_observation_timestamp"), errors="coerce")

# Auto-processing remains the production behavior. This preview only changes
# presentation; it does not alter the decision engine.
if bundles and st.session_state.get("preview_auto", True):
    pending = [
        (source_ts(g[-1]), g)
        for g in bundles
        if pd.notna(source_ts(g[-1]))
        and (pd.isna(last_state_ts) or source_ts(g[-1]) > last_state_ts)
    ]
    if pending:
        ts, group = pending[0]
        try:
            process_snapshot(group[-1], ts)
            st.session_state["preview_last_processed"] = ts.isoformat()
        except Exception:
            pass

# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
mode = st.session_state.get("preview_mode", "LIVE")
asof = live_ts if pd.notna(live_ts) else pd.Timestamp.now()

st.markdown(
    f"""
<div class="sdl-hero">
  <div class="sdl-hero-row">
    <div class="sdl-brand">
      <div class="sdl-logo">SDL</div>
      <div>
        <div class="sdl-name">NTIS SDL — Intraday Decision Centre</div>
        <div class="sdl-sub">Live Decision Queue &amp; Historical Replay</div>
      </div>
    </div>
    <div class="sdl-live">
      <div class="sdl-live-pill"><span class="sdl-live-dot"></span>{mode}</div>
      <div class="sdl-asof">As of {asof.strftime("%I:%M:%S %p")}</div>
      <div class="sdl-date">{asof.strftime("%d-%b-%Y")}</div>
      <div class="sdl-processing">◉ Processing automatically</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# CONTROL SURFACE — same hierarchy as reference image.
# ---------------------------------------------------------------------------
st.markdown('<div class="control-grid">', unsafe_allow_html=True)
st.markdown(
    """
<div class="control-card">
  <div class="control-title">LIVE DATA</div>
  <div class="control-copy">Current state updates automatically as timestamp evidence bundles arrive.</div>
</div>
""",
    unsafe_allow_html=True,
)
st.markdown(
    """
<div class="control-card">
  <div class="control-title">HISTORICAL REPLAY</div>
  <div class="control-copy">Use the calendar and snapshot time for a manual historical decision check.</div>
</div>
""",
    unsafe_allow_html=True,
)
st.markdown(
    """
<div class="control-card">
  <div class="control-title">DISPLAY MODE</div>
  <div class="control-row">
    <div class="mode-chip live-active"><span class="mode-dot live"></span>LIVE<div class="mode-caption">Current State</div></div>
    <div class="mode-chip"><span class="mode-dot"></span>REPLAY<div class="mode-caption">Historical Snapshot</div></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# Streamlit controls under the visual cards.
r1, r2, r3 = st.columns([1, 1.05, .72])
with r1:
    all_files = source_files()
    dates = sorted({source_ts(p).date().isoformat() for p in all_files if pd.notna(source_ts(p))}, reverse=True)
    if dates:
        default_date = pd.Timestamp(st.session_state.get("preview_replay_date", dates[0])).date()
        replay_date = st.date_input(
            "Select Trading Day",
            value=default_date,
            min_value=min(pd.Timestamp(d).date() for d in dates),
            max_value=max(pd.Timestamp(d).date() for d in dates),
            key="preview_replay_calendar",
        )
        replay_date_iso = replay_date.isoformat()
    else:
        replay_date_iso = today
        replay_date = pd.Timestamp(today).date()
with r2:
    rfiles = source_files(replay_date_iso)
    labels = [source_ts(p).strftime("%I:%M:%S %p") for p in rfiles if pd.notna(source_ts(p))]
    selected_label = st.selectbox(
        "Select Snapshot Time",
        labels or ["No snapshots"],
        key="preview_replay_time",
    )
with r3:
    st.markdown('<div style="height:25px"></div>', unsafe_allow_html=True)
    if st.button("Load Replay", type="primary", use_container_width=True):
        if rfiles and labels:
            selected = rfiles[labels.index(selected_label)]
            try:
                with st.status("Preparing historical replay…", expanded=False) as status:
                    replay_trading_date(replay_date_iso)
                    _, rdf, rts = process_snapshot(selected, source_ts(selected))
                    st.session_state["preview_replay_df"] = rdf
                    st.session_state["preview_replay_timestamp"] = rts
                    st.session_state["preview_mode"] = "REPLAY"
                    status.update(label=f"Replay ready · {selected_label}", state="complete")
                st.rerun()
            except Exception as exc:
                st.error(f"Replay failed: {exc}")

st.markdown('<div class="replay-row">', unsafe_allow_html=True)
st.markdown(
    f'<div class="replay-card"><div class="replay-label">SELECTED TRADING DAY</div><div class="replay-value">{replay_date.strftime("%Y/%m/%d")}</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="replay-card"><div class="replay-label">SELECTED SNAPSHOT TIME</div><div class="replay-value">{selected_label if labels else "—"}</div></div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="replay-card"><div class="replay-label">MODE</div><div class="replay-value">LIVE</div></div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# PROCESSING STATE
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class="process-banner">
  <div>
    <div class="process-main">◌ Processing evidence bundle…</div>
    <div class="process-sub">Please wait while we prepare the latest market evidence and decisions.</div>
  </div>
  <div class="process-time">Last updated: <b>{asof.strftime("%I:%M:%S %p")}</b><br>Updates automatically when evidence is available</div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Determine displayed dataset.
# ---------------------------------------------------------------------------
display_df = pd.DataFrame()
display_ts = asof
if mode == "REPLAY" and not st.session_state.get("preview_replay_df", pd.DataFrame()).empty:
    display_df = st.session_state["preview_replay_df"]
    display_ts = pd.to_datetime(st.session_state["preview_replay_timestamp"])
else:
    if live_path is not None:
        try:
            _, display_df, display_ts = process_snapshot(live_path, live_ts)
        except Exception:
            display_df = pd.DataFrame()

display_candidates = candidates(display_df)
c = counts(display_candidates)

# ---------------------------------------------------------------------------
# TOP PRIORITY — deliberately before the full live queue.
# ---------------------------------------------------------------------------
st.markdown('<div class="section" id="top">', unsafe_allow_html=True)
st.markdown(
    f"""
<div class="section-head priority-head">
  <span class="snapshot-pill">Snapshot: {display_ts.strftime("%d-%b-%Y %I:%M:%S %p") if pd.notna(display_ts) else "—"}</span>
  <div class="section-title">⭐ TOP PRIORITY NOW</div>
  <div class="section-sub">Highest opportunity — right now</div>
</div>
""",
    unsafe_allow_html=True,
)
st.markdown(html_table(display_candidates, limit=5), unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;padding:5px 8px 8px;font-size:8px;color:#6537d6;font-weight:850;">View full Live Decision Queue ›</div>',
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# LIVE QUEUE
# ---------------------------------------------------------------------------
st.markdown('<div class="section" id="live">', unsafe_allow_html=True)
st.markdown(
    """
<div class="section-head">
  <div class="section-title">1. LIVE DECISION QUEUE</div>
  <div class="section-sub">Automatically processed current evidence. Previous per-stock state remains part of the decision.</div>
</div>
""",
    unsafe_allow_html=True,
)

filter_choice = st.radio(
    "Filter by decision state",
    ["All", "Bullish", "Bearish", "Developing", "Wait", "Approaching", "Breakout"],
    horizontal=True,
    key="preview_live_filter",
    label_visibility="collapsed",
)
filtered = display_candidates.copy()
if filter_choice == "Bullish":
    filtered = filtered[filtered.direction_label.eq("BULLISH")]
elif filter_choice == "Bearish":
    filtered = filtered[filtered.direction_label.eq("BEARISH")]
elif filter_choice == "Developing":
    filtered = filtered[filtered.strength_label.eq("DEVELOPING")]
elif filter_choice == "Wait":
    filtered = filtered[filtered.strength_label.str.contains("WAIT", na=False)]
elif filter_choice == "Approaching":
    filtered = filtered[filtered.progress.ge(75) & filtered.progress.lt(100)]
elif filter_choice == "Breakout":
    filtered = filtered[filtered.factual_breakout.fillna(False)]

st.markdown(html_table(filtered), unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CURRENT DECISION STATE
# ---------------------------------------------------------------------------
st.markdown('<div class="section">', unsafe_allow_html=True)
st.markdown(
    """
<div class="section-head">
  <div class="section-title">2. CURRENT DECISION STATE</div>
  <div class="section-sub">Compact system state for the current completed evidence bundle.</div>
</div>
""",
    unsafe_allow_html=True,
)
state_items = [
    ("CANDIDATES", c["candidates"]),
    ("BULLISH", c["bullish"]),
    ("BEARISH", c["bearish"]),
    ("STRONG", c["strong"]),
    ("DEVELOPING", c["developing"]),
    ("WAIT", c["wait"]),
    ("BREAKOUT", c["breakout"]),
]
# Target has 7 compact state cards; keep them in one row on desktop and wrap on mobile.
st.markdown(
    '<div class="state-grid" style="grid-template-columns:repeat(7,1fr);">'
    + "".join(
        f'<div class="state-box"><div class="state-label">{label}</div><div class="state-value">{value}</div></div>'
        for label, value in state_items
    )
    + "</div>",
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# COLLAPSED DETAILS — not allowed to dominate the decision screen.
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class="collapsed-section" id="inspector">
  › &nbsp; 3. DECISION INSPECTOR <span>— tap to inspect</span>
</div>
""",
    unsafe_allow_html=True,
)
with st.expander("Open Decision Inspector", expanded=False):
    inspect_df = display_candidates
    if inspect_df.empty:
        st.info("No qualified decision is available.")
    else:
        symbol = st.selectbox("Selected Stock", inspect_df.symbol.tolist(), key="preview_inspect_symbol")
        row = inspect_df[inspect_df.symbol.eq(symbol)].iloc[0]
        st.markdown(f"### {row.decision}")
        a, b, cc, d, e = st.columns(5)
        a.metric("Open", f"{row.opening_price:.2f}")
        b.metric("Current", f"{row.current_price:.2f}")
        cc.metric("Frozen S", f"{row.frozen_straddle:.2f}")
        d.metric("Upper", f"{row.upper_breakout:.2f}")
        e.metric("Lower", f"{row.lower_breakout:.2f}")
        st.caption(
            f"Progress {row.progress:.1f}% of frozen S · Price {row.signed_price_move_pct:+.2f}%"
        )
        factors = [{"FACTOR": f.label, "STATE": f.state, "WEIGHT": f.weight} for f in row.factors]
        st.dataframe(pd.DataFrame(factors), use_container_width=True, hide_index=True)

st.markdown(
    """
<div class="collapsed-section">
  › &nbsp; 4. HISTORICAL EVIDENCE <span>— factual audit</span>
</div>
""",
    unsafe_allow_html=True,
)
with st.expander("Open Historical Evidence", expanded=False):
    events = load_events(EVENT_CSV)
    if events.empty:
        st.info("No factual first-breakout events recorded.")
    else:
        h = events.copy()
        h["observation_timestamp"] = pd.to_datetime(h.get("observation_timestamp"), errors="coerce")
        h["trading_date"] = h.get("trading_date", "").astype(str).str[:10]
        h = h[h.trading_date.eq(replay_date_iso)]
        st.dataframe(h, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# FOOTER + FIXED NAV
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class="footer">© 2026 NTIS SDL — Straddle Breakout Decision · Data updates automatically when new evidence is available</div>
<div class="bottom-nav">
  <a href="#live"><span class="bottom-icon">⌂</span>Live Queue</a>
  <a href="#top"><span class="bottom-icon">★</span>Top Priority</a>
  <a href="#replay"><span class="bottom-icon">↶</span>Replay</a>
  <a href="#inspector"><span class="bottom-icon">⌕</span>Inspector</a>
  <a href="#settings"><span class="bottom-icon">⚙</span>Settings</a>
</div>
""",
    unsafe_allow_html=True,
)
