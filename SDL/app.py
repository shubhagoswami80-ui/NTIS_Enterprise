
from __future__ import annotations

from pathlib import Path
import time

import pandas as pd
import streamlit as st

import config as sdl_config
import pipeline as sdl_pipeline
from config import EVENT_CSV, STATE_JSON
from pipeline import (
    discover_historical_snapshots,
    process_snapshot,
    replay_trading_date,
)
from prediction_engine import build_current_predictions
from source_loader import parse_observation_timestamp
from storage import load_events, load_state


st.set_page_config(
    page_title="SDL — Straddle Breakout Decision Center",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
:root{
 --navy:#0b1730;--navy2:#293f7a;--ink:#17233f;--muted:#6e788c;
 --panel:#ffffff;--page:#f4f6fa;--line:#e2e7ef;
 --green:#bfe8ce;--green-dark:#084f28;--green-break:#72c58e;
 --red:#f5c9ca;--red-dark:#761219;--red-break:#e78a8d;
 --amber:#fff3cf;--amber-dark:#8a5b00;--wait:#eef2f7;
}
.stApp{background:var(--page)}
.block-container{max-width:1220px;padding:14px 18px 34px}
section[data-testid="stSidebar"]{background:#fff}
.sdl-header{
 background:linear-gradient(105deg,var(--navy),#1a2b55 65%,var(--navy2));
 color:#fff;padding:14px 18px;border-radius:14px;margin-bottom:10px;
 box-shadow:0 5px 18px rgba(11,23,48,.12)
}
.sdl-brand{display:flex;align-items:center;gap:11px}
.sdl-logo{width:38px;height:38px;border-radius:10px;background:#fff;color:#182b57;
 display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:900;
 box-shadow:0 2px 8px rgba(0,0,0,.12)}
.sdl-title{font-size:22px;font-weight:820;line-height:1.1;margin:0}
.sdl-subtitle{font-size:10px;opacity:.88;margin-top:3px}
.status-row{display:flex;align-items:center;gap:10px;margin:6px 0 9px}
.live-pill,.replay-pill,.processing-pill{
 display:inline-block;padding:4px 9px;border-radius:999px;font-size:9px;
 font-weight:850;letter-spacing:.06em
}
.live-pill{background:#e5f7ec;color:#116b38}
.replay-pill{background:#eeeaff;color:#5540c9}
.processing-pill{background:#fff3cf;color:#8a5b00}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
 padding:12px 14px;margin:8px 0;box-shadow:0 3px 12px rgba(20,34,72,.035)}
.card-title{color:var(--ink);font-size:15px;font-weight:800;margin-bottom:2px}
.card-subtitle{color:var(--muted);font-size:10px;margin-bottom:8px}
.metric{background:#fbfcff;border:1px solid var(--line);border-radius:9px;
 padding:8px 9px;min-height:57px}
.metric-label{color:#737d90;font-size:8px;font-weight:800;letter-spacing:.06em}
.metric-value{color:var(--ink);font-size:17px;font-weight:800;margin-top:2px}
.small-note{color:var(--muted);font-size:9px}
section[data-testid="stExpander"]{border:1px solid var(--line);border-radius:11px;background:#fff}
div[data-testid="stDataFrame"]{font-size:11px}
@media (max-width:760px){
 .block-container{padding:8px 9px 24px}
 .sdl-header{padding:11px 12px;border-radius:11px}
 .sdl-logo{width:32px;height:32px;font-size:14px}
 .sdl-title{font-size:17px}
 .sdl-subtitle{font-size:8px}
 .card{padding:9px 10px;margin:6px 0}
 .card-title{font-size:13px}.card-subtitle{font-size:9px}
 .metric{min-height:50px}.metric-value{font-size:14px}
 .metric-label{font-size:7px}
}
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
    if not files:
        return []
    groups = [[files[0]]]
    for p in files[1:]:
        prev = source_ts(groups[-1][-1]); cur = source_ts(p)
        if pd.notna(prev) and pd.notna(cur) and (cur-prev).total_seconds() <= tolerance_seconds:
            groups[-1].append(p)
        else:
            groups.append([p])
    return groups


def latest_file(files: list[Path]):
    if not files: return None, None
    p = max(files,key=source_ts)
    return p,source_ts(p)


def frozen_base(snapshot: pd.DataFrame) -> dict:
    if snapshot.empty or "Symbol" not in snapshot.columns: return {}
    result={}
    for _,r in snapshot.drop_duplicates("Symbol").iterrows():
        symbol=str(r.get("Symbol","")).strip().upper()
        op=pd.to_numeric(r.get("daily_open_reference"),errors="coerce")
        prem=pd.to_numeric(r.get("opening_straddle_premium"),errors="coerce")
        if symbol and pd.notna(op) and pd.notna(prem) and prem>0:
            result[symbol]={"open_price":float(op),"opening_straddle_premium":float(prem)}
    return result


def candidates(snapshot: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame() if snapshot.empty else build_current_predictions(snapshot,frozen_base(snapshot))


def decision_class(row):
    d=str(row.get("direction_label","")).upper()
    strength=str(row.get("strength_label","")).upper()
    progress=float(row.get("progress",0) or 0)
    if "WAIT" in strength: return "wait"
    if progress>=100: return "dir-up-break" if d=="BULLISH" else "dir-down-break"
    if strength=="STRONG": return "dir-up-strong" if d=="BULLISH" else "dir-down-strong"
    if strength=="DEVELOPING": return "developing"
    return "dir-up" if d=="BULLISH" else "dir-down"


def filter_queue(df,key):
    if df.empty:return df
    opts=["All","Bullish","Bearish","Developing","Wait","Approaching","Breakout"]
    selected=st.radio("Filter",opts,horizontal=True,key=key)
    out=df.copy()
    if selected=="Bullish":out=out[out.direction_label.eq("BULLISH")]
    elif selected=="Bearish":out=out[out.direction_label.eq("BEARISH")]
    elif selected=="Developing":out=out[out.strength_label.eq("DEVELOPING")]
    elif selected=="Wait":out=out[out.strength_label.str.contains("WAIT",na=False)]
    elif selected=="Approaching":out=out[out.progress.ge(75)&out.progress.lt(100)]
    elif selected=="Breakout":out=out[out.factual_breakout]
    return out


def queue_table(df):
    if df.empty:return pd.DataFrame()
    return pd.DataFrame({
      "SYMBOL":df.symbol,"DECISION":df.decision,
      "PRICE MOVE":df.signed_price_move_pct.map(lambda x:f"{x:+.2f}%"),
      "STRADDLE MOVE":df.progress.map(lambda x:f"{x:.1f}%"),
      "STAGE":df.stage,"CONFIRMATION":df.strength_label,
      "STRENGTH":df.strength.map(lambda x:f"{x:.0f}"),
      "BREAKOUT":df.factual_breakout.map(lambda x:"YES" if x else "—")
    })


def styled_queue(df):
    table=queue_table(df)
    if table.empty:return
    def style_row(row):
        d=str(row.get("DECISION","")).upper()
        if "BULLISH" in d: cls="background-color:#bfe8ce;color:#084f28;font-weight:750;"
        elif "BEARISH" in d: cls="background-color:#f5c9ca;color:#761219;font-weight:750;"
        elif "WAIT" in d: cls="background-color:#eef2f7;color:#536174;font-weight:700;"
        else: cls="background-color:#fff3cf;color:#8a5b00;font-weight:700;"
        return [cls if c in {"DECISION","STAGE","CONFIRMATION"} else "" for c in row.index]
    st.dataframe(table.style.apply(style_row,axis=1),width="stretch",hide_index=True)


def counts(df):
    if df.empty:return {"bull":0,"bear":0,"strong":0,"dev":0,"wait":0,"break":0}
    return {"bull":int(df.direction_label.eq("BULLISH").sum()),
            "bear":int(df.direction_label.eq("BEARISH").sum()),
            "strong":int(df.strength_label.eq("STRONG").sum()),
            "dev":int(df.strength_label.eq("DEVELOPING").sum()),
            "wait":int(df.strength_label.str.contains("WAIT",na=False).sum()),
            "break":int(df.factual_breakout.sum())}


def historical_table(events,trading_date):
    if events.empty:return
    h=events.copy()
    h["observation_timestamp"]=pd.to_datetime(h.get("observation_timestamp"),errors="coerce")
    h["trading_date"]=h.get("trading_date","").astype(str).str[:10]
    h["straddle_progress_pct"]=((pd.to_numeric(h["current_price"],errors="coerce")-
        pd.to_numeric(h["open_price"],errors="coerce")).abs()/
        pd.to_numeric(h["opening_straddle_premium"],errors="coerce").replace(0,pd.NA)*100)
    if trading_date:h=h[h.trading_date.eq(trading_date)]
    if h.empty:
        st.info("No factual first-breakout events recorded for this day.");return
    h=h.sort_values(["observation_timestamp","straddle_progress_pct"],ascending=[False,False])
    display=pd.DataFrame({
      "TIME":h.observation_timestamp.dt.strftime("%H:%M:%S").fillna("—"),
      "SYMBOL":h.symbol,
      "DIRECTION":h.direction.map({"UP":"🟢 UP","DOWN":"🔴 DOWN"}).fillna(h.direction),
      "STRADDLE":h.straddle_progress_pct.map(lambda x:f"{x:.1f}%" if pd.notna(x) else "—"),
      "PRICE MOVE":pd.to_numeric(h.price_chg_pct,errors="coerce").map(lambda x:f"{x:+.2f}%" if pd.notna(x) else "—"),
      "BREAKOUT DIST":pd.to_numeric(h.breakout_distance,errors="coerce").map(lambda x:f"{x:+.2f}" if pd.notna(x) else "—")
    })
    st.dataframe(display,width="stretch",hide_index=True)


# ---------- internal source settings ----------
def apply_source_root(root_text: str):
    root=Path(root_text).expanduser().resolve()
    sdl_pipeline.INTRADAY_SOURCE_ROOT=root
    sdl_config.INTRADAY_SOURCE_ROOT=root
    st.session_state["sdl_source_root"]=str(root)
    return root

if "sdl_source_root" not in st.session_state:
    st.session_state["sdl_source_root"]=str(sdl_pipeline.INTRADAY_SOURCE_ROOT)

with st.sidebar:
    with st.expander("⚙ Admin Settings", expanded=False):
        st.caption("Administrator-only operational configuration. Runtime/log paths remain internal.")
        source_text=st.text_input("Source data folder",value=st.session_state["sdl_source_root"],key="sdl_source_input")
        if st.button("Save source folder",width="stretch"):
            root=apply_source_root(source_text)
            if root.exists():
                st.success("Source folder saved.")
            else:
                st.warning("Folder path saved, but it is not currently accessible.")
        st.caption(f"Active source: `{st.session_state['sdl_source_root']}`")


# ---------- header ----------
st.markdown("""
<div class="sdl-header">
 <div class="sdl-brand">
  <div class="sdl-logo">SDL</div>
  <div>
   <div class="sdl-title">Straddle Breakout Decision Center</div>
   <div class="sdl-subtitle">±0.75% price gate → 25/50/75/100% frozen straddle → confirmation → strength priority</div>
  </div>
 </div>
</div>
""",unsafe_allow_html=True)


# ---------- live processing ----------
today=pd.Timestamp.now().date().isoformat()
files=source_files(today)
bundles=source_bundles(files)
live_path,live_ts=latest_file(files)
state=load_state(STATE_JSON)
last_state_ts=pd.to_datetime(state.get("last_observation_timestamp"),errors="coerce")

if bundles:
    bundle_meta=[(source_ts(g[-1]),g) for g in bundles]
    pending=[x for x in bundle_meta if pd.notna(x[0]) and (pd.isna(last_state_ts) or x[0]>last_state_ts)]
    if pending and st.session_state.get("sdl_auto_enabled",True):
        ts,group=pending[0]
        with st.status(f"Processing evidence bundle {ts.strftime('%H:%M:%S')}…",expanded=False) as status:
            try:
                process_snapshot(group[-1],ts)
                st.session_state["sdl_last_auto_bundle"]=ts.isoformat()
                status.update(label=f"Processed evidence bundle {ts.strftime('%H:%M:%S')}",state="complete")
                st.rerun()
            except Exception as exc:
                status.update(label="Evidence bundle processing failed",state="error")
                st.error(str(exc))


# ---------- status ----------
mode="REPLAY" if st.session_state.get("sdl_replay_timestamp") else "LIVE"
c1,c2,c3,c4=st.columns([.9,1.5,1.1,1.0])
with c1: st.markdown(f'<span class="{"replay-pill" if mode=="REPLAY" else "live-pill"}">● {mode}</span>',unsafe_allow_html=True)
with c2: st.markdown(f"**As of:** {live_ts.strftime('%d %b %Y, %H:%M:%S') if pd.notna(live_ts) else '—'}")
with c3: st.markdown(f"**Bundles:** {len(bundles)}")
with c4:
    if st.button("↻ Refresh",width="stretch"): st.rerun()


# ---------- live queue ----------
st.markdown('<div class="card">',unsafe_allow_html=True)
st.markdown('<div class="card-title">1. LIVE DECISION QUEUE</div>',unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">Automatically advances through completed evidence bundles. Previous per-stock state is preserved.</div>',unsafe_allow_html=True)
live_df=pd.DataFrame()
if live_path is not None:
    try: _,live_df,_=process_snapshot(live_path,live_ts)
    except Exception: pass
live_candidates=candidates(live_df); lc=counts(live_candidates)
if live_candidates.empty: st.info("No currently qualified live decision candidates.")
else:
    st.caption(f"Current evidence bundle: **{live_ts.strftime('%d %b %Y, %H:%M:%S')}**")
    styled_queue(filter_queue(live_candidates,"sdl_live_filter"))
st.markdown('</div>',unsafe_allow_html=True)


# ---------- top priority ----------
st.markdown('<div class="card">',unsafe_allow_html=True)
st.markdown('<div class="card-title">2. TOP PRIORITY NOW</div>',unsafe_allow_html=True)
st.markdown(f'<div class="card-subtitle">Ranked strongest current opportunities · Snapshot: {live_ts.strftime("%d %b %Y, %H:%M:%S") if pd.notna(live_ts) else "—"}</div>',unsafe_allow_html=True)
if live_candidates.empty: st.info("No priority candidate at the current live snapshot.")
else:
    priority=live_candidates.sort_values(["factual_breakout","strength","progress"],ascending=[False,False,False]).head(10)
    styled_queue(priority)
st.markdown('</div>',unsafe_allow_html=True)


# ---------- compact state ----------
st.markdown('<div class="card">',unsafe_allow_html=True)
st.markdown('<div class="card-title">3. CURRENT DECISION STATE</div>',unsafe_allow_html=True)
items=[("CANDIDATES",len(live_candidates)),("BULLISH",lc["bull"]),("BEARISH",lc["bear"]),("STRONG",lc["strong"]),("DEVELOPING",lc["dev"]),("WAIT",lc["wait"]),("BREAKOUT",lc["break"]),("AS OF",live_ts.strftime("%H:%M:%S") if pd.notna(live_ts) else "—")]
cols=st.columns(8)
for col,(label,value) in zip(cols,items):
    with col: st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>',unsafe_allow_html=True)
st.markdown('</div>',unsafe_allow_html=True)


# ---------- replay ----------
st.markdown('<div class="card">',unsafe_allow_html=True)
st.markdown('<div class="card-title">4. REPLAY / SNAPSHOT CHECK</div>',unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">Manual historical investigation. Day → time → replay. No source filename is exposed.</div>',unsafe_allow_html=True)

all_files=source_files()
dates=sorted({source_ts(p).date().isoformat() for p in all_files if pd.notna(source_ts(p))},reverse=True)
if dates:
    current_date=pd.Timestamp(st.session_state.get("sdl_replay_date",dates[0]))
    rdate=st.date_input("Trading day",value=current_date.date(),min_value=min(pd.Timestamp(d).date() for d in dates),max_value=max(pd.Timestamp(d).date() for d in dates),key="sdl_replay_calendar")
    rdate_iso=rdate.isoformat()
    rfiles=source_files(rdate_iso)
    if rfiles:
        times=[source_ts(p) for p in rfiles]
        labels=[t.strftime("%H:%M:%S") for t in times]
        idx=0
        prev=st.session_state.get("sdl_replay_selected_time")
        if prev in labels: idx=labels.index(prev)
        selected_label=st.selectbox("Snapshot time",labels,index=idx,key="sdl_replay_time")
        selected=rfiles[labels.index(selected_label)]
        if st.button("Replay selected snapshot",type="primary"):
            started=time.perf_counter()
            try:
                with st.status(f"Preparing replay {rdate.strftime('%d %b %Y')}…",expanded=True) as status:
                    if st.session_state.get("sdl_replay_prepared_date") != rdate_iso:
                        status.write("Rebuilding the selected trading day once…")
                        replay_trading_date(rdate_iso)
                        st.session_state["sdl_replay_prepared_date"]=rdate_iso
                    status.write(f"Loading snapshot {selected_label}…")
                    _,replay_df,replay_ts=process_snapshot(selected,source_ts(selected))
                    st.session_state["sdl_replay_df"]=replay_df
                    st.session_state["sdl_replay_timestamp"]=source_ts(selected)
                    st.session_state["sdl_replay_selected_time"]=selected_label
                    status.update(label=f"Replay ready · {selected_label} · {time.perf_counter()-started:.1f}s",state="complete",expanded=False)
                st.rerun()
            except Exception as exc:
                st.error(f"Replay failed: {exc}")
    else: st.info("No source snapshots available for this day.")
else: st.info("No source snapshots available.")

if st.session_state.get("sdl_replay_timestamp"):
    rts=pd.to_datetime(st.session_state["sdl_replay_timestamp"])
    st.markdown(f'<span class="replay-pill">REPLAY · {rts.strftime("%d %b %Y · %H:%M:%S")}</span>',unsafe_allow_html=True)
    rdf=st.session_state.get("sdl_replay_df",pd.DataFrame())
    rc=candidates(rdf)
    if not rc.empty: styled_queue(filter_queue(rc,"sdl_replay_filter"))
    else: st.info("No qualified candidates at the selected replay snapshot.")
st.markdown('</div>',unsafe_allow_html=True)


# ---------- inspector, intentionally collapsed ----------
with st.expander("5. DECISION INSPECTOR · tap to inspect",expanded=False):
    st.caption("Detailed evidence and interpretation for the selected decision. Does not change selection.")
    inspect=live_candidates
    if st.session_state.get("sdl_replay_timestamp") and not st.session_state.get("sdl_replay_df",pd.DataFrame()).empty:
        inspect=candidates(st.session_state["sdl_replay_df"])
    if inspect.empty: st.info("No candidate available.")
    else:
        sym=st.selectbox("Stock",inspect.symbol.tolist(),key="sdl_inspect")
        row=inspect[inspect.symbol.eq(sym)].iloc[0]
        css=decision_class(row)
        st.markdown(f'<div class="card {css}"><div style="font-size:17px;font-weight:800">{row.decision}</div><div style="font-size:10px;margin-top:4px">Progress {row.progress:.1f}% of frozen S · Price {row.signed_price_move_pct:+.2f}% · Frozen S ₹{row.frozen_straddle:.2f}</div></div>',unsafe_allow_html=True)
        a,b,c,d,e=st.columns(5)
        a.metric("Open",f"{row.opening_price:.2f}"); b.metric("Current",f"{row.current_price:.2f}"); c.metric("Frozen S",f"{row.frozen_straddle:.2f}"); d.metric("Upper",f"{row.upper_breakout:.2f}"); e.metric("Lower",f"{row.lower_breakout:.2f}")
        factors=[{"FACTOR":f.label,"STATE":f.state,"WEIGHT":f.weight} for f in row.factors]
        st.dataframe(pd.DataFrame(factors),width="stretch",hide_index=True)


# ---------- historical evidence, intentionally collapsed ----------
with st.expander("6. HISTORICAL EVIDENCE · factual audit",expanded=False):
    st.caption("Factual first-breakout history only. It does not create the current decision.")
    events=load_events(EVENT_CSV)
    historical_table(events,rdate_iso if 'rdate_iso' in locals() else today)

st.markdown('<div class="small-note">Frozen decision logic is unchanged: ±0.75% primary price gate → 25/50/75/100% of frozen opening straddle → secondary confirmation → strength priority. Source files remain read-only.</div>',unsafe_allow_html=True)
