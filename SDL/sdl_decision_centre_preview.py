
from __future__ import annotations

from pathlib import Path
import html
import time

import pandas as pd
import streamlit as st

import config as sdl_config
import pipeline as sdl_pipeline
from config import EVENT_CSV
from pipeline import discover_historical_snapshots, process_snapshot, replay_trading_date
from prediction_engine import build_current_predictions, factor_labels
from source_loader import parse_observation_timestamp
from storage import load_events

st.set_page_config(
    page_title="NTIS SDL — Intraday Decision Centre",
    page_icon="SDL",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================================
# FINAL APPROVED DECISION CENTRE — PRESENTATION LAYER ONLY
# Existing SDL qualification/scoring/replay pipeline remains the source of
# truth. This file changes presentation/navigation only.
# ============================================================================

st.markdown(
    """
<style>
:root{
  --navy:#061a45; --navy2:#0b2c67; --ink:#17233f; --muted:#68758d;
  --page:#f4f7fb; --card:#fff; --line:#dce4ef; --soft:#f8faff;
  --green:#0a9b52; --green-bg:#edf9f2; --green-line:#bfe8d0;
  --red:#e0444e; --red-bg:#fff1f2; --red-line:#f2c5ca;
  --amber:#b77800; --amber-bg:#fff7e5; --amber-line:#efd8a0;
  --purple:#4d22e8; --purple2:#6b43ff; --blue:#2e5de7;
}
.stApp{background:var(--page);color:var(--ink)}
.block-container{max-width:1680px;padding:0 16px 24px}
header[data-testid="stHeader"]{background:#fff0}
[data-testid="stSidebar"]{display:none}
div[data-testid="stToolbar"]{z-index:999}
.appnav{
  margin:0 -16px 14px;
  padding:12px 18px;
  min-height:58px;
  background:linear-gradient(110deg,#06173d,#071d4e 62%,#0b2c68);
  color:#fff;
  display:flex;align-items:center;justify-content:space-between;
  box-shadow:0 3px 12px rgba(6,26,69,.18)
}
.brand{display:flex;align-items:center;gap:10px;min-width:310px}
.brandmark{
  width:31px;height:31px;border-radius:50%;background:#fff;color:#09245b;
  display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:950
}
.brandname{font-size:21px;font-weight:900;letter-spacing:.01em}
.brandsep{height:24px;width:1px;background:rgba(255,255,255,.35);margin:0 2px}
.brandsub{font-size:12px;font-weight:800;letter-spacing:.05em;opacity:.94}
.navlinks{display:flex;align-items:center;gap:6px;flex:1;margin-left:22px}
.navitem{
  padding:9px 13px;border-radius:6px;font-size:11px;font-weight:850;
  color:#fff;opacity:.92;white-space:nowrap
}
.navitem.active{background:linear-gradient(110deg,#5930ef,#4320d6);box-shadow:0 3px 12px rgba(72,36,231,.35)}
.navright{display:flex;align-items:center;gap:9px;font-size:10px}
.livepill{padding:7px 12px;border:1px solid rgba(70,116,183,.35);border-radius:6px;font-weight:900;color:#31e47f}
.clockbox{border-left:1px solid rgba(255,255,255,.18);padding-left:12px;text-align:right;line-height:1.2}
.clockbox b{font-size:15px}
.refreshbtn{
  border:1px solid rgba(255,255,255,.25);border-radius:6px;padding:7px 10px;
  color:#fff;background:rgba(255,255,255,.05);font-weight:800
}
.autopill{padding:7px 9px;border:1px solid rgba(255,255,255,.18);border-radius:6px;white-space:nowrap}
.kpis{
  background:#fff;border:1px solid var(--line);border-radius:8px;
  box-shadow:0 2px 10px rgba(30,50,85,.06);display:grid;grid-template-columns:repeat(6,1fr);
  margin-bottom:14px
}
.kpi{padding:14px 28px;border-right:1px solid #edf0f5;min-height:72px}
.kpi:last-child{border-right:0}
.kpilabel{font-size:9px;font-weight:900;letter-spacing:.07em;color:#2e436b}
.kpivalue{font-size:21px;font-weight:900;margin-top:5px}
.kpifoot{font-size:9px;color:#7a879b;margin-top:2px}
.filterbar{
  background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 12px;
  margin-bottom:14px;box-shadow:0 2px 8px rgba(30,50,85,.035)
}
.filtergrid{display:grid;grid-template-columns:1.08fr .9fr 1.08fr 1.62fr;gap:16px;align-items:end}
.filtergroup{min-width:0}
.filtertitle{font-size:9px;font-weight:900;color:#2f4c7e;letter-spacing:.07em;margin-bottom:5px}
.filterrow{display:flex;gap:5px;flex-wrap:wrap}
.pill{
  display:inline-flex;align-items:center;gap:6px;border:1px solid #d8e0eb;
  background:#fff;border-radius:18px;padding:6px 10px;font-size:10px;font-weight:800;
  color:#24324d;white-space:nowrap
}
.pill.on{border-color:#aabfff;background:#f1f4ff;color:#2c55d7}
.dot{width:13px;height:13px;border-radius:50%;border:1px solid #d4dbe6;background:#fff}
.pill.on .dot{border:4px solid #ff4b55}
.reset{float:right;font-size:10px;color:#4b38e6;font-weight:900;border:1px solid #a99cff;padding:6px 9px;border-radius:6px}
.radar{
  background:linear-gradient(105deg,#061a45,#102f6d);border-radius:9px;
  padding:11px 12px;margin-bottom:8px;color:#fff
}
.radar-title{font-size:9px;letter-spacing:.11em;font-weight:900;opacity:.86}
.radar-filters{display:flex;justify-content:space-between;align-items:center;margin:9px 0 6px}
.radar-cards{display:flex;gap:9px;overflow:hidden}
.radar-card{
  min-width:175px;background:#fff;color:#18243e;border-radius:7px;padding:8px 10px;
  border:1px solid #e0e6ef
}
.radar-symbol{font-size:10px;font-weight:900}
.radar-meta{font-size:8px;color:#6f7b8f;margin-top:4px}
.radar-progress{font-size:14px;font-weight:950;margin-top:5px}
.main-grid{display:grid;grid-template-columns:minmax(0,3.5fr) minmax(300px,1.25fr);gap:12px;align-items:start}
.tablecard,.detailcard{
  background:#fff;border:1px solid var(--line);border-radius:8px;overflow:hidden;
  box-shadow:0 2px 9px rgba(30,50,85,.035)
}
.tablehead{padding:9px 11px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}
.tabletitle{font-size:11px;font-weight:900;letter-spacing:.04em}
.tablesub{font-size:9px;color:#7a879b}
table.queue{width:100%;border-collapse:collapse;table-layout:fixed}
.queue th{
  background:#fbfcfe;color:#41516d;text-align:left;font-size:8px;letter-spacing:.07em;
  font-weight:900;padding:9px 7px;border-bottom:1px solid var(--line);white-space:nowrap
}
.queue td{
  padding:9px 7px;border-bottom:1px solid #edf1f6;font-size:10px;font-weight:750;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;height:49px
}
.queue tr.selected{background:#fbfffd;outline:1px solid #7ac79d;outline-offset:-1px}
.qno{color:#7b8799}
.stock{display:flex;align-items:center;gap:7px;font-weight:950;font-size:11px}
.logo{
  width:25px;height:25px;border:1px solid #dfe5ee;border-radius:6px;background:#fff;
  display:inline-flex;align-items:center;justify-content:center;font-size:7px;color:#1d3c78;
  overflow:hidden;flex:0 0 25px
}
.dirup{color:var(--green);font-weight:900}.dirdown{color:var(--red);font-weight:900}
.badge{
  display:inline-block;border:1px solid #bfe5d0;background:#f0fbf5;color:#087d42;
  border-radius:4px;padding:5px 7px;font-size:8px;font-weight:900
}
.badge.red{border-color:#f2c7cb;background:#fff2f3;color:#d13742}
.badge.amber{border-color:#efd9a2;background:#fff7e7;color:#a86c00}
.barwrap{display:flex;align-items:center;gap:6px}.bar{
  width:68px;height:6px;background:#e3e8f0;border-radius:6px;overflow:hidden
}.bar>i{display:block;height:100%;background:#0a9b52;border-radius:6px}
.stage{
  display:inline-block;border:1px solid #d9e0ea;background:#f7f9fc;border-radius:12px;
  padding:4px 7px;font-size:8px;font-weight:850
}
.confirm{
  display:inline-block;border:1px solid #bdcaff;background:#f0f3ff;color:#385bd3;
  border-radius:5px;padding:4px 7px;font-size:8px;font-weight:900
}
.strength{color:#07934b;font-weight:950}.strengthmid{color:#6a49db;font-weight:900}
.breakyes{color:#07934b;font-weight:950}.breakno{color:#778399}
.time{font-variant-numeric:tabular-nums;font-weight:850}
.detailcard{padding:0}
.detailtop{padding:12px 14px;border-bottom:1px solid var(--line)}
.detailstock{display:flex;justify-content:space-between;align-items:flex-start}
.detailname{font-size:16px;font-weight:950}.detailicons{color:#6d7890;font-size:17px}
.detaildecision{font-size:12px;font-weight:950;margin-top:10px}.detaildecision.up{color:#07934b}.detaildecision.down{color:#d43b45}
.detailstage{float:right;border:1px solid #d9e0ea;background:#f7f9fc;border-radius:13px;padding:5px 8px;font-size:8px;font-weight:900}
.detailprogress{padding:10px 14px;border-bottom:1px solid var(--line)}
.dplabel{font-size:9px;color:#68768d;font-weight:800}.dpvalue{font-size:21px;color:#07934b;font-weight:950}
.dpline{height:7px;background:#e3e8f0;border-radius:7px;margin-top:5px}.dpline i{display:block;height:100%;background:#07934b;border-radius:7px}
.detailmetrics{display:grid;grid-template-columns:repeat(3,1fr);margin:0 14px;border:1px solid #e5eaf1;border-radius:6px;overflow:hidden}
.dm{padding:9px;border-right:1px solid #e5eaf1}.dm:last-child{border-right:0}
.dml{font-size:8px;color:#718096}.dmv{font-size:13px;font-weight:900;margin-top:3px}.green{color:#07934b}.purple{color:#5b3bd6}
.detailsection{margin:10px 14px;border:1px solid #e5eaf1;border-radius:6px;padding:9px}
.sectiontitle{font-size:8px;color:#65738b;font-weight:900;letter-spacing:.08em;margin-bottom:7px}
.factrow{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #eef1f5;font-size:8px}.factrow:last-child{border-bottom:0}
.interpret{font-size:9px;color:#4b5870;line-height:1.55}
.pagination{
  display:flex;align-items:center;justify-content:space-between;padding:8px 11px;
  font-size:8px;color:#7a879b;border-top:1px solid var(--line)
}
.pagebtn{border:1px solid #d8dfeb;border-radius:5px;padding:4px 7px;background:#fff}
.pagebtn.on{background:#4c24e8;color:#fff;border-color:#4c24e8}
.footer{font-size:8px;color:#7b8798;margin-top:10px;padding:8px 2px;border-top:1px solid var(--line)}
@media(max-width:1100px){
  .navlinks{display:none}.brand{min-width:auto}.navright .autopill{display:none}
  .kpis{grid-template-columns:repeat(3,1fr)}.filtergrid{grid-template-columns:1fr 1fr}
  .main-grid{grid-template-columns:1fr}.detailcard{position:static}
}
@media(max-width:700px){
  .block-container{padding:0 8px 18px}.appnav{margin:0 -8px 10px;padding:10px}.brandname{font-size:18px}
  .brandsub{display:none}.kpis{grid-template-columns:repeat(2,1fr)}.kpi{padding:10px 14px}
  .filtergrid{grid-template-columns:1fr}.radar-cards{overflow-x:auto}.tablecard{overflow-x:auto}
  table.queue{min-width:930px}.detailcard{width:100%}
}
</style>
""",
    unsafe_allow_html=True,
)


def ts(path):
    try:
        return parse_observation_timestamp(path)
    except Exception:
        try:
            return pd.Timestamp.fromtimestamp(Path(path).stat().st_mtime)
        except Exception:
            return pd.NaT


def files(day=None):
    try:
        found = [Path(p) for p in discover_historical_snapshots(day)]
    except Exception:
        return []
    pairs = [(p, ts(p)) for p in found if pd.notna(ts(p))]
    return [p for p, _ in sorted(pairs, key=lambda z: (z[1], str(z[0]).lower()))]


def frozen_base(df):
    if df.empty or "Symbol" not in df.columns:
        return {}
    result = {}
    for _, row in df.drop_duplicates("Symbol").iterrows():
        symbol = str(row.get("Symbol", "")).strip().upper()
        open_price = pd.to_numeric(row.get("daily_open_reference"), errors="coerce")
        premium = pd.to_numeric(row.get("opening_straddle_premium"), errors="coerce")
        if symbol and pd.notna(open_price) and pd.notna(premium) and premium > 0:
            result[symbol] = {"open_price": float(open_price), "opening_straddle_premium": float(premium)}
    return result


def candidates(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return build_current_predictions(df, frozen_base(df))


def first_seen(row):
    for key in ("first_seen_timestamp","first_detection_timestamp","trigger_timestamp","decision_timestamp","observation_timestamp"):
        value = pd.to_datetime(row.get(key), errors="coerce")
        if pd.notna(value):
            return value
    return pd.NaT


def time_text(value, date=False):
    x = pd.to_datetime(value, errors="coerce")
    if pd.isna(x):
        return "—"
    return x.strftime("%d %b %Y, %H:%M:%S" if date else "%H:%M:%S")


def pct(value):
    x = pd.to_numeric(value, errors="coerce")
    return "—" if pd.isna(x) else f"{float(x):+.2f}%"


def esc(v):
    return html.escape(str(v))


def logo(symbol):
    s = str(symbol).upper().strip()
    if not s or s == "NAN":
        return '<span class="logo">—</span>'
    return f'<span class="logo">{esc(s[:4])}</span>'


def filtered(df, progress, direction, strength, stage):
    out = df.copy()
    if direction != "All":
        out = out[out.direction_label.astype(str).str.upper().eq(direction.upper())]
    if strength != "All":
        out = out[out.strength_label.astype(str).str.upper().eq(strength.upper())]
    if stage != "All":
        out = out[out.stage.astype(str).eq(stage)]
    pv = pd.to_numeric(out.get("progress", pd.Series(index=out.index)), errors="coerce").fillna(-1)
    if progress == "25%+": out = out[pv >= 25]
    elif progress == "50%+": out = out[pv >= 50]
    elif progress == "70%+": out = out[pv >= 70]
    elif progress == "75%+": out = out[pv >= 75]
    elif progress == "Breakout": out = out[out.factual_breakout.astype(bool)]
    return out


def run_live(path, stamp):
    if path is None:
        return pd.DataFrame()
    try:
        result = process_snapshot(path, stamp)
        frames = [x for x in result if isinstance(x, pd.DataFrame)] if isinstance(result, tuple) else [result]
        df = frames[1] if len(frames) > 1 else (frames[0] if frames else pd.DataFrame())
        return candidates(df)
    except Exception:
        return pd.DataFrame()


def radio_pills(label, options, current, key):
    # Native radio keeps state/accessibility; CSS makes it match approved pills.
    return st.radio(label, options, index=options.index(current), horizontal=True, key=key, label_visibility="collapsed")


def filter_panel(df):
    progress = radio_pills("Progress", ["All","25%+","50%+","70%+","75%+","Breakout"], "All", "approved_progress")
    direction = radio_pills("Decision direction", ["All","Bullish","Bearish"], "All", "approved_direction")
    strengths = ["All"] + sorted({str(x).title() for x in df.get("strength_label", pd.Series(dtype=str)).dropna()})
    strength = radio_pills("Strength", strengths, "All", "approved_strength")
    stages = ["All"] + sorted({str(x) for x in df.get("stage", pd.Series(dtype=str)).dropna() if str(x).strip() and str(x).lower() != "nan"})
    stage = radio_pills("Stage", stages, "All", "approved_stage")
    return progress, direction, strength, stage


def priority(df):
    pprogress = radio_pills("Priority progress", ["All","25%+","50%+","70%+","75%+","Breakout"], "All", "priority_progress")
    pstrength = radio_pills("Priority strength", ["All","Strong","Developing"], "All", "priority_strength")
    top = filtered(df, pprogress, "All", pstrength, "All")
    top = top.sort_values(["factual_breakout","strength","progress"], ascending=[False,False,False]).head(5)
    cards = []
    for _, r in top.iterrows():
        prog = float(pd.to_numeric(r.get("progress"), errors="coerce") or 0)
        cards.append(
            f'<div class="radar-card"><div class="radar-symbol">{logo(r.get("symbol"))} {esc(str(r.get("symbol")).upper())}</div>'
            f'<div class="radar-meta">{esc(str(r.get("direction_label","—")).title())} · {esc(str(r.get("strength_label","—")).title())} · {esc(str(r.get("stage","—")))}</div>'
            f'<div class="radar-progress">{prog:.1f}%{" · BREAKOUT" if bool(r.get("factual_breakout",False)) else ""}</div></div>'
        )
    return "".join(cards)


def queue_html(df, selected):
    rows = []
    for i, (_, r) in enumerate(df.iterrows(), 1):
        symbol = str(r.get("symbol","")).upper()
        direction = str(r.get("direction_label","—")).upper()
        strength_label = str(r.get("strength_label","—")).upper()
        price = pd.to_numeric(r.get("signed_price_move_pct"), errors="coerce")
        progress = float(pd.to_numeric(r.get("progress"), errors="coerce") or 0)
        strength = pd.to_numeric(r.get("strength"), errors="coerce")
        stage = str(r.get("stage","—"))
        confirmation = str(r.get("confirmation", r.get("confirmation_label","STRONG")))
        breakout = bool(r.get("factual_breakout",False))
        pcls = "dirup" if pd.notna(price) and price > 0 else "dirdown" if pd.notna(price) and price < 0 else ""
        bcls = "badge" if direction == "BULLISH" else "badge red" if direction == "BEARISH" else "badge amber"
        scl = "strength" if strength_label == "STRONG" else "strengthmid"
        sel = " selected" if symbol == selected else ""
        rows.append(
            f'<tr class="{sel}" data-symbol="{esc(symbol)}">'
            f'<td class="qno">{i}</td><td><div class="stock">{logo(symbol)}{esc(symbol)}</div></td>'
            f'<td><span class="{bcls}">{esc(direction.title())} · {esc(strength_label.title())}</span></td>'
            f'<td class="{pcls}">{pct(price)}</td>'
            f'<td><div class="barwrap"><b>{progress:.1f}%</b><span class="bar"><i style="width:{min(max(progress,0),100):.0f}%"></i></span></div></td>'
            f'<td><span class="stage">{esc(stage)}</span></td><td><span class="confirm">{esc(confirmation)}</span></td>'
            f'<td class="{scl}">{("—" if pd.isna(strength) else f"{float(strength):.0f}")}</td>'
            f'<td class="{"breakyes" if breakout else "breakno"}">{"YES" if breakout else "—"}</td>'
            f'<td class="time">{time_text(r.get("observation_timestamp"))}</td></tr>'
        )
    if not rows:
        return '<div style="padding:24px;text-align:center;color:#778399;font-size:11px">No stocks match the current filters.</div>'
    return (
        '<table class="queue"><thead><tr>'
        '<th style="width:4%">#</th><th style="width:15%">STOCK</th><th style="width:18%">DIRECTION</th>'
        '<th style="width:10%">MOMENTUM</th><th style="width:16%">STRADDLE PROGRESS</th><th style="width:13%">STAGE</th>'
        '<th style="width:11%">CONFIRMATION</th><th style="width:7%">STRENGTH</th><th style="width:6%">BREAKOUT</th><th style="width:8%">TIME</th>'
        '</tr></thead><tbody>' + "".join(rows) + "</tbody></table>"
    )


def detail(df, selected):
    if df.empty:
        return
    r = df[df.symbol.astype(str).str.upper().eq(selected)].iloc[0]
    direction = str(r.get("direction_label","—")).upper()
    strength_label = str(r.get("strength_label","—")).upper()
    stage = str(r.get("stage","—"))
    progress = float(pd.to_numeric(r.get("progress"), errors="coerce") or 0)
    momentum = pd.to_numeric(r.get("signed_price_move_pct"), errors="coerce")
    strength = pd.to_numeric(r.get("strength"), errors="coerce")
    confirmation = str(r.get("confirmation", r.get("confirmation_label","STRONG")))
    breakout = bool(r.get("factual_breakout",False))
    updated = r.get("observation_timestamp")
    first = first_seen(r)
    dcls = "up" if direction == "BULLISH" else "down"
    facts = []
    for f in r.get("factors", []) or []:
        state = str(getattr(f,"state",""))
        facts.append(f'<div class="factrow"><span>{esc(getattr(f,"label","Factor"))}</span><b class="{"green" if state=="SUPPORT" else "purple" if state=="NEUTRAL" else "dirdown"}">{esc(state)}</b></div>')
    interpretation = (
        "Price holding with strong directional momentum and confirmation."
        if direction == "BULLISH" else
        "Price weakening with bearish directional momentum and confirmation."
        if direction == "BEARISH" else
        "Developing setup; confirmation should be reviewed before action."
    )
    st.markdown(
        f'<div class="detailtop"><div class="detailstock"><div><div class="detailname">{logo(selected)} {esc(selected)}</div>'
        f'<div class="detaildecision {dcls}">{esc(direction.title())} · {esc(strength_label.title())}</div></div>'
        f'<div class="detailicons">☆　×</div></div>'
        f'<span class="detailstage">STAGE&nbsp; {esc(stage)}</span></div>'
        f'<div style="font-size:8px;color:#7a879b;margin-top:7px">First seen: <b>{time_text(first,True)}</b> · Updated: <b>{time_text(updated,True)}</b></div></div>'
        f'<div class="detailprogress"><div class="dplabel">STRADDLE PROGRESS</div><div class="dpvalue">{progress:.1f}%</div>'
        f'<div class="dpline"><i style="width:{min(max(progress,0),100):.0f}%"></i></div></div>'
        f'<div class="detailmetrics"><div class="dm"><div class="dml">MOMENTUM</div><div class="dmv green">{pct(momentum)}</div></div>'
        f'<div class="dm"><div class="dml">STRENGTH</div><div class="dmv green">{"—" if pd.isna(strength) else f"{float(strength):.0f}"} <small>/100</small></div></div>'
        f'<div class="dm"><div class="dml">CONFIRMATION</div><div class="dmv purple">{esc(confirmation)}</div></div></div>'
        f'<div class="detailsection"><div class="sectiontitle">DECISION EVIDENCE</div>{ "".join(facts) if facts else "<div class=\"interpret\">Existing confirmation factors retained.</div>" }</div>'
        f'<div class="detailsection"><div class="sectiontitle">INTERPRETATION</div><div class="interpret">{interpretation}</div></div>'
        f'<div class="detailsection"><div class="sectiontitle">NEXT LEVEL</div><div style="font-size:13px;font-weight:950">{ "BREAKOUT" if breakout else "75%" }</div>'
        f'<div style="font-size:8px;color:#7a879b;margin-top:3px">Decision time {time_text(updated,True)}</div></div>',
        unsafe_allow_html=True,
    )


def metrics(df, stamp):
    vals = [
        ("QUALIFIED STOCKS", len(df), "Live Universe"),
        ("STRONG", int(df.strength_label.eq("STRONG").sum()) if not df.empty else 0, f"{(int(df.strength_label.eq('STRONG').sum())/len(df)*100 if len(df) else 0):.1f}% of universe"),
        ("ABOVE 50%", int((pd.to_numeric(df.progress,errors='coerce')>=50).sum()) if not df.empty else 0, "50%+ Progress"),
        ("APPROACHING 75%+", int((pd.to_numeric(df.progress,errors='coerce')>=75).sum()) if not df.empty else 0, "Near Next Level"),
        ("BREAKOUT", int(df.factual_breakout.sum()) if not df.empty else 0, "100% Breakout"),
        ("DATA UPDATED", time_text(stamp), time_text(stamp, True).split(", ",1)[0] if pd.notna(pd.to_datetime(stamp,errors="coerce")) else "—"),
    ]
    st.markdown('<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="kpilabel">{esc(a)}</div><div class="kpivalue">{esc(b)}</div><div class="kpifoot">{esc(c)}</div></div>'
        for a,b,c in vals
    ) + "</div>", unsafe_allow_html=True)


def top_nav(page, live_ts):
    st.markdown(
        f'<div class="appnav"><div class="brand"><div class="brandmark">◈</div><div class="brandname">NTIS SDL</div>'
        f'<div class="brandsep"></div><div class="brandsub">INTRADAY DECISION CENTRE</div></div>'
        f'<div class="navlinks"><div class="navitem {"active" if page=="Decision Board" else ""}">▣　DECISION BOARD</div>'
        f'<div class="navitem {"active" if page=="Replay" else ""}">◷　REPLAY</div>'
        f'<div class="navitem {"active" if page=="Historical Evidence" else ""}">▤　HISTORICAL EVIDENCE</div>'
        f'<div class="navitem {"active" if page=="Settings" else ""}">⚙　SETTINGS</div></div>'
        f'<div class="navright"><span class="livepill">LIVE ●</span><div class="clockbox"><b>{time_text(live_ts)}</b><br>{time_text(live_ts,True).split(", ",1)[0] if pd.notna(pd.to_datetime(live_ts,errors="coerce")) else ""}</div>'
        f'<span class="refreshbtn">⟳ Refresh</span><span class="autopill">● Auto Refresh　10s⌄</span></div></div>',
        unsafe_allow_html=True,
    )


today = pd.Timestamp.now().date().isoformat()
today_files = files(today)
live_path = max(today_files, key=ts) if today_files else None
live_ts = ts(live_path) if live_path else pd.NaT
live = run_live(live_path, live_ts)

# Use a compact control row for navigation; query-param navigation is not used so
# the existing decision engine remains untouched.
page = st.session_state.get("approved_page", "Decision Board")
top_nav(page, live_ts)

if page == "Decision Board":
    metrics(live, live_ts)
    progress, direction, strength, stage = filter_panel(live)
    visible = filtered(live, progress, direction, strength, stage)

    st.markdown('<div class="radar"><div class="radar-title">PRIORITY RADAR · INDEPENDENT FILTER</div></div>', unsafe_allow_html=True)
    # Priority controls use a separate state space from Live Queue.
    priority_cards = priority(live)
    st.markdown(f'<div class="radar-cards">{priority_cards}</div></div>', unsafe_allow_html=True)

    symbols = [str(x).upper() for x in visible.symbol.dropna().tolist()] if not visible.empty else []
    selected = st.session_state.get("selected_symbol")
    if selected not in symbols:
        selected = symbols[0] if symbols else ""

    # Streamlit selectbox is deliberately compact and hidden visually; it is the
    # reliable selection mechanism while the table remains the trader-facing view.
    if symbols:
        selected = st.selectbox("Stock selection", symbols, index=symbols.index(selected), key="selected_symbol", label_visibility="collapsed")

    left, right = st.columns([3.55, 1.25], gap="small")
    with left:
        st.markdown(
            f'<div class="tablecard"><div class="tablehead"><div><div class="tabletitle">LIVE DECISION QUEUE</div>'
            f'<div class="tablesub">{len(visible)} matching stock(s) · existing SDL decision records</div></div>'
            f'<div class="tablesub">Updated {time_text(live_ts)}</div></div>{queue_html(visible, selected)}'
            f'<div class="pagination"><span>Showing 1 to {len(visible)} of {len(visible)} stocks</span><span>‹　 <b class="pagebtn on">1</b>　›　 Items per page: 50</span></div></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="detailcard">', unsafe_allow_html=True)
        if symbols:
            detail(visible, selected)
        else:
            st.markdown('<div style="padding:20px;color:#778399;font-size:11px">No qualified stock available.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div class="footer">NTIS SDL · Intraday Straddle Breakout Decision Centre'
        f'<span style="float:right">First timestamp retained · Latest update {time_text(live_ts,True)} · Filters never change SDL decision logic</span></div>',
        unsafe_allow_html=True,
    )

elif page == "Replay":
    st.markdown('<div class="tablecard" style="padding:14px"><b>REPLAY</b><div style="font-size:10px;color:#748198;margin-top:4px">Trading day and exact snapshot timestamp.</div></div>', unsafe_allow_html=True)
    all_files = files()
    days = sorted({ts(p).date().isoformat() for p in all_files if pd.notna(ts(p))}, reverse=True)
    if days:
        day = st.date_input("Trading day", pd.Timestamp(days[0]).date(), key="replay_day")
        day_files = files(day.isoformat())
        labels = [ts(p).strftime("%H:%M:%S") for p in day_files]
        if labels:
            label = st.selectbox("Snapshot time", labels, key="replay_time")
            selected_path = day_files[labels.index(label)]
            if st.button("Replay selected snapshot", type="primary"):
                try:
                    replay_trading_date(day.isoformat())
                    _, replay_df, replay_ts = process_snapshot(selected_path, ts(selected_path))
                    st.session_state["replay_df"] = replay_df
                    st.session_state["replay_ts"] = replay_ts
                    st.rerun()
                except Exception as exc:
                    st.error(f"Replay failed: {exc}")
    replay_df = st.session_state.get("replay_df", pd.DataFrame())
    if isinstance(replay_df,pd.DataFrame) and not replay_df.empty:
        rp = candidates(replay_df)
        st.markdown(f'<div class="tablecard" style="margin-top:10px;padding:10px">Replay boundary: <b>{time_text(st.session_state.get("replay_ts"),True)}</b></div>', unsafe_allow_html=True)
        st.markdown(queue_html(rp, ""), unsafe_allow_html=True)
    else:
        st.info("Select a trading day and snapshot time, then load Replay.")

elif page == "Historical Evidence":
    st.markdown('<div class="tablecard" style="padding:14px"><b>HISTORICAL EVIDENCE</b><div style="font-size:10px;color:#748198;margin-top:4px">Factual historical evidence only.</div></div>', unsafe_allow_html=True)
    events = load_events(EVENT_CSV)
    if events is None or events.empty:
        st.info("No historical evidence records available.")
    else:
        e = events.copy()
        if "observation_timestamp" in e.columns:
            e["observation_timestamp"] = pd.to_datetime(e["observation_timestamp"], errors="coerce")
            e = e.sort_values("observation_timestamp", ascending=False)
        st.dataframe(e, width="stretch", hide_index=True)

elif page == "Settings":
    st.markdown('<div class="tablecard" style="padding:14px"><b>SETTINGS</b></div>', unsafe_allow_html=True)
    root = st.text_input("Active source data folder", str(getattr(sdl_pipeline, "INTRADAY_SOURCE_ROOT", "")))
    if st.button("Apply source folder", type="primary"):
        source_path = Path(root).expanduser().resolve()
        sdl_pipeline.INTRADAY_SOURCE_ROOT = source_path
        sdl_config.INTRADAY_SOURCE_ROOT = source_path
        st.success("Source folder applied for this SDL application session.")

else:
    st.info("Use the Decision Board for live decisions.")

# Minimal navigation controls at the bottom preserve the final compact top layout.
with st.expander("Navigation", expanded=False):
    choice = st.radio("Page", ["Decision Board","Replay","Historical Evidence","Settings"], index=["Decision Board","Replay","Historical Evidence","Settings"].index(page), horizontal=True, label_visibility="collapsed")
    if choice != page:
        st.session_state["approved_page"] = choice
        st.rerun()
