from __future__ import annotations

from pathlib import Path
from datetime import datetime
import html

import pandas as pd
import streamlit as st

import config as sdl_config
import pipeline as sdl_pipeline
from config import EVENT_CSV
from pipeline import discover_historical_snapshots, process_snapshot, replay_trading_date
from prediction_engine import build_current_predictions, factor_labels
from source_loader import parse_observation_timestamp
from storage import load_events

PORT = 8587

st.set_page_config(
    page_title="NTIS SDL — Intraday Decision Centre",
    page_icon="SDL",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# APPROVED DASHBOARD VISUAL SYSTEM
# Presentation only. Existing SDL decision / scoring / replay engine is reused.
# -----------------------------------------------------------------------------
st.markdown(r"""
<style>
:root{
  --navy:#061333; --navy2:#10275c; --purple:#6737e8; --purple2:#7b4cff;
  --page:#f6f8fc; --card:#ffffff; --ink:#17233f; --muted:#68758d; --line:#dfe5ef;
  --green:#0b9a50; --green-bg:#eaf8f0; --green-line:#b9e4cb;
  --red:#d52d39; --red-bg:#fff0f1; --red-line:#f1c4c8;
  --amber:#d18a00; --amber-bg:#fff7e5; --amber-line:#eed59e;
  --blue:#355bd6; --blue-bg:#eef2ff; --blue-line:#ccd7ff;
}
.stApp{background:var(--page);color:var(--ink)}
.block-container{max-width:1660px;padding:0 16px 26px}
header[data-testid="stHeader"]{background:transparent}
footer{display:none}
div[data-testid="stToolbar"],div[data-testid="stDecoration"]{display:none}

/* Header / navigation */
.sdl-header{margin:0 -16px 14px;background:linear-gradient(105deg,#06102c 0%,#081942 62%,#12295e 100%);color:#fff;min-height:66px;padding:10px 18px;display:flex;align-items:center;justify-content:space-between;gap:18px;box-shadow:0 5px 18px rgba(5,17,47,.18)}
.sdl-brand{display:flex;align-items:center;gap:10px;min-width:0}
.sdl-logo{width:30px;height:30px;border-radius:50%;background:#fff;color:#12295e;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:950;flex:0 0 30px}
.sdl-name{font-size:22px;font-weight:950;letter-spacing:-.03em;white-space:nowrap}
.sdl-product{font-size:12px;font-weight:800;letter-spacing:.08em;border-left:1px solid rgba(255,255,255,.25);padding-left:12px;white-space:nowrap}
.sdl-nav{display:flex;align-items:center;gap:4px;flex:1;min-width:0}
.nav-label{font-size:11px;font-weight:850;letter-spacing:.02em;color:#fff;padding:9px 14px;border-radius:6px;white-space:nowrap}
.nav-label.active{background:linear-gradient(135deg,#5b2edb,#7446f4);box-shadow:0 3px 10px rgba(100,55,230,.35)}
.header-right{display:flex;align-items:center;gap:10px;white-space:nowrap}
.live-pill{border:1px solid #155d44;background:#082f24;color:#26d47c;border-radius:6px;padding:8px 12px;font-size:11px;font-weight:900}
.header-clock{font-variant-numeric:tabular-nums;text-align:right;line-height:1.1}.header-clock strong{font-size:15px}.header-clock small{font-size:9px;color:#c8d0e2}
.header-control{border:1px solid #435170;background:#0c1b3e;color:#fff;border-radius:6px;padding:8px 10px;font-size:10px;font-weight:850}

/* KPI strip */
.kpi-strip{background:#fff;border:1px solid var(--line);border-radius:9px;display:grid;grid-template-columns:repeat(6,1fr);box-shadow:0 2px 9px rgba(20,35,70,.035);margin-bottom:14px}
.kpi-item{padding:11px 15px;border-right:1px solid #e8ecf2;min-height:76px}.kpi-item:last-child{border-right:0}
.kpi-label{font-size:9px;color:#5b6880;font-weight:900;letter-spacing:.06em}.kpi-value{font-size:23px;font-weight:950;line-height:1.1;margin-top:5px}.kpi-foot{font-size:9px;color:#7c8799;margin-top:3px}.kpi-live{float:right;width:8px;height:8px;background:#14a75c;border-radius:50%;margin-top:4px;box-shadow:0 0 0 4px #e7f7ee}

/* Filter panel */
.filter-panel{background:#fff;border:1px solid var(--line);border-radius:9px;padding:10px 12px;margin-bottom:14px;box-shadow:0 2px 8px rgba(20,35,70,.025)}
.filter-grid{display:grid;grid-template-columns:1.45fr .8fr 1fr 1.7fr;gap:14px;align-items:start}
.filter-group{border-right:1px solid #edf0f4;padding-right:12px;min-width:0}.filter-group:last-child{border-right:0}
.filter-title{font-size:9px;font-weight:950;color:#31508b;letter-spacing:.06em;margin-bottom:6px}
div[data-testid="stRadio"] > label{display:none}
div[data-testid="stRadio"] div[role="radiogroup"]{display:flex;flex-wrap:wrap;gap:5px!important}
div[data-testid="stRadio"] div[role="radiogroup"] label{border:1px solid #d9e0eb!important;border-radius:999px!important;background:#fff!important;padding:5px 10px!important;margin:0!important;min-height:28px!important}
div[data-testid="stRadio"] div[role="radiogroup"] label p{font-size:10px!important;font-weight:800!important;color:#3f4b61!important;margin:0!important}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked){background:#eef2ff!important;border-color:#b7c7ff!important}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p{color:#1e4ec7!important}
.filter-reset button{height:30px!important;font-size:10px!important;border-radius:7px!important}

/* Priority radar */
.radar-head{background:linear-gradient(105deg,#071735,#112d64);color:#fff;border-radius:9px 9px 0 0;padding:9px 13px;display:flex;align-items:center;justify-content:space-between}
.radar-title{font-size:10px;font-weight:950;letter-spacing:.13em}.radar-sub{font-size:9px;color:#b8c6e2}
.radar-filters{background:#fff;border:1px solid var(--line);border-top:0;padding:8px 12px;border-radius:0 0 9px 9px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;gap:10px}
.radar-filters .filter-title{margin:0 4px 0 0;display:inline-block}

/* Main trading workspace */
.workspace{display:grid;grid-template-columns:minmax(0,3.55fr) minmax(320px,1.18fr);gap:12px;align-items:start}
.table-card{background:#fff;border:1px solid var(--line);border-radius:9px;overflow:hidden;box-shadow:0 2px 9px rgba(20,35,70,.035)}
.table-titlebar{padding:10px 13px;border-bottom:1px solid #e7ebf1;display:flex;justify-content:space-between;align-items:center}.table-title{font-size:13px;font-weight:950}.table-meta{font-size:9px;color:#748096}
.stock-table{width:100%;font-size:11px}
.stock-table thead th{background:#f8f9fc;color:#5e6b81;font-size:9px;letter-spacing:.05em;font-weight:950;padding:9px 7px;border-bottom:1px solid var(--line);text-align:left}
.stock-table tbody td{padding:10px 7px;border-bottom:1px solid #edf0f4;vertical-align:middle}
.stock-table tbody tr:hover{background:#fbfcff}
.logo-img{width:27px;height:27px;object-fit:contain;border:1px solid #dce3ed;border-radius:6px;background:#fff;padding:2px;vertical-align:middle;margin-right:6px}
.symbol-text{font-weight:900;color:#182540}
.badge{display:inline-block;border-radius:5px;padding:4px 7px;font-size:9px;font-weight:900;white-space:nowrap}.badge-bull{background:var(--green-bg);border:1px solid var(--green-line);color:#087b3e}.badge-bear{background:var(--red-bg);border:1px solid var(--red-line);color:#ad1d29}.badge-dev{background:var(--amber-bg);border:1px solid var(--amber-line);color:#9a6500}.badge-blue{background:var(--blue-bg);border:1px solid var(--blue-line);color:#3459d2}.badge-neutral{background:#f2f4f7;border:1px solid #dde2e9;color:#5d687b}
.momentum-up{color:#078c49;font-weight:900}.momentum-down{color:#d52d39;font-weight:900}
.progress-cell{display:flex;align-items:center;gap:7px}.progress-rail{width:75px;height:7px;background:#e3e8ef;border-radius:99px;overflow:hidden}.progress-fill{height:100%;border-radius:99px;background:#10a45b}.progress-fill.hot{background:#d18a00}.progress-fill.break{background:#0b9a50}
.stage-chip{font-size:9px;font-weight:850;border:1px solid #d9e0e9;border-radius:999px;padding:4px 7px;background:#f6f8fb;white-space:nowrap}
.strength-strong{color:#079448;font-weight:950}.strength-mid{color:#6e3cd6;font-weight:900}.strength-low{color:#68758b;font-weight:850}
.time-cell{font-variant-numeric:tabular-nums;font-weight:900;color:#273551}.break-yes{color:#079448;font-weight:950}.break-no{color:#8c96a7;font-weight:800}

/* Right selected-stock panel */
.detail-panel{background:#fff;border:1px solid var(--line);border-radius:9px;overflow:hidden;box-shadow:0 2px 9px rgba(20,35,70,.035);position:sticky;top:8px}
.detail-top{padding:12px 13px;border-bottom:1px solid #edf0f4;display:flex;align-items:center;justify-content:space-between;gap:10px}.detail-stock{display:flex;align-items:center;gap:8px}.detail-logo{width:34px;height:34px;object-fit:contain;border:1px solid #dce3ed;border-radius:7px;padding:2px}.detail-symbol{font-size:15px;font-weight:950}.detail-actions{color:#68758a;font-size:18px}
.detail-body{padding:12px 13px}.detail-decision{display:flex;justify-content:space-between;align-items:center;gap:8px}.detail-decision-text{font-size:14px;font-weight:950}.detail-progress-label{font-size:9px;color:#66738a;margin-top:12px}.detail-progress-value{font-size:23px;font-weight:950;color:#0a9a50}.detail-big-rail{height:7px;background:#e2e7ee;border-radius:99px;overflow:hidden;margin:6px 0 12px}.detail-big-fill{height:100%;background:#0a9a50;border-radius:99px}
.detail-metrics{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #e3e7ee;border-radius:7px;overflow:hidden;margin-bottom:10px}.detail-metric{padding:8px;border-right:1px solid #e3e7ee}.detail-metric:last-child{border-right:0}.dm-label{font-size:8px;color:#647189;font-weight:900}.dm-value{font-size:15px;font-weight:950;margin-top:3px}.dm-foot{font-size:8px;color:#7c8798;margin-top:2px}
.detail-evidence{border:1px solid #e3e7ee;border-radius:7px;overflow:hidden}.ev-grid{display:grid;grid-template-columns:1fr 1fr 1fr}.ev-cell{padding:8px;border-right:1px solid #e3e7ee;border-bottom:1px solid #e3e7ee}.ev-cell:nth-child(3n){border-right:0}.ev-cell:nth-last-child(-n+3){border-bottom:0}.ev-label{font-size:7px;color:#6c788d;font-weight:900;letter-spacing:.05em}.ev-value{font-size:10px;font-weight:900;margin-top:3px}.ev-good{color:#0a9a50}.ev-bad{color:#d52d39}
.detail-section{margin-top:11px}.detail-section-title{font-size:9px;font-weight:950;color:#5d6a80;letter-spacing:.07em;margin-bottom:6px}.interpretation{font-size:10px;line-height:1.5;color:#4b5870}.detail-time{border-top:1px solid #edf0f4;margin-top:11px;padding-top:8px;display:flex;justify-content:space-between;font-size:9px}.detail-time strong{font-size:10px;color:#263551}.first-time{color:#315bd5;font-weight:900}

/* Secondary pages */
.page-card{background:#fff;border:1px solid var(--line);border-radius:9px;padding:14px;box-shadow:0 2px 9px rgba(20,35,70,.035)}
.page-title{font-size:15px;font-weight:950}.page-sub{font-size:10px;color:#6c7890;margin-top:3px;margin-bottom:12px}

@media(max-width:1100px){
  .sdl-product{display:none}.sdl-nav .nav-label{padding:8px 9px;font-size:10px}.header-clock{display:none}.workspace{grid-template-columns:1fr}.detail-panel{position:relative;top:auto}.filter-grid{grid-template-columns:1fr 1fr}.filter-group{border-right:0}
}
@media(max-width:700px){
  .block-container{padding:0 8px 18px}.sdl-header{margin:0 -8px 10px;padding:8px 10px}.sdl-name{font-size:19px}.sdl-product{display:none}.sdl-nav{gap:1px;overflow-x:auto}.sdl-nav .nav-label{padding:7px 8px;font-size:9px}.header-right .header-control{display:none}
  .kpi-strip{grid-template-columns:repeat(3,1fr)}.kpi-item:nth-child(3){border-right:0}.kpi-item:nth-child(-n+3){border-bottom:1px solid #e8ecf2}.filter-grid{grid-template-columns:1fr}.radar-filters{flex-direction:column;align-items:flex-start}.stock-table{min-width:1040px}.table-card{overflow-x:auto}
}
</style>
""", unsafe_allow_html=True)


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
    for key in ("first_seen_timestamp", "first_detection_timestamp", "trigger_timestamp", "decision_timestamp", "observation_timestamp"):
        value = pd.to_datetime(row.get(key), errors="coerce")
        if pd.notna(value):
            return value
    return pd.NaT


def pct(value):
    x = pd.to_numeric(value, errors="coerce")
    return "—" if pd.isna(x) else f"{x:+.2f}%"


def time_text(value, date=True):
    x = pd.to_datetime(value, errors="coerce")
    if pd.isna(x):
        return "—"
    return x.strftime("%d %b %Y, %I:%M:%S %p") if date else x.strftime("%I:%M:%S")


def logo_url(symbol):
    symbol = str(symbol).strip().lower()
    return f"https://s3-symbol-logo.tradingview.com/{symbol}.svg" if symbol and symbol != "nan" else ""


def filter_frame(df, progress="All", direction="All", strength="All", stage="All"):
    out = df.copy()
    if out.empty:
        return out
    if direction != "All":
        out = out[out.direction_label.astype(str).str.upper().eq(direction.upper())]
    if strength != "All":
        out = out[out.strength_label.astype(str).str.upper().eq(strength.upper())]
    if stage != "All":
        out = out[out.stage.astype(str).eq(stage)]
    pv = pd.to_numeric(out.get("progress", pd.Series(index=out.index, dtype=float)), errors="coerce").fillna(-1)
    if progress == "25%+": out = out[pv >= 25]
    elif progress == "50%+": out = out[pv >= 50]
    elif progress == "70%+": out = out[pv >= 70]
    elif progress == "75%+": out = out[pv >= 75]
    elif progress == "Breakout": out = out[out.factual_breakout.astype(bool)]
    return out


def priority_frame(df, progress="All", strength="All"):
    out = filter_frame(df, progress=progress)
    if strength != "All":
        out = out[out.strength_label.astype(str).str.upper().eq(strength.upper())]
    if out.empty:
        return out
    return out.sort_values(["factual_breakout", "strength", "progress"], ascending=[False, False, False])


def run_live(path, stamp):
    try:
        result = process_snapshot(path, stamp)
        frames = [x for x in result if isinstance(x, pd.DataFrame)] if isinstance(result, tuple) else [result]
        df = frames[1] if len(frames) > 1 else (frames[0] if frames else pd.DataFrame())
        return candidates(df)
    except Exception:
        return pd.DataFrame()


def behaviour(row):
    d = str(row.get("direction_label", "")).upper()
    s = str(row.get("strength_label", "")).upper()
    if d == "BULLISH" and s == "STRONG": return "badge-bull"
    if d == "BEARISH" and s == "STRONG": return "badge-bear"
    if s == "DEVELOPING": return "badge-dev"
    if "WAIT" in s: return "badge-neutral"
    return "badge-blue"


def stage_class(stage):
    return "badge-blue" if "APPROACHING" in stage.upper() else "badge-neutral"


def confirmation_text(row):
    value = row.get("confirmation", row.get("confirmation_label", "STRONG"))
    if isinstance(value, str) and value.strip():
        return value
    return "STRONG"


def render_stock_table(df, key="decision_table"):
    if df.empty:
        st.markdown('<div class="table-card"><div style="padding:28px;text-align:center;color:#7a8699;font-size:12px">No qualified stocks match the current filters.</div></div>', unsafe_allow_html=True)
        return None

    work = df.copy().reset_index(drop=True)
    work["__logo"] = work["symbol"].map(logo_url)
    work["Stock"] = work.apply(lambda r: f"{str(r.get('symbol','')).upper()}", axis=1)
    work["Direction"] = work.apply(lambda r: f"{str(r.get('direction_label','—')).title()} · {str(r.get('strength_label','—')).title()}", axis=1)
    work["Momentum"] = pd.to_numeric(work.get("signed_price_move_pct"), errors="coerce")
    work["Straddle Progress"] = pd.to_numeric(work.get("progress"), errors="coerce").fillna(0)
    work["Stage"] = work.get("stage", "—").astype(str)
    work["Confirmation"] = work.apply(confirmation_text, axis=1)
    work["Strength"] = pd.to_numeric(work.get("strength"), errors="coerce")
    work["Breakout"] = work.get("factual_breakout", False).astype(bool).map(lambda x: "YES" if x else "—")
    work["Time"] = pd.to_datetime(work.get("observation_timestamp"), errors="coerce").map(lambda x: time_text(x, False))

    display = work[["__logo","Stock","Direction","Momentum","Straddle Progress","Stage","Confirmation","Strength","Breakout","Time"]].copy()
    display.insert(0, "#", range(1, len(display)+1))
    display = display.rename(columns={"__logo":"Logo"})

    styler = display.style
    styler = styler.format({
        "Momentum": lambda x: "—" if pd.isna(x) else f"{x:+.2f}%",
        "Straddle Progress": lambda x: f"{x:.1f}%",
        "Strength": lambda x: "—" if pd.isna(x) else f"{x:.0f}",
    })
    def color_momentum(v):
        if isinstance(v, (float, int)):
            return "color:#078c49;font-weight:800" if v >= 0 else "color:#d52d39;font-weight:800"
        return ""
    styler = styler.map(color_momentum, subset=["Momentum"])
    styler = styler.map(lambda v: "color:#079448;font-weight:900" if str(v)=="YES" else "color:#8c96a7;font-weight:700", subset=["Breakout"])
    styler = styler.map(lambda v: "color:#079448;font-weight:900" if isinstance(v,(float,int)) and v>=85 else "color:#17233f;font-weight:800", subset=["Strength"])

    st.markdown('<div class="table-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="table-titlebar"><div class="table-title">LIVE DECISION QUEUE</div><div class="table-meta">{len(display)} qualified · timestamped snapshot</div></div>', unsafe_allow_html=True)
    try:
        event = st.dataframe(
            styler,
            use_container_width=True,
            hide_index=True,
            height=min(610, 54 + 43 * max(1, min(len(display), 13))),
            selection_mode="single-row",
            on_select="rerun",
            key=key,
            column_config={
                "Logo": st.column_config.ImageColumn("", width="small"),
                "Stock": st.column_config.TextColumn("STOCK", width="medium"),
                "Direction": st.column_config.TextColumn("DIRECTION", width="medium"),
                "Momentum": st.column_config.NumberColumn("MOMENTUM", format="%.2f%%"),
                "Straddle Progress": st.column_config.ProgressColumn("STRADDLE PROGRESS", min_value=0, max_value=100, format="%.1f%%"),
                "Stage": st.column_config.TextColumn("STAGE", width="medium"),
                "Confirmation": st.column_config.TextColumn("CONFIRMATION", width="small"),
                "Strength": st.column_config.NumberColumn("STRENGTH", format="%.0f"),
                "Breakout": st.column_config.TextColumn("BREAKOUT", width="small"),
                "Time": st.column_config.TextColumn("TIME", width="small"),
            },
        )
        rows = getattr(getattr(event, "selection", None), "rows", []) if event is not None else []
        selected_idx = rows[0] if rows else 0
    except TypeError:
        st.dataframe(styler, use_container_width=True, hide_index=True, height=540)
        selected_idx = 0
    st.markdown('</div>', unsafe_allow_html=True)
    return work.iloc[selected_idx] if 0 <= selected_idx < len(work) else work.iloc[0]


def render_detail(row):
    if row is None:
        return
    symbol = str(row.get("symbol", "—")).upper()
    direction = str(row.get("direction_label", "—")).upper()
    strength_label = str(row.get("strength_label", "—")).upper()
    progress = float(pd.to_numeric(row.get("progress"), errors="coerce") or 0)
    momentum = pd.to_numeric(row.get("signed_price_move_pct"), errors="coerce")
    strength = pd.to_numeric(row.get("strength"), errors="coerce")
    stage = str(row.get("stage", "—"))
    confirmation = confirmation_text(row)
    breakout = bool(row.get("factual_breakout", False))
    updated = pd.to_datetime(row.get("observation_timestamp"), errors="coerce")
    first = first_seen(row)
    dclass = behaviour(row)
    move_cls = "ev-good" if pd.notna(momentum) and momentum >= 0 else "ev-bad"
    progress = min(100, max(0, progress))
    next_level = "100% BREAKOUT" if progress >= 75 else "75%" if progress >= 50 else "50%" if progress >= 25 else "25%"

    st.markdown('<div class="detail-panel">', unsafe_allow_html=True)
    st.markdown(f'''<div class="detail-top"><div class="detail-stock"><img class="detail-logo" src="{logo_url(symbol)}"><div><div class="detail-symbol">{html.escape(symbol)}</div><div style="font-size:8px;color:#778398">First seen: <b class="first-time">{time_text(first)}</b></div></div></div><div class="detail-actions">☆ ×</div></div>''', unsafe_allow_html=True)
    st.markdown(f'''<div class="detail-body"><div class="detail-decision"><div class="detail-decision-text" style="color:{'#0a9a50' if direction=='BULLISH' else '#d52d39' if direction=='BEARISH' else '#d18a00'}">{html.escape(direction.title())} · {html.escape(strength_label.title())}</div><span class="badge {stage_class(stage)}">STAGE&nbsp; {html.escape(stage)}</span></div><div class="detail-progress-label">Straddle Progress</div><div class="detail-progress-value">{progress:.1f}%</div><div class="detail-big-rail"><div class="detail-big-fill" style="width:{progress:.0f}%"></div></div><div class="detail-metrics"><div class="detail-metric"><div class="dm-label">MOMENTUM</div><div class="dm-value {move_cls}">{pct(momentum)}</div></div><div class="detail-metric"><div class="dm-label">STRENGTH</div><div class="dm-value">{'—' if pd.isna(strength) else f'{float(strength):.0f}'}</div><div class="dm-foot">/100</div></div><div class="detail-metric"><div class="dm-label">CONFIRMATION</div><div class="dm-value"><span class="badge badge-blue">{html.escape(str(confirmation).upper())}</span></div></div></div>''', unsafe_allow_html=True)

    open_p = pd.to_numeric(row.get("daily_open_reference", row.get("open_price")), errors="coerce")
    current_p = pd.to_numeric(row.get("current_price"), errors="coerce")
    frozen_s = pd.to_numeric(row.get("opening_straddle_premium", row.get("frozen_straddle")), errors="coerce")
    upper = open_p + frozen_s if pd.notna(open_p) and pd.notna(frozen_s) else pd.NA
    lower = open_p - frozen_s if pd.notna(open_p) and pd.notna(frozen_s) else pd.NA
    st.markdown(f'''<div class="detail-evidence"><div class="ev-grid"><div class="ev-cell"><div class="ev-label">OPEN</div><div class="ev-value">{'—' if pd.isna(open_p) else f'{float(open_p):,.2f}'}</div></div><div class="ev-cell"><div class="ev-label">CURRENT</div><div class="ev-value ev-good">{'—' if pd.isna(current_p) else f'{float(current_p):,.2f}'}</div></div><div class="ev-cell"><div class="ev-label">FROZEN S</div><div class="ev-value">{'—' if pd.isna(frozen_s) else f'{float(frozen_s):,.2f}'}</div></div><div class="ev-cell"><div class="ev-label">UPPER</div><div class="ev-value">{'—' if pd.isna(upper) else f'{float(upper):,.2f}'}</div></div><div class="ev-cell"><div class="ev-label">LOWER</div><div class="ev-value">{'—' if pd.isna(lower) else f'{float(lower):,.2f}'}</div></div><div class="ev-cell"><div class="ev-label">BREAKOUT</div><div class="ev-value {'ev-good' if breakout else ''}">{'YES' if breakout else '—'}</div></div></div></div>''', unsafe_allow_html=True)

    factors = []
    for factor in row.get("factors", []) or []:
        state = str(getattr(factor, "state", ""))
        label = str(getattr(factor, "label", "Factor"))
        factors.append((label, state))
    factor_lines = "".join(f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #edf0f4;font-size:9px"><span>{html.escape(label)}</span><b style="color:{"#0a9a50" if state=="SUPPORT" else "#d52d39" if state=="CONTRADICT" else "#7c8798"}">{html.escape(state)}</b></div>' for label,state in factors) or '<div style="font-size:9px;color:#7c8798">No additional factor rows available.</div>'
    interpretation = f"Price is {'above' if pd.notna(momentum) and momentum >= 0 else 'below'} the opening reference with {strength_label.lower()} confirmation. Straddle progression is {progress:.1f}% and the next decision level is {next_level}."
    st.markdown(f'''<div class="detail-section"><div class="detail-section-title">INTERPRETATION</div><div class="interpretation">{html.escape(interpretation)}</div></div><div class="detail-section"><div class="detail-section-title">CONFIRMATION FACTORS</div>{factor_lines}</div><div class="detail-time"><span>Updated <strong>{time_text(updated)}</strong></span><span>Decision time <strong>{time_text(updated, False)}</strong></span></div></div></div>''', unsafe_allow_html=True)


def render_filters(df, prefix="live"):
    strengths = sorted({str(x).upper() for x in df.get("strength_label", pd.Series(dtype=str)).dropna()}) if not df.empty else []
    stages = sorted({str(x) for x in df.get("stage", pd.Series(dtype=str)).dropna() if str(x).strip() and str(x).lower() != "nan"}) if not df.empty else []
    c1,c2,c3,c4 = st.columns([1.45,.8,1,1.7], gap="small")
    with c1:
        st.markdown('<div class="filter-title">PROGRESS</div>', unsafe_allow_html=True)
        progress = st.radio("progress", ["All","25%+","50%+","70%+","75%+","Breakout"], horizontal=True, key=f"{prefix}_progress", label_visibility="collapsed")
    with c2:
        st.markdown('<div class="filter-title">DECISION DIRECTION</div>', unsafe_allow_html=True)
        direction = st.radio("direction", ["All","Bullish","Bearish"], horizontal=True, key=f"{prefix}_direction", label_visibility="collapsed")
    with c3:
        st.markdown('<div class="filter-title">STRENGTH</div>', unsafe_allow_html=True)
        strength = st.radio("strength", ["All"] + [s.title() for s in strengths], horizontal=True, key=f"{prefix}_strength", label_visibility="collapsed")
    with c4:
        st.markdown('<div class="filter-title">STAGE</div>', unsafe_allow_html=True)
        stage = st.radio("stage", ["All"] + stages, horizontal=True, key=f"{prefix}_stage", label_visibility="collapsed")
    return filter_frame(df, progress, direction, strength, stage)


def render_kpis(df, stamp):
    q=len(df)
    strong=int(df.strength_label.astype(str).str.upper().eq("STRONG").sum()) if not df.empty else 0
    above50=int(pd.to_numeric(df.get("progress", pd.Series(dtype=float)), errors="coerce").ge(50).sum()) if not df.empty else 0
    approaching=int((pd.to_numeric(df.get("progress", pd.Series(dtype=float)), errors="coerce").ge(75) & pd.to_numeric(df.get("progress", pd.Series(dtype=float)), errors="coerce").lt(100)).sum()) if not df.empty else 0
    breakout=int(df.factual_breakout.astype(bool).sum()) if not df.empty else 0
    strong_pct=(strong/q*100) if q else 0
    stamp_text=time_text(stamp, False)
    items=[("QUALIFIED STOCKS",q,"Live Universe"),("STRONG",strong,f"{strong_pct:.1f}% of universe"),("ABOVE 50%",above50,"50%+ Progress"),("APPROACHING 75%+",approaching,"Near Next Level"),("BREAKOUT",breakout,"100% Breakout"),("DATA UPDATED",stamp_text,pd.to_datetime(stamp,errors="coerce").strftime("%d %b %Y") if pd.notna(pd.to_datetime(stamp,errors="coerce")) else "Snapshot time")]
    cells=[]
    for i,(label,val,foot) in enumerate(items):
        dot='<span class="kpi-live"></span>' if i==5 else ''
        cells.append(f'<div class="kpi-item"><div class="kpi-label">{label}{dot}</div><div class="kpi-value">{val}</div><div class="kpi-foot">{foot}</div></div>')
    st.markdown('<div class="kpi-strip">'+''.join(cells)+'</div>', unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Header navigation. Navigation changes presentation page only.
# -----------------------------------------------------------------------------
now=pd.Timestamp.now()
today=now.date().isoformat()
today_files=files(today)
live_path=max(today_files,key=ts) if today_files else None
live_ts=ts(live_path) if live_path else pd.NaT
live=run_live(live_path,live_ts) if live_path else pd.DataFrame()

page_options=["Decision Board","Replay","Historical Evidence","Settings"]
try:
    query_page=str(st.query_params.get("page", "Decision Board"))
except Exception:
    query_page="Decision Board"
current=query_page if query_page in page_options else "Decision Board"

nav_html=[]
for label in page_options:
    active=" active" if label==current else ""
    href=label.replace(" ", "%20")
    nav_html.append(f'<a class="nav-label{active}" href="?page={href}">{html.escape(label)}</a>')
nav=''.join(nav_html)

header_html=f"""<div class=\"sdl-header\"><div class=\"sdl-brand\"><div class=\"sdl-logo\">SDL</div><div class=\"sdl-name\">NTIS SDL</div><div class=\"sdl-product\">INTRADAY DECISION CENTRE</div></div><div class=\"sdl-nav\">{nav}</div><div class=\"header-right\"><span class=\"live-pill\">LIVE</span><div class=\"header-clock\"><strong>{now.strftime('%I:%M:%S %p')}</strong><br><small>{now.strftime('%d %b %Y')}</small></div><a class=\"header-control\" href=\"?page={current}&refresh={now.value}\">Refresh</a><span class=\"header-control\">Auto Refresh&nbsp;&nbsp;10s</span></div></div>"""
st.markdown(header_html,unsafe_allow_html=True)

# The visible control is intentionally compact; the header remains visually identical to the approved reference.
auto=st.checkbox("Auto Refresh",value=st.session_state.get("auto_refresh",True),key="auto_refresh",label_visibility="collapsed")
if auto and hasattr(st,"fragment"):
    @st.fragment(run_every="10s")
    def _sdl_refresh_tick():
        st.rerun()
    _sdl_refresh_tick()

if page_options.index(current)==0:
    render_kpis(live,live_ts)
    st.markdown('<div class="filter-panel">',unsafe_allow_html=True)
    visible=render_filters(live,"live")
    reset_col1, reset_col2 = st.columns([5,1])
    with reset_col2:
        if st.button("Reset Filters", key="reset_live_filters"):
            for k in ["live_progress","live_direction","live_strength","live_stage","radar_progress","radar_strength"]:
                st.session_state.pop(k, None)
            st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)
    if st.button("↻ Refresh", key="manual_refresh_top"):
        st.rerun()

    st.markdown('<div class="radar-head"><div><div class="radar-title">PRIORITY RADAR · INDEPENDENT FILTER</div><div class="radar-sub">Highest-strength members of the same qualified universe</div></div></div>',unsafe_allow_html=True)
    rp1,rp2=st.columns([1.2,1])
    with rp1:
        st.markdown('<div class="filter-title">PROGRESS</div>',unsafe_allow_html=True)
        rp=st.radio("radar_progress",["All","25%+","50%+","70%+","75%+","Breakout"],horizontal=True,key="radar_progress",label_visibility="collapsed")
    with rp2:
        st.markdown('<div class="filter-title">STRENGTH</div>',unsafe_allow_html=True)
        rs=st.radio("radar_strength",["All","Strong","Developing"],horizontal=True,key="radar_strength",label_visibility="collapsed")
    radar=priority_frame(live,rp,rs).head(5)
    if not radar.empty:
        cards=[]
        for _,r in radar.iterrows():
            p=float(pd.to_numeric(r.get("progress"),errors="coerce") or 0)
            cards.append(f'<div style="display:inline-block;width:19%;min-width:150px;padding:7px 10px;border-right:1px solid #e8ecf2"><div style="font-size:9px;font-weight:900;color:#253451">{html.escape(str(r.get("symbol","" )).upper())}</div><div style="font-size:8px;color:#6f7c91">{html.escape(str(r.get("direction_label","—")).title())} · {html.escape(str(r.get("strength_label","—")).title())}</div><div style="font-size:15px;font-weight:950;margin-top:4px">{p:.1f}%</div></div>')
        st.markdown('<div style="background:#fff;border:1px solid var(--line);border-top:0;border-radius:0 0 9px 9px;padding:4px 6px;margin-bottom:12px;white-space:nowrap;overflow-x:auto">'+''.join(cards)+'</div>',unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#fff;border:1px solid var(--line);border-top:0;border-radius:0 0 9px 9px;padding:14px;color:#7a8699;font-size:10px">No priority stocks match the independent radar filters.</div>',unsafe_allow_html=True)

    st.markdown('<div style="font-size:10px;color:#6c7890;margin:4px 0 7px"><b>'+str(len(visible))+'</b> matching stocks · filters only narrow the qualified universe.</div>',unsafe_allow_html=True)
    selected=render_stock_table(visible,"live_stock_table")
    with st.container():
        render_detail(selected)

elif current=="Replay":
    st.markdown('<div class="page-card"><div class="page-title">REPLAY</div><div class="page-sub">Exact historical snapshot replay. Later observations cannot upgrade the selected result.</div></div>',unsafe_allow_html=True)
    all_files=files()
    days=sorted({ts(p).date().isoformat() for p in all_files if pd.notna(ts(p))},reverse=True)
    if days:
        day=st.date_input("Trading day",pd.Timestamp(days[0]).date(),key="replay_day")
        day_files=files(day.isoformat())
        times=[ts(p) for p in day_files]
        labels=[t.strftime("%H:%M:%S") for t in times]
        if labels:
            label=st.selectbox("Snapshot time",labels,key="replay_time")
            selected_path=day_files[labels.index(label)]
            if st.button("Replay selected snapshot",type="primary"):
                try:
                    replay_trading_date(day.isoformat())
                    result=process_snapshot(selected_path,ts(selected_path))
                    frames=[x for x in result if isinstance(x,pd.DataFrame)] if isinstance(result,tuple) else [result]
                    replay_df=frames[1] if len(frames)>1 else (frames[0] if frames else pd.DataFrame())
                    st.session_state["replay_df"]=candidates(replay_df)
                    st.session_state["replay_ts"]=ts(selected_path)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Replay failed: {exc}")
    replay_df=st.session_state.get("replay_df",pd.DataFrame())
    if isinstance(replay_df,pd.DataFrame) and not replay_df.empty:
        replay_ts=st.session_state.get("replay_ts",pd.NaT)
        render_kpis(replay_df,replay_ts)
        st.markdown('<div class="filter-panel">',unsafe_allow_html=True)
        rv=render_filters(replay_df,"replay")
        st.markdown('</div>',unsafe_allow_html=True)
        selected=render_stock_table(rv,"replay_stock_table")
        render_detail(selected)
    else:
        st.info("Select a trading day and snapshot time, then load Replay.")

elif current=="Historical Evidence":
    st.markdown('<div class="page-card"><div class="page-title">HISTORICAL EVIDENCE</div><div class="page-sub">Factual historical evidence only; it never feeds information backward into Live or Replay.</div></div>',unsafe_allow_html=True)
    events=load_events(EVENT_CSV)
    if events is None or events.empty:
        st.info("No historical evidence records available.")
    else:
        events=events.copy()
        if "observation_timestamp" in events.columns:
            events["observation_timestamp"]=pd.to_datetime(events["observation_timestamp"],errors="coerce")
            events=events.sort_values("observation_timestamp",ascending=False)
            events["observation_timestamp"]=events["observation_timestamp"].dt.strftime("%d %b %Y, %H:%M:%S")
        keep=[c for c in ["observation_timestamp","symbol","direction","price_chg_pct","breakout_distance","strength"] if c in events.columns]
        st.dataframe(events[keep] if keep else events,use_container_width=True,hide_index=True)

else:
    st.markdown('<div class="page-card"><div class="page-title">SETTINGS</div><div class="page-sub">Administrative configuration. Normal Decision Board remains focused on trading decisions.</div></div>',unsafe_allow_html=True)
    root=st.text_input("Active source data folder",str(getattr(sdl_pipeline,"INTRADAY_SOURCE_ROOT","")))
    if st.button("Apply source folder",type="primary"):
        source_path=Path(root).expanduser().resolve()
        sdl_pipeline.INTRADAY_SOURCE_ROOT=source_path
        sdl_config.INTRADAY_SOURCE_ROOT=source_path
        st.success("Source folder applied for this dashboard session.")
    st.markdown('<div class="page-card"><b>Runtime:</b> Preview 8587 · Production 8504 remains untouched.<br><b>Decision engine:</b> existing SDL pipeline / prediction / replay implementation.</div>',unsafe_allow_html=True)

st.markdown(f'<div style="border-top:1px solid #dfe5ef;margin-top:14px;padding:8px 3px;color:#7a8698;font-size:9px;display:flex;justify-content:space-between"><span>NTIS SDL · Intraday Decision Centre</span><span>First timestamp preserved · Latest update {time_text(live_ts)}</span></div>',unsafe_allow_html=True)
