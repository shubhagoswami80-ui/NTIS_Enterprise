from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

import config as sdl_config
import pipeline as sdl_pipeline
from config import EVENT_CSV
from pipeline import discover_historical_snapshots, process_snapshot
from prediction_engine import build_current_predictions, factor_labels
from source_loader import parse_observation_timestamp
from storage import load_events


# ============================================================================
# NTIS SDL — APPROVED DASHBOARD DEPLOYMENT
#
# PRESENTATION LAYER ONLY
# ----------------------------------------------------------------------------
# SDL/app.py is deliberately NOT used or modified.
# Existing pipeline, qualified-stock selection, frozen-base calculation,
# prediction/evidence grading, and event persistence remain authoritative.
#
# Filters only reduce the already-qualified display universe.
# Replay is bounded to the selected completed source snapshot.
# Historical evidence never feeds backward into Live or Replay.
# ============================================================================

st.set_page_config(
    page_title="NTIS SDL — Intraday Decision Centre",
    page_icon="SDL",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================================
# APPROVED VISUAL SYSTEM
# ============================================================================

st.markdown(
    """
<style>
:root{
  --bg:#050d18;
  --bg2:#071323;
  --panel:#0a1728;
  --panel2:#0e1d31;
  --panel3:#13243a;
  --line:#1d3453;
  --line2:#29476e;
  --text:#f2f6fc;
  --muted:#8fa2bb;
  --blue:#5b8dff;
  --purple:#7a5cff;
  --green:#19df82;
  --red:#ff5963;
  --amber:#ffb21c;
  --cyan:#11cfe2;
}

.stApp{
  background:
    radial-gradient(circle at 50% -12%,#102b54 0%,transparent 38%),
    linear-gradient(180deg,#050d18 0%,#071321 100%);
  color:var(--text);
}
.block-container{max-width:1660px!important;padding:0 18px 24px!important}
[data-testid="stSidebar"]{display:none!important}
footer{display:none!important}
header[data-testid="stHeader"]{background:#040a12!important;height:38px!important}
div[data-testid="stToolbar"],div[data-testid="stDecoration"]{display:none!important}
div[data-testid="stAppViewContainer"]{background:transparent!important}
div[data-testid="stVerticalBlock"]{gap:.32rem!important}
p,label,span,div{font-family:Inter,Segoe UI,Arial,sans-serif}

/* HEADER */
.sdl-header{
  margin:0 -18px 10px;
  padding:9px 20px 10px;
  min-height:60px;
  background:linear-gradient(105deg,#061126 0%,#0b1c3a 55%,#102a58 100%);
  border-bottom:1px solid #20375d;
  box-shadow:0 8px 28px rgba(0,0,0,.28);
}
.sdl-header-grid{
  display:grid;
  grid-template-columns:1.25fr 2.1fr 2.25fr;
  gap:12px;
  align-items:center;
}
.sdl-brand{font-size:20px;font-weight:950;letter-spacing:.02em}
.sdl-sub{color:#b7c5da;font-size:9px;font-weight:700;letter-spacing:.07em;margin-top:3px}
.nav-row{display:flex;gap:6px}
.nav-row div[data-testid="stButton"] button{
  min-height:34px!important;border-radius:7px!important;
  font-size:11px!important;font-weight:900!important
}
.nav-row div[data-testid="stButton"] button[kind="primary"]{
  background:#f02f35!important;border:1px solid #ff5960!important;color:#fff!important
}
.nav-row div[data-testid="stButton"] button[kind="secondary"]{
  background:#0d192c!important;border:1px solid #1f324e!important;color:#dce5f3!important
}
.header-right{display:flex;align-items:center;justify-content:flex-end;gap:9px}
.live-pill{
  display:inline-flex;align-items:center;gap:6px;
  border:1px solid #155f46;background:#08291e;color:#4de59b;
  border-radius:999px;padding:6px 10px;font-size:9px;font-weight:950
}
.live-pill i{width:7px;height:7px;border-radius:50%;background:#1fe184;box-shadow:0 0 0 3px rgba(31,225,132,.12)}
.clock{text-align:right;line-height:1.05}
.clock b{font-size:14px}.clock small{display:block;color:#9aabc2;font-size:8px;margin-top:3px}
.header-right div[data-testid="stButton"] button{
  min-height:32px!important;border-radius:7px!important;
  background:#101f35!important;border:1px solid #29405e!important;
  color:#e8eef8!important;font-size:9px!important;font-weight:900!important
}
.header-right div[data-testid="stCheckbox"] label p{color:#e8eef8!important;font-size:9px!important;font-weight:850!important}
.header-right div[data-testid="stSelectbox"]>div>div{
  min-height:32px!important;background:#101f35!important;border:1px solid #29405e!important;
  color:#fff!important;font-size:9px!important
}

/* STATUS */
.status-strip{
  display:grid;grid-template-columns:1fr 1fr;
  background:#091729;border:1px solid #203653;border-radius:9px;margin-bottom:9px;overflow:hidden
}
.status-cell{padding:8px 14px;min-height:55px}
.status-cell:first-child{border-right:1px solid #203653}
.status-label{color:#a8b8ce;font-size:8px;font-weight:950;letter-spacing:.12em}
.status-value{font-size:13px;font-weight:950;margin-top:5px}
.status-value.green{color:#18df82}
.status-foot{font-size:8px;color:#7588a2;margin-top:3px}

/* KPI */
.kpi-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:9px}
.kpi{
  min-height:76px;padding:10px 12px;border-radius:8px;background:#0d1b2e;
  border:1px solid #233a5d;box-shadow:0 5px 15px rgba(0,0,0,.16)
}
.kpi.green{border-color:#104d3d}.kpi.red{border-color:#6b242c}
.kpi.purple{border-color:#3c2d78}.kpi.amber{border-color:#604612}.kpi.cyan{border-color:#15546a}
.kpi-label{font-size:8px;font-weight:950;letter-spacing:.10em;color:#aabbd0}
.kpi-value{font-size:24px;line-height:1;margin-top:6px;font-weight:950}
.kpi-foot{font-size:8px;color:#8a9ab1;margin-top:6px}
.kpi-icon{
  float:left;width:30px;height:30px;border-radius:8px;margin-right:9px;
  display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:950;
  background:#142a4c;color:#74a2ff
}
.kpi.green .kpi-icon{background:#083324;color:#18df82}
.kpi.red .kpi-icon{background:#3b171d;color:#ff6570}
.kpi.purple .kpi-icon{background:#211957;color:#9b7cff}
.kpi.amber .kpi-icon{background:#39270b;color:#ffb31c}
.kpi.cyan .kpi-icon{background:#073341;color:#10d1e6}

/* FILTERS */
.filter-panel{
  background:#091729;border:1px solid #203653;border-radius:9px;
  padding:10px 12px 9px;margin-bottom:9px
}
.filter-caption{color:#8ea1bb;font-size:8px;margin-bottom:8px}
.filter-group{padding:0 12px;border-right:1px solid #1c304a;min-width:0}
.filter-group:first-child{padding-left:2px}.filter-group:last-child{border-right:0;padding-right:2px}
.filter-title{color:#b5c4d8;font-size:9px;font-weight:950;letter-spacing:.10em;margin-bottom:6px}
div[data-testid="stRadio"]>label{display:none!important}
div[data-testid="stRadio"] [role="radiogroup"]{display:flex!important;flex-wrap:wrap!important;gap:5px!important}
div[data-testid="stRadio"] [role="radiogroup"] label{
  background:#0d1b2e!important;border:1px solid #29405e!important;border-radius:999px!important;
  padding:5px 10px!important;min-height:27px!important;margin:0!important
}
div[data-testid="stRadio"] [role="radiogroup"] label p{color:#dfe8f6!important;font-size:9px!important;font-weight:850!important}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked){background:#f02f35!important;border-color:#ff5960!important}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p{color:#fff!important}
.reset-row{display:flex;justify-content:flex-end;margin-top:-2px}
.reset-row div[data-testid="stButton"] button{
  min-height:28px!important;border-radius:6px!important;background:#102038!important;
  border:1px solid #27415f!important;color:#d8e2ef!important;font-size:9px!important;font-weight:850!important
}

/* RADAR */
.section-bar{
  background:linear-gradient(105deg,#081b38,#102c5b);
  border:1px solid #294b7b;border-radius:8px;padding:7px 10px;color:#fff;
  font-size:9px;font-weight:950;letter-spacing:.10em;margin-bottom:7px
}
.radar{background:#091729;border:1px solid #203653;border-radius:9px;padding:8px 10px;margin-bottom:9px}
.radar-top{display:grid;grid-template-columns:1.45fr 1fr 2.1fr;gap:8px;align-items:center}
.radar-filter{border-right:1px solid #1d314c;padding-right:10px}
.radar-title{font-size:8px;color:#b1c0d3;font-weight:950;letter-spacing:.1em;margin-bottom:5px}
.radar div[data-testid="stRadio"] [role="radiogroup"] label{padding:4px 8px!important;min-height:24px!important}
.radar-cards{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;min-width:0}
.radar-card{background:#0f1e33;border:1px solid #203a5b;border-radius:7px;padding:7px;min-height:68px}
.radar-symbol{font-size:10px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.radar-meta{font-size:7px;color:#93a5bd;margin-top:3px}
.radar-progress{font-size:13px;font-weight:950;color:#ffb31c;margin-top:4px}
.radar-first{font-size:7px;color:#7489a4;margin-top:2px}

/* WORKSPACE */
.workspace{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(300px,.95fr) minmax(230px,.72fr);gap:9px;align-items:start}
.panel{background:#091729;border:1px solid #203653;border-radius:9px;overflow:hidden}
.panel-head{padding:9px 11px;border-bottom:1px solid #203653;background:#0e1d31}
.panel-title{font-size:11px;font-weight:950;color:#edf3fc}
.panel-sub{font-size:8px;color:#8093ad;margin-top:3px}
.queue-scroll{overflow-x:auto}
table.queue{width:100%;border-collapse:collapse;table-layout:fixed;font-size:9px}
table.queue th{background:#13243a;color:#a9b8ce;font-size:7px;letter-spacing:.08em;text-align:left;padding:8px 6px;border-bottom:1px solid #2a4260;white-space:nowrap}
table.queue td{background:#0b192b;color:#e3ebf7;padding:8px 6px;border-bottom:1px solid #1b2c43;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stock{display:flex;align-items:center;gap:5px;font-weight:950}
.logo{width:23px;height:23px;flex:0 0 23px;border-radius:6px;background:#fff;color:#17325c;border:1px solid #415675;display:flex;align-items:center;justify-content:center;font-size:7px;font-weight:950}
.badge{display:inline-block;padding:4px 6px;border-radius:5px;font-size:8px;font-weight:950}
.badge.red{background:#35171d;border:1px solid #773039;color:#ff6b75}
.badge.green{background:#0b3023;border:1px solid #19694a;color:#38e296}
.badge.amber{background:#34260f;border:1px solid #6e521e;color:#ffc24d}
.badge.blue{background:#14284b;border:1px solid #3a5f9f;color:#93b2ff}
.progress{display:flex;align-items:center;gap:4px}.progress span{font-weight:950}
.rail{width:42px;height:5px;border-radius:99px;background:#26384f;overflow:hidden}
.fill{height:100%;background:#ffad17;border-radius:99px}.fill.green{background:#19d27f}
.time{font-variant-numeric:tabular-nums;color:#b8c6d9;font-weight:850}
.view-more{display:flex;justify-content:center;padding:7px;border-top:1px solid #203653}
.view-more div[data-testid="stButton"] button{min-height:27px!important;background:#102038!important;border:1px solid #2a4565!important;color:#e0e8f4!important;font-size:8px!important}

/* DETAIL */
.detail-body{padding:10px}
.detail-select div[data-testid="stSelectbox"]>div>div{background:#0f1e33!important;border:1px solid #29415f!important;min-height:31px!important;color:#fff!important}
.detail-hero{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:8px 0 9px;border-bottom:1px solid #203653}
.detail-symbol{font-size:15px;font-weight:950}.detail-sub{font-size:7px;color:#8498b2;margin-top:3px}
.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-top:8px}
.metric{background:#0f1e33;border:1px solid #203a59;border-radius:7px;padding:7px;min-height:58px}
.metric-label{font-size:7px;color:#8da0b9;font-weight:950;letter-spacing:.08em}
.metric-value{font-size:14px;font-weight:950;margin-top:4px;line-height:1.05}
.metric-foot{font-size:7px;color:#758aa5;margin-top:3px}
.process{background:#0f1e33;border:1px solid #203a59;border-radius:7px;padding:8px;margin-top:7px}
.process-title{font-size:8px;color:#9eb0c7;font-weight:950;letter-spacing:.08em}
.process-value{font-size:21px;font-weight:950;margin-top:2px}
.process-rail{height:7px;background:#27384e;border-radius:99px;overflow:hidden;margin:7px 0}
.process-fill{height:100%;background:#ff4d5a;border-radius:99px}
.process-scale{display:flex;justify-content:space-between;color:#6f829d;font-size:6px}
.factor-list{background:#0b192b;border:1px solid #203653;border-radius:7px;margin-top:7px;padding:5px 8px}
.factor-row{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1b2c43;font-size:8px}
.factor-row:last-child{border-bottom:0}.support{color:#18d27f;font-weight:950}.contradict{color:#ff626c;font-weight:950}.neutral{color:#8ea0b8;font-weight:850}

/* NEWS / REPLAY */
.news-card{padding:10px;border-top:1px solid #203653;min-height:96px}
.news-card:first-of-type{border-top:0}.news-title{font-size:9px;font-weight:950;letter-spacing:.05em}
.news-status{display:inline-block;margin-top:8px;padding:4px 6px;border-radius:5px;background:#101f33;border:1px dashed #3a506d;color:#8fa1b8;font-size:7px}
.news-copy{font-size:8px;color:#8498b1;line-height:1.35;margin-top:7px}
.replay{margin-top:9px;background:#091729;border:1px solid #203653;border-radius:9px;padding:9px 11px}
.replay-title{font-size:10px;font-weight:950}.replay-sub{font-size:8px;color:#8295ae;margin-top:3px}
.replay-state{text-align:right;color:#8ea0b8;font-size:8px;padding-top:4px}
.replay div[data-testid="stDateInput"] input,.replay div[data-testid="stTimeInput"] input{background:#0f1e33!important;color:#edf3fc!important;border:1px solid #29415f!important}
.replay div[data-testid="stButton"] button{min-height:32px!important;background:#f02f35!important;border:1px solid #ff5960!important;color:#fff!important;font-weight:950!important}
.replay-queue{margin-top:8px}

/* FOOTER */
.sdl-footer{display:flex;justify-content:space-between;gap:10px;border-top:1px solid #1d3049;margin-top:9px;padding-top:7px;color:#6f819b;font-size:7px}

/* RESPONSIVE */
@media(max-width:1200px){
  .sdl-header-grid{grid-template-columns:1fr}.header-right{justify-content:flex-start}
  .kpi-grid{grid-template-columns:repeat(3,1fr)}.workspace{grid-template-columns:1fr}
  .radar-top{grid-template-columns:1fr}.radar-filter{border-right:0;border-bottom:1px solid #1d314c;padding:0 0 7px}
}
@media(max-width:700px){
  .kpi-grid{grid-template-columns:1fr}.radar-cards{grid-template-columns:1fr 1fr}
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================================
# DATA HELPERS — EXISTING SDL LOGIC ONLY
# ============================================================================

def _timestamp(path: str | Path) -> pd.Timestamp:
    try:
        return parse_observation_timestamp(path)
    except Exception:
        try:
            return pd.Timestamp.fromtimestamp(Path(path).stat().st_mtime)
        except Exception:
            return pd.NaT


def _snapshot_files(day: str | None = None) -> list[Path]:
    try:
        raw = [Path(p) for p in discover_historical_snapshots(day)]
    except Exception:
        return []
    pairs = []
    for p in raw:
        t = _timestamp(p)
        if pd.notna(t):
            pairs.append((p, t))
    return [p for p, _ in sorted(pairs, key=lambda x: (x[1], str(x[0]).lower()))]


def _frozen_base(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    if df is None or df.empty or "Symbol" not in df.columns:
        return {}
    result: dict[str, dict[str, float]] = {}
    for _, row in df.drop_duplicates("Symbol").iterrows():
        symbol = str(row.get("Symbol", "")).strip().upper()
        op = pd.to_numeric(row.get("daily_open_reference"), errors="coerce")
        premium = pd.to_numeric(row.get("opening_straddle_premium"), errors="coerce")
        if symbol and pd.notna(op) and pd.notna(premium) and float(premium) > 0:
            result[symbol] = {"open_price": float(op), "opening_straddle_premium": float(premium)}
    return result


def _predictions(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return build_current_predictions(df, _frozen_base(df))


def _process(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    try:
        result = process_snapshot(path, _timestamp(path))
        frames = [x for x in result if isinstance(x, pd.DataFrame)] if isinstance(result, tuple) else [result]
        # Preserve the existing SDL application's current-snapshot dataframe.
        base = frames[1] if len(frames) > 1 else (frames[0] if frames else pd.DataFrame())
        return _predictions(base)
    except Exception:
        return pd.DataFrame()


def _first_seen(row: pd.Series) -> pd.Timestamp:
    for key in ("first_seen_timestamp","first_detection_timestamp","trigger_timestamp","decision_timestamp","observation_timestamp"):
        value = pd.to_datetime(row.get(key), errors="coerce")
        if pd.notna(value):
            return value
    return pd.NaT


def _fmt_time(value: Any, date: bool = True) -> str:
    x = pd.to_datetime(value, errors="coerce")
    if pd.isna(x):
        return "—"
    return x.strftime("%d %b %Y, %H:%M:%S" if date else "%H:%M:%S")


def _fmt_pct(value: Any) -> str:
    x = pd.to_numeric(value, errors="coerce")
    return "—" if pd.isna(x) else f"{x:+.2f}%"


def _logo(symbol: Any) -> str:
    text = str(symbol or "").strip().upper()
    if not text or text == "NAN":
        text = "—"
    return f'<span class="logo">{text[:4]}</span>'


def _direction_class(row: pd.Series) -> str:
    direction = str(row.get("direction_label", "")).upper()
    return "green" if direction == "BULLISH" else "red" if direction == "BEARISH" else "amber"


def _safe_stage(row: pd.Series) -> str:
    value = str(row.get("stage", "—"))
    return "—" if value.lower() == "nan" else value


# ============================================================================
# DISPLAY FILTERS — NEVER ALTER THE SDL DECISION
# ============================================================================

def _filter_df(df: pd.DataFrame, key: str) -> pd.DataFrame:
    if df.empty:
        return df

    progress_options = ["All", "25%+", "50%+", "70%+", "75%+", "Breakout"]
    direction_options = ["All", "Bullish", "Bearish"]
    strength_options = ["All", "Developing", "Strong", "Supported", "Wait / Conflict"]
    stage_options = ["All", "100%+ BREAKOUT", "25–<50% EARLY", "50–<75%", "75–<100% APPROACHING"]

    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    st.markdown('<div class="filter-caption">✦ Four independent trader dimensions · filtering never changes the underlying SDL decision score.</div>', unsafe_allow_html=True)

    values = {}
    cols = st.columns(4)
    for col, title, options in zip(cols, ["PROGRESS","DIRECTION","STRENGTH","STAGE"], [progress_options,direction_options,strength_options,stage_options]):
        with col:
            st.markdown(f'<div class="filter-group"><div class="filter-title">{title} ⓘ</div>', unsafe_allow_html=True)
            values[title] = st.radio(title, options, horizontal=True, key=f"{key}_{title.lower()}", label_visibility="collapsed")
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="reset-row">', unsafe_allow_html=True)
    if st.button("↻ Reset Filters", key=f"{key}_reset"):
        for suffix in ("progress","direction","strength","stage"):
            st.session_state.pop(f"{key}_{suffix}", None)
        st.rerun()
    st.markdown("</div></div>", unsafe_allow_html=True)

    out = df.copy()

    if values["DIRECTION"] != "All":
        out = out[out["direction_label"].astype(str).str.upper().eq(values["DIRECTION"].upper())]
    if values["STRENGTH"] != "All":
        target = values["STRENGTH"].upper().replace(" / ", "/")
        out = out[out["strength_label"].astype(str).str.upper().str.contains(target.split("/")[0], regex=False)]

    p = pd.to_numeric(out.get("progress", pd.Series(index=out.index, dtype=float)), errors="coerce").fillna(-1)
    if values["PROGRESS"] == "25%+": out = out[p >= 25]
    elif values["PROGRESS"] == "50%+": out = out[p >= 50]
    elif values["PROGRESS"] == "70%+": out = out[p >= 70]
    elif values["PROGRESS"] == "75%+": out = out[p >= 75]
    elif values["PROGRESS"] == "Breakout": out = out[out["factual_breakout"].astype(bool)]

    if values["STAGE"] != "All":
        wanted = values["STAGE"]
        p = pd.to_numeric(out.get("progress", pd.Series(index=out.index, dtype=float)), errors="coerce")
        if wanted == "100%+ BREAKOUT": out = out[out["factual_breakout"].astype(bool)]
        elif wanted == "25–<50% EARLY": out = out[(p >= 25) & (p < 50)]
        elif wanted == "50–<75%": out = out[(p >= 50) & (p < 75)]
        elif wanted == "75–<100% APPROACHING": out = out[(p >= 75) & (p < 100)]

    return out


# ============================================================================
# UI COMPONENTS
# ============================================================================

def _kpis(df: pd.DataFrame, stamp: pd.Timestamp) -> None:
    qualified = len(df)
    bullish = int(df["direction_label"].eq("BULLISH").sum()) if not df.empty else 0
    bearish = int(df["direction_label"].eq("BEARISH").sum()) if not df.empty else 0
    strong = int(df["strength_label"].eq("STRONG").sum()) if not df.empty else 0
    breakout = int(df["factual_breakout"].astype(bool).sum()) if not df.empty else 0

    first = pd.NaT
    if not df.empty:
        vals = [_first_seen(row) for _, row in df.iterrows()]
        vals = [x for x in vals if pd.notna(x)]
        first = min(vals) if vals else pd.NaT

    items = [
        ("QUALIFIED", qualified, "◉", ""),
        ("BULLISH", bullish, "◆", "green"),
        ("BEARISH", bearish, "◆", "red"),
        ("STRONG", strong, "★", "purple"),
        ("BREAKOUT", breakout, "◎", "amber"),
        ("FIRST ALERT", _fmt_time(first, False), "♢", "cyan"),
    ]
    html = ['<div class="kpi-grid">']
    for label, value, icon, cls in items:
        html.append(
            f'<div class="kpi {cls}"><div class="kpi-icon">{icon}</div>'
            f'<div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>'
            f'<div class="kpi-foot">Data updated {_fmt_time(stamp, False)}</div></div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _priority_radar(df: pd.DataFrame) -> None:
    st.markdown('<div class="section-bar">PRIORITY RADAR · INDEPENDENT FILTER</div>', unsafe_allow_html=True)
    st.markdown('<div class="radar"><div class="radar-top">', unsafe_allow_html=True)

    c1, c2 = st.columns([1.35, 1])
    with c1:
        st.markdown('<div class="radar-filter"><div class="radar-title">PROGRESS</div>', unsafe_allow_html=True)
        rp = st.radio("Radar progress", ["All","25%+","50%+","70%+","75%+","Breakout"], horizontal=True, key="radar_progress", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="radar-filter"><div class="radar-title">STRENGTH</div>', unsafe_allow_html=True)
        rs = st.radio("Radar strength", ["All","Strong","Developing"], horizontal=True, key="radar_strength", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

    work = df.copy()
    p = pd.to_numeric(work.get("progress", pd.Series(index=work.index, dtype=float)), errors="coerce").fillna(-1)
    if rp == "25%+": work = work[p >= 25]
    elif rp == "50%+": work = work[p >= 50]
    elif rp == "70%+": work = work[p >= 70]
    elif rp == "75%+": work = work[p >= 75]
    elif rp == "Breakout": work = work[work["factual_breakout"].astype(bool)]
    if rs != "All":
        work = work[work["strength_label"].astype(str).str.upper().eq(rs.upper())]

    work = work.sort_values(["factual_breakout","strength","progress"], ascending=[False,False,False]).head(5)

    cards = []
    for _, row in work.iterrows():
        progress = float(pd.to_numeric(row.get("progress"), errors="coerce") or 0)
        symbol = str(row.get("symbol","—")).upper()
        cards.append(
            f'<div class="radar-card"><div class="radar-symbol">{_logo(symbol)} {symbol}</div>'
            f'<div class="radar-meta">{str(row.get("direction_label","—")).title()} · {str(row.get("strength_label","—")).title()}</div>'
            f'<div class="radar-meta">{_safe_stage(row)}</div>'
            f'<div class="radar-progress">{progress:.1f}%{" · BREAKOUT" if bool(row.get("factual_breakout",False)) else ""}</div>'
            f'<div class="radar-first">First: {_fmt_time(_first_seen(row),False)}</div></div>'
        )
    st.markdown('<div class="radar-cards">' + "".join(cards) + "</div></div></div>", unsafe_allow_html=True)


def _queue(df: pd.DataFrame, limit: int = 12) -> None:
    if df.empty:
        st.markdown('<div style="padding:20px;color:#8fa1bb;text-align:center">No qualified SDL decisions are available for the selected snapshot.</div>', unsafe_allow_html=True)
        return

    rows = []
    for i, (_, row) in enumerate(df.head(limit).iterrows(), 1):
        symbol = str(row.get("symbol","—")).upper()
        direction = str(row.get("direction_label","—")).title()
        strength = str(row.get("strength_label","—")).title()
        momentum = pd.to_numeric(row.get("signed_price_move_pct"), errors="coerce")
        progress = float(pd.to_numeric(row.get("progress"), errors="coerce") or 0)
        stage = _safe_stage(row)
        confirmation = str(row.get("confirmation", row.get("confirmation_label","STRONG")))
        strength_value = pd.to_numeric(row.get("strength"), errors="coerce")
        breakout = bool(row.get("factual_breakout", False))
        first = _fmt_time(_first_seen(row), False)
        updated = _fmt_time(row.get("observation_timestamp"), False)
        cls = _direction_class(row)
        momentum_text = "—" if pd.isna(momentum) else f"{float(momentum):+.2f}%"
        momentum_color = "#1be083" if pd.notna(momentum) and float(momentum) > 0 else "#ff626c" if pd.notna(momentum) and float(momentum) < 0 else "#dce5f2"
        strength_text = "—" if pd.isna(strength_value) else f"{float(strength_value):.0f}"
        rows.append(
            f"<tr><td>{i}</td><td><div class='stock'>{_logo(symbol)}{symbol}</div></td>"
            f"<td><span class='badge {cls}'>{direction} · {strength}</span></td>"
            f"<td style='color:{momentum_color};font-weight:950'>{momentum_text}</td>"
            f"<td><div class='progress'><span>{progress:.1f}%</span><span class='rail'><span class='fill {'green' if breakout else ''}' style='width:{min(max(progress,0),100):.0f}%'></span></span></div></td>"
            f"<td><span class='badge blue'>{stage}</span></td><td><span class='badge blue'>{confirmation}</span></td>"
            f"<td style='color:#1be083;font-weight:950'>{strength_text}</td>"
            f"<td style='color:{'#1be083' if breakout else '#71849d'};font-weight:950'>{'YES' if breakout else '—'}</td>"
            f"<td class='time'>{first}</td><td class='time'>{updated}</td></tr>"
        )

    table = (
        '<div class="queue-scroll"><table class="queue"><thead><tr>'
        '<th style="width:4%">#</th><th style="width:14%">STOCK ⓘ</th>'
        '<th style="width:15%">DIRECTION / STRENGTH</th><th style="width:9%">MOMENTUM</th>'
        '<th style="width:13%">STRADDLE PROGRESS</th><th style="width:12%">STAGE</th>'
        '<th style="width:10%">CONFIRMATION</th><th style="width:7%">STRENGTH</th>'
        '<th style="width:7%">BREAKOUT</th><th style="width:9%">FIRST TIME</th><th style="width:9%">UPDATED</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    )
    st.markdown(table, unsafe_allow_html=True)


def _detail(df: pd.DataFrame, key: str) -> None:
    if df.empty or "symbol" not in df.columns:
        st.markdown('<div style="padding:14px;color:#7f93ad">No selected decision.</div>', unsafe_allow_html=True)
        return

    symbols = [str(x).upper() for x in df["symbol"].dropna().tolist()]
    if not symbols:
        return

    selected = st.selectbox("Selected decision", symbols, key=f"{key}_selected")
    row = df[df["symbol"].astype(str).str.upper().eq(selected)].iloc[0]

    direction = str(row.get("direction_label","—")).upper()
    strength_label = str(row.get("strength_label","—")).upper()
    progress = float(pd.to_numeric(row.get("progress"), errors="coerce") or 0)
    momentum = pd.to_numeric(row.get("signed_price_move_pct"), errors="coerce")
    strength = pd.to_numeric(row.get("strength"), errors="coerce")
    stage = _safe_stage(row)
    first = _first_seen(row)
    updated = row.get("observation_timestamp")

    st.markdown(
        '<div class="detail-hero"><div><div class="detail-symbol">'
        f'{_logo(selected)} {selected}</div><div class="detail-sub">First seen: {_fmt_time(first)} · Updated: {_fmt_time(updated)}</div>'
        f'</div><span class="badge {_direction_class(row)}">{direction.title()} · {strength_label.title()}</span></div>',
        unsafe_allow_html=True,
    )

    values = [
        ("STRENGTH", "—" if pd.isna(strength) else f"{float(strength):.0f}", strength_label.title()),
        ("STRADDLE PROGRESS", f"{progress:.1f}%", "Next: Breakout" if progress >= 75 else "Existing SDL stage"),
        ("STAGE", stage, "Existing SDL stage"),
        ("MOMENTUM", _fmt_pct(momentum), f"As of {_fmt_time(updated,False)}"),
    ]
    st.markdown('<div class="metric-grid">' + "".join(
        f'<div class="metric"><div class="metric-label">{a}</div><div class="metric-value">{b}</div><div class="metric-foot">{c}</div></div>'
        for a,b,c in values
    ) + '</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div class="process"><div class="process-title">STRADDLE PROCESS</div>'
        f'<div class="process-value">{progress:.1f}%</div>'
        f'<div class="process-rail"><div class="process-fill" style="width:{min(max(progress,0),100):.0f}%"></div></div>'
        '<div class="process-scale"><span>25%</span><span>50%</span><span>75%</span><span>100% BREAKOUT</span></div></div>',
        unsafe_allow_html=True,
    )

    factors = row.get("factors", []) or []
    if factors:
        factor_html = []
        for factor in factors:
            state = str(getattr(factor,"state",""))
            css = "support" if state == "SUPPORT" else "contradict" if state == "CONTRADICT" else "neutral"
            factor_html.append(f'<div class="factor-row"><span>{getattr(factor,"label","Factor")}</span><b class="{css}">{state}</b></div>')
        st.markdown('<div class="factor-list">' + "".join(factor_html) + '</div>', unsafe_allow_html=True)

    try:
        labels = factor_labels(row.to_dict())
        if labels:
            st.caption(" · ".join(labels))
    except Exception:
        pass


def _news_panel() -> None:
    st.markdown(
        '<div class="news-card"><div class="news-title">STOCK RELATED NEWS (PLANNED)</div>'
        '<span class="news-status">Coming soon</span><div class="news-copy">Real-time stock related news will appear here.</div></div>'
        '<div class="news-card"><div class="news-title">LATEST RESULT (PLANNED)</div>'
        '<span class="news-status">Coming soon</span><div class="news-copy">Latest results and earnings updates will appear here.</div></div>'
        '<div class="news-card"><div class="news-title">IMPACT ANALYSIS (PLANNED)</div>'
        '<span class="news-status">Coming soon</span><div class="news-copy">AI-driven impact analysis of news and results will appear here.</div></div>',
        unsafe_allow_html=True,
    )


def _replay(snapshot_files: list[Path], live_ts: pd.Timestamp) -> None:
    st.markdown(
        '<div class="replay"><div class="replay-title">⌄ INTRADAY REPLAY · same page · Live state remains unchanged</div>'
        '<div class="replay-sub">Replay loads an existing completed snapshot only. Later observations cannot upgrade that replay result.</div>',
        unsafe_allow_html=True,
    )

    dates = sorted({_timestamp(p).date() for p in snapshot_files if pd.notna(_timestamp(p))})
    if not dates:
        st.markdown('<div class="replay-state">No completed SDL snapshots are available.</div></div>', unsafe_allow_html=True)
        return

    default_date = dates[-1]
    chosen_date = st.date_input("Trading day", value=st.session_state.get("replay_date", default_date), key="replay_date")
    day_files = [p for p in snapshot_files if pd.notna(_timestamp(p)) and _timestamp(p).date() == chosen_date]
    day_files.sort(key=_timestamp)

    if day_files:
        times = [_timestamp(p).time().replace(microsecond=0) for p in day_files]
        default_time = st.session_state.get("replay_time", times[-1])
        if default_time not in times:
            default_time = times[-1]
        chosen_time = st.time_input("Snapshot time", value=default_time, key="replay_time")
    else:
        chosen_time = pd.Timestamp("09:25").time()
        st.info("No completed snapshot exists for the selected trading day.")

    if st.button("Load Replay", key="load_replay"):
        eligible = [p for p in day_files if _timestamp(p) <= pd.Timestamp.combine(chosen_date, chosen_time)]
        st.session_state["replay_path"] = str(eligible[-1]) if eligible else ""
        st.rerun()

    replay_path = Path(st.session_state.get("replay_path","")) if st.session_state.get("replay_path") else None
    if replay_path and replay_path.exists():
        replay_ts = _timestamp(replay_path)
        replay_df = _process(replay_path)
        st.markdown(
            f'<div class="replay-state">Replay boundary: {_fmt_time(replay_ts)} · Live snapshot remains {_fmt_time(live_ts)}</div>',
            unsafe_allow_html=True,
        )
        if replay_df.empty:
            st.markdown('<div class="replay-state">No qualified decisions exist in this completed snapshot.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="replay-state">{len(replay_df)} qualified decision(s) in replay snapshot.</div>', unsafe_allow_html=True)
            replay_visible = _filter_df(replay_df, "replay")
            st.markdown('<div class="replay-queue">', unsafe_allow_html=True)
            _queue(replay_visible, limit=50)
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="replay-state">Select a trading day and snapshot time, then Load Replay.</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================================
# SESSION / NAVIGATION
# ============================================================================

if "page" not in st.session_state:
    st.session_state["page"] = "Decision Board"
if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = False
if "queue_limit" not in st.session_state:
    st.session_state["queue_limit"] = 12

snapshot_files = _snapshot_files()
live_path = snapshot_files[-1] if snapshot_files else None
live_ts = _timestamp(live_path) if live_path else pd.NaT
live_df = _process(live_path)

# HEADER
st.markdown('<div class="sdl-header"><div class="sdl-header-grid">', unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="sdl-brand">◉ NTIS SDL</div><div class="sdl-sub">INTRADAY DECISION CENTRE · STRADDLE BREAKOUT</div>', unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="nav-row">', unsafe_allow_html=True)
    n1,n2,n3 = st.columns([1,1.25,.9])
    with n1:
        if st.button("◉ Decision Board", type="primary" if st.session_state["page"]=="Decision Board" else "secondary", use_container_width=True):
            st.session_state["page"]="Decision Board"; st.rerun()
    with n2:
        if st.button("▣ Historical Evidence", type="primary" if st.session_state["page"]=="Historical Evidence" else "secondary", use_container_width=True):
            st.session_state["page"]="Historical Evidence"; st.rerun()
    with n3:
        if st.button("⚙ Settings", type="primary" if st.session_state["page"]=="Settings" else "secondary", use_container_width=True):
            st.session_state["page"]="Settings"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="header-right">', unsafe_allow_html=True)
    a,b,c,d = st.columns([.72,1,.85,.9])
    with a:
        st.markdown('<span class="live-pill"><i></i>LIVE</span>', unsafe_allow_html=True)
    with b:
        now = pd.Timestamp.now()
        st.markdown(f'<div class="clock"><b>{now.strftime("%I:%M:%S %p")}</b><small>{now.strftime("%d %b %Y")}</small></div>', unsafe_allow_html=True)
    with c:
        if st.button("⟳ Refresh", key="header_refresh", use_container_width=True):
            st.rerun()
    with d:
        st.session_state["auto_refresh"] = st.checkbox("Auto Refresh", value=st.session_state["auto_refresh"], key="auto_refresh_checkbox")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div></div>', unsafe_allow_html=True)

# DECISION BOARD
if st.session_state["page"] == "Decision Board":
    first_alert = pd.NaT
    if not live_df.empty:
        seen = [_first_seen(row) for _,row in live_df.iterrows()]
        seen = [x for x in seen if pd.notna(x)]
        first_alert = min(seen) if seen else pd.NaT

    st.markdown(
        '<div class="status-strip"><div class="status-cell"><div class="status-label">FIRST ALERT ⓘ</div>'
        f'<div class="status-value">{_fmt_time(first_alert,False)}</div><div class="status-foot">Data updated {_fmt_time(live_ts,False)}</div></div>'
        '<div class="status-cell" style="text-align:right"><div class="status-label">DATA UPDATED ⓘ</div>'
        f'<div class="status-value green">{_fmt_time(live_ts)}</div><div class="status-foot">Latest completed snapshot</div></div></div>',
        unsafe_allow_html=True,
    )

    _kpis(live_df, live_ts)

    visible = _filter_df(live_df, "live")

    _priority_radar(visible)

    st.markdown('<div class="workspace">', unsafe_allow_html=True)

    st.markdown(
        f'<div class="panel"><div class="panel-head"><div class="panel-title">LIVE QUEUE</div>'
        f'<div class="panel-sub">As of {_fmt_time(live_ts)} · FIRST TIME is immutable</div></div>',
        unsafe_allow_html=True,
    )
    _queue(visible, limit=int(st.session_state["queue_limit"]))
    st.markdown('<div class="view-more">', unsafe_allow_html=True)
    if st.button("View More ⌄", key="view_more"):
        st.session_state["queue_limit"] = min(int(st.session_state["queue_limit"])+12, max(len(visible),12))
        st.rerun()
    st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="panel"><div class="panel-head"><div class="panel-title">STOCK DETAIL</div>'
        '<div class="panel-sub">Selected decision</div></div><div class="detail-body">',
        unsafe_allow_html=True,
    )
    _detail(visible, "live_detail")
    st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="panel"><div class="panel-head"><div class="panel-title">STOCK RELATED NEWS (PLANNED)</div>'
        '<div class="panel-sub">Evidence remains separate from SDL scoring.</div></div>',
        unsafe_allow_html=True,
    )
    _news_panel()
    st.markdown('</div></div>', unsafe_allow_html=True)

    _replay(snapshot_files, live_ts)

elif st.session_state["page"] == "Historical Evidence":
    st.markdown('<div class="section-bar">HISTORICAL EVIDENCE</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#091729;border:1px solid #203653;border-radius:9px;padding:12px;color:#9eb0c7;font-size:9px">'
        'Historical evidence is an audit surface only. It never feeds information backward into Live or Replay.</div>',
        unsafe_allow_html=True,
    )
    try:
        events = load_events(EVENT_CSV)
    except Exception:
        events = pd.DataFrame()
    if events is None or events.empty:
        st.info("No historical SDL evidence records are available.")
    else:
        events = events.copy()
        if "observation_timestamp" in events.columns:
            events["observation_timestamp"] = pd.to_datetime(events["observation_timestamp"], errors="coerce")
            events = events.sort_values("observation_timestamp", ascending=False)
            events["observation_timestamp"] = events["observation_timestamp"].dt.strftime("%d %b %Y, %H:%M:%S")
        keep = [c for c in ["observation_timestamp","symbol","direction","price_chg_pct","breakout_distance","strength"] if c in events.columns]
        st.dataframe(events[keep] if keep else events, use_container_width=True, hide_index=True)

elif st.session_state["page"] == "Settings":
    st.markdown('<div class="section-bar">SETTINGS</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#091729;border:1px solid #203653;border-radius:9px;padding:12px;color:#9eb0c7;font-size:9px">'
        '<b>Presentation controls only.</b> Existing SDL decision and stock-selection logic is not changed here.<br>'
        '<b>Source:</b> Existing configured SDL pipeline source root is used. SDL/app.py remains untouched.</div>',
        unsafe_allow_html=True,
    )
    st.session_state["auto_refresh"] = st.checkbox("Auto Refresh", value=st.session_state["auto_refresh"], key="settings_auto_refresh")
    st.session_state["refresh_seconds"] = st.selectbox("Refresh interval", [5,10,15,30,60], index=1, key="settings_refresh_interval")
    st.caption(f"Configured SDL source root: {getattr(sdl_pipeline, 'INTRADAY_SOURCE_ROOT', getattr(sdl_config, 'INTRADAY_SOURCE_ROOT', ''))}")

# FOOTER
st.markdown(
    '<div class="sdl-footer"><span>NTIS SDL — Intraday Decision Centre</span>'
    '<span>Decision-first · Facts only · No future leakage</span>'
    f'<span>Preview 8587 · Latest completed: {_fmt_time(live_ts)}</span></div>',
    unsafe_allow_html=True,
)
