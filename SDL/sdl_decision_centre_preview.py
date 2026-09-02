from __future__ import annotations

from pathlib import Path
from datetime import datetime
import html
import json
import re
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

import config as sdl_config
import pipeline as sdl_pipeline
from config import EVENT_CSV, STATE_JSON, REQUIRED_EVIDENCE_DIR
from pipeline import (
    discover_historical_snapshots,
    process_latest_snapshot_for_today,
    derive_straddle_values,
)
from prediction_engine import build_current_predictions
from source_loader import load_primary_snapshot, parse_observation_timestamp
from storage import load_events, load_state

IST = "Asia/Kolkata"


def to_ist(value):
    """Normalize dashboard display timestamps to Asia/Kolkata."""
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    try:
        # SDL source/event timestamps are naive local NSE/IST timestamps.
        # Never reinterpret a naive source timestamp as UTC.
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize(IST)
        return ts.tz_convert(IST).tz_localize(None)
    except Exception:
        return pd.NaT



# ============================================================================
# NTIS SDL — FINAL CONSOLIDATED DECISION CENTRE
#
# CONTROLLED PRESENTATION-LAYER REPLACEMENT — 31-Aug-2026
#
# SDL/app.py and the existing SDL decision engine remain authoritative.
# This file changes only dashboard presentation / controls / evidence views.
#
# Source workbooks are READ ONLY.
# No Git write is performed by this deployment package.
# ============================================================================

st.set_page_config(
    page_title="NTIS SDL — Intraday Decision Centre",
    page_icon="SDL",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SETTINGS_FILE = Path(__file__).resolve().parent / ".sdl_dashboard_settings.json"


# ============================================================================
# SETTINGS / SOURCE BINDING
# ============================================================================

def load_ui_settings() -> dict:
    defaults = {
        "source_root": str(getattr(sdl_config, "INTRADAY_SOURCE_ROOT", "")),
        "auto_refresh": False,
        "refresh_seconds": 60,
    }
    try:
        if SETTINGS_FILE.exists():
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                defaults.update(saved)
    except Exception:
        pass
    return defaults


def save_ui_settings(**values) -> None:
    current = load_ui_settings()
    current.update(values)
    try:
        SETTINGS_FILE.write_text(
            json.dumps(current, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception:
        pass


def bind_source_root(root: str) -> tuple[bool, str]:
    candidate = Path(str(root)).expanduser()
    try:
        candidate = candidate.resolve()
    except Exception:
        candidate = candidate.absolute()

    if not candidate.exists():
        return False, f"Source folder does not exist: {candidate}"
    if not candidate.is_dir():
        return False, f"Source path is not a folder: {candidate}"

    # The configured source is an established READ-ONLY repository.
    sdl_config.INTRADAY_SOURCE_ROOT = candidate
    sdl_pipeline.INTRADAY_SOURCE_ROOT = candidate
    return True, str(candidate)


_UI = load_ui_settings()
_source_ok, _source_message = bind_source_root(str(_UI.get("source_root", "")))


# ============================================================================
# APPROVED DARK VISUAL SYSTEM
# ============================================================================

st.markdown(
    r"""
<style>
:root{
  --bg:#050d18;
  --panel:#091729;
  --panel2:#0e1d31;
  --panel3:#13243a;
  --line:#203653;
  --line2:#29476e;
  --text:#eef4fb;
  --muted:#93a6bf;
  --red:#ff3038;
  --green:#18df82;
  --purple:#7a62ff;
  --amber:#ffb21c;
  --cyan:#16cfe2;
  --blue:#6d99ff;
}

header[data-testid="stHeader"],
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
footer{
  display:none!important;
}
[data-testid="stSidebar"]{display:none!important}

.stApp{
  background:
    radial-gradient(circle at 50% -12%,#102b54 0%,transparent 36%),
    linear-gradient(180deg,#050d18 0%,#071321 100%);
  color:var(--text);
}
div[data-testid="stAppViewContainer"]{background:transparent!important}
.block-container{
  max-width:1660px!important;
  padding:10px 18px 22px!important;
}
div[data-testid="stVerticalBlock"]{gap:.34rem!important}
p,label,span,div,button,input,textarea{
  font-family:Inter,Segoe UI,Arial,sans-serif!important;
  box-sizing:border-box;
}

/* ---------- APPROVED APPLICATION HEADER ---------- */
.sdl-header{
  width:100%;
  min-height:70px;
  padding:8px 12px;
  margin:0 0 0;
  background:linear-gradient(105deg,#061126 0%,#0b1c3a 55%,#102a58 100%);
  border:1px solid #29476e;
  border-radius:8px;
  box-shadow:0 8px 26px rgba(0,0,0,.28);
}
.sdl-brand{
  color:#f7faff;
  font-size:20px!important;
  line-height:1.05;
  font-weight:950!important;
}
.sdl-sub{
  color:#b7c5da;
  font-size:9px!important;
  font-weight:800!important;
  letter-spacing:.08em;
  margin-top:4px;
}
.header-nav div[data-testid="stButton"] button,
.header-action 
/* SDL FINAL native control override */
div[data-testid="stButton"] button,
div[data-testid="stButton"] button:hover,
div[data-testid="stButton"] button:focus{
  opacity:1!important;
  background:#0d1b2e!important;
  color:#eef4fb!important;
  border:1px solid #3a5a82!important;
  box-shadow:none!important;
}
div[data-testid="stButton"] button p,
div[data-testid="stButton"] button span{
  color:#eef4fb!important;
  opacity:1!important;
}
div[data-testid="stButton"] button{
  min-height:38px!important;
  border-radius:7px!important;
  font-size:10px!important;
  font-weight:900!important;
  padding:4px 10px!important;
  background:#0d1b2e!important;
  border:1px solid #29405e!important;
  color:#edf4fc!important;
}
.header-nav div[data-testid="stButton"] button[kind="primary"]{
  background:#f02f35!important;
  border-color:#ff5960!important;
  color:#fff!important;
}
.live-pill{
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:8px 10px;
  border:1px solid #155f46;
  background:#08291e;
  color:#4de59b;
  border-radius:999px;
  font-size:9px!important;
  font-weight:950!important;
}
.live-pill i{
  width:7px;height:7px;border-radius:50%;
  background:#1fe184;
  box-shadow:0 0 0 3px rgba(31,225,132,.12);
}
.clock-box{
  text-align:right;
  color:#fff;
  line-height:1.05;
  font-variant-numeric:tabular-nums;
}
.clock-box b{font-size:14px!important}
.clock-box small{
  display:block;
  color:#9aabc2;
  font-size:8px!important;
  margin-top:3px;
}
.header-control div[data-testid="stCheckbox"] label p{
  color:#eef4fb!important;
  font-size:9px!important;
  font-weight:850!important;
}
.header-control div[data-testid="stSelectbox"]>div>div{
  min-height:38px!important;
  background:#101f35!important;
  border:1px solid #29405e!important;
  color:#fff!important;
  font-size:10px!important;
}
.header-control div[data-testid="stSelectbox"] svg{
  fill:#b9c8dc!important;
  color:#b9c8dc!important;
}
.header-control div[data-testid="stButton"] button{
  min-height:38px!important;
  background:#0d1b2e!important;
  border:1px solid #29405e!important;
  color:#edf4fc!important;
}

/* ---------- UTILITY STRIP ---------- */
.utility-strip{
  width:100%;
  min-height:50px;
  padding:6px 10px;
  margin:8px 0 8px;
  background:linear-gradient(105deg,#081a35 0%,#0d2448 55%,#102b58 100%);
  border:1px solid #203b66;
  border-radius:8px;
}
.utility-cell{
  min-height:34px;
  padding:3px 9px;
  border-right:1px solid #203653;
}
.utility-cell:last-child{border-right:0}
.utility-label{
  color:#8096b3;
  font-size:8px!important;
  font-weight:950!important;
  letter-spacing:.10em;
}
.utility-value{
  color:#eef4fb;
  font-size:11px!important;
  font-weight:900!important;
  margin-top:3px;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.utility-value.green{color:#18df82}
.utility-value.amber{color:#ffb21c}
.utility-value.cyan{color:#16cfe2}
.utility-note{color:#8fa2bb;font-size:8px!important;margin-top:2px}

/* ---------- DISTINCT ALERT / UPDATE RIBBON ---------- */
.alert-strip{
  display:grid;
  grid-template-columns:1fr 1fr;
  background:#091729;
  border:1px solid #203653;
  border-radius:8px;
  overflow:hidden;
  margin-bottom:8px;
}
.alert-cell{min-height:64px;padding:9px 13px}
.alert-cell:first-child{border-right:1px solid #203653}
.alert-label{
  color:#a8b8ce;
  font-size:9px!important;
  font-weight:950!important;
  letter-spacing:.12em;
}
.alert-value{
  color:#f1f5fc;
  font-size:16px!important;
  font-weight:950!important;
  margin-top:5px;
  font-variant-numeric:tabular-nums;
}
.alert-value.green{color:#18df82}
.alert-foot{color:#8194ad;font-size:8px!important;margin-top:4px}

/* ---------- KPI RIBBON ---------- */
.kpi-card{
  min-height:82px;
  padding:10px 11px;
  border-radius:8px;
  background:#0d1b2e;
  border:1px solid #233a5d;
  box-shadow:0 5px 15px rgba(0,0,0,.16);
}
.kpi-card.green{border-color:#104d3d}
.kpi-card.red{border-color:#6b242c}
.kpi-card.purple{border-color:#3c2d78}
.kpi-card.amber{border-color:#604612}
.kpi-label{
  color:#aabbd0;
  font-size:9px!important;
  font-weight:950!important;
  letter-spacing:.10em;
}
.kpi-value{
  color:#f5f8ff;
  font-size:27px!important;
  line-height:1;
  font-weight:950!important;
  margin-top:8px;
}
.kpi-foot{color:#8a9ab1;font-size:8px!important;margin-top:6px}

/* ---------- FILTERS ---------- */
.filter-panel{
  background:#091729;
  border:1px solid #203653;
  border-radius:8px;
  padding:9px 11px 10px;
  margin-bottom:8px;
}
/* Live Queue header: title row + one equal-width aligned filter row. */
.live-queue-header-title{
  display:flex;
  align-items:center;
  min-height:44px;
  padding:7px 11px 6px;
  background:#0e1d31;
  border-bottom:1px solid #203653;
}
.live-queue-header-title .panel-title{
  font-size:14px!important;
  line-height:1.05;
}
.live-queue-header-title .panel-meta{
  margin-top:4px;
  font-size:9px!important;
}
.live-queue-filter-row{
  background:#091729;
  border-bottom:1px solid #203653;
  padding:7px 11px 8px;
}
.live-queue-filter-row > div[data-testid="stHorizontalBlock"]{
  align-items:flex-start!important;
}
.live-queue-filter-row .filter-title{
  min-height:15px;
  margin-bottom:5px!important;
}
.live-queue-filter-row div[data-testid="stRadio"] [role="radiogroup"]{
  align-content:flex-start!important;
  min-height:30px;
}
.live-queue-filter-row div[data-testid="stRadio"] [role="radiogroup"] label{
  padding:5px 9px!important;
  min-height:30px!important;
}
.filter-caption{color:#a7b7cc;font-size:11px!important;font-weight:750!important;margin-bottom:7px}
.filter-group{padding:0 9px;border-right:1px solid #1c304a}
.filter-group:first-child{padding-left:1px}
.filter-group:last-child{border-right:0;padding-right:1px}
.live-inline-filter-title{margin-bottom:4px!important;white-space:nowrap}
.filter-title{
  color:#b7c6da;
  font-size:11px!important;
  font-weight:950!important;
  letter-spacing:.10em;
  margin-bottom:5px;
}
div[data-testid="stRadio"]>label{display:none!important}
div[data-testid="stRadio"] [role="radiogroup"]{
  display:flex!important;
  flex-wrap:wrap!important;
  gap:5px!important;
}
div[data-testid="stRadio"] [role="radiogroup"] label{
  background:#0d1b2e!important;
  border:1px solid #29405e!important;
  border-radius:999px!important;
  padding:5px 10px!important;
  min-height:28px!important;
  margin:0!important;
}
div[data-testid="stRadio"] [role="radiogroup"] label p,
div[data-testid="stRadio"] [role="radiogroup"] label span{
  color:#e7eef8!important;
  font-size:11px!important;
  font-weight:850!important;
}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked){
  background:#f02f35!important;
  border-color:#ff5960!important;
}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p,
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) span{
  color:#fff!important;
}

/* V24 UI REFINEMENT: filter text +2px; non-stock queue data +2px. No logic changes. */

/* ---------- PRIORITY RADAR ---------- */
.radar-panel{
  background:#091729;
  border:1px solid #203653;
  border-radius:8px;
  padding:9px 10px;
  margin-bottom:8px;
  box-shadow:0 0 18px rgba(42,105,176,.10);
}
.radar-title{
  color:#e8f0fb;
  font-size:12px!important;
  font-weight:950!important;
  letter-spacing:.10em;
  margin-bottom:6px;
}
.radar-card{
  min-height:82px;
  padding:7px;
  background:#0f1e33;
  border:1px solid #203a5b;
  border-radius:7px;
}
.radar-symbol{color:#f0f5fc;font-size:11px!important;font-weight:950!important}
.radar-meta{color:#a5b5ca;font-size:9px!important;margin-top:3px}
.radar-progress{color:#ffb31c;font-size:15px!important;font-weight:950!important;margin-top:5px}
 .radar-first{color:#8195af;font-size:9px!important;margin-top:3px}
.radar-up{border-color:#0f7550!important;background:#0a211c!important}
.radar-up .radar-symbol{color:#38e58e!important}
.radar-up .radar-meta{color:#9be8c1!important}
.radar-down{border-color:#a33b48!important;background:#241318!important}
.radar-down .radar-symbol{color:#ff6671!important}
.radar-down .radar-meta{color:#ffb0b6!important}

/* ---------- LIVE / REPLAY TABLE ---------- */
.workspace-panel{
  background:#091729;
  border:1px solid #203653;
  border-radius:8px;
  overflow:hidden;
}
.panel-head{padding:9px 11px;background:#0e1d31;border-bottom:1px solid #203653}
.panel-title{color:#edf3fc;font-size:13px!important;font-weight:950!important}
.panel-meta{color:#8fa2bb;font-size:9px!important;margin-top:3px}
.replay-note{color:#b7c6d9;font-size:11px!important;line-height:1.45;margin:5px 0 2px}
.queue-wrap{overflow-x:auto}
.queue-header-note{color:#91a3ba;font-size:9px!important;padding:4px 11px 6px;background:#091729;border-bottom:1px solid #203653}
table.queue{
  width:100%;
  border-collapse:collapse;
  table-layout:fixed;
}
table.queue th{
  background:#13243a;
  color:#a9b8ce;
  font-size:10px!important;
  font-weight:900!important;
  letter-spacing:.025em;
  text-align:left;
  padding:9px 6px;
  border-bottom:1px solid #2a4260;
  white-space:nowrap;
}
table.queue td{
  background:#0b192b;
  color:#e3ebf7;
  font-size:14px!important;
  padding:10px 6px;
  border-bottom:1px solid #1b2c43;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  vertical-align:middle;
}
.stock-cell{display:flex;align-items:center;gap:8px;font-size:12px!important;font-weight:950!important}
.logo{
  width:25px;height:25px;flex:0 0 25px;border-radius:6px;
  background:#fff;color:#17325c;border:1px solid #415675;
  display:flex;align-items:center;justify-content:center;
  font-size:7px!important;font-weight:950!important;
}
.badge{
  display:inline-block;padding:4px 7px;border-radius:5px;
  font-size:12px!important;font-weight:950!important;
  border:1px solid #29405e;background:#0d1b2e;color:#e8eff8;
}
.badge-green{background:#063a29;border-color:#0f7550;color:#38e58e}
.badge-red{background:#3c171e;border-color:#a33b48;color:#ff6671}
.badge-blue{background:#102a50;border-color:#3764a4;color:#bcd0f5}
.badge-amber{background:#3a280b;border-color:#8b6114;color:#ffc650}
.up{color:#18df82!important;font-weight:950!important}
.down{color:#ff5960!important;font-weight:950!important}
.strength{color:#e8eff8;font-weight:950!important}
.breakout{color:#18df82;font-weight:950!important}
.rail{
  display:inline-block;
  width:68px;height:7px;margin-left:7px;
  background:#243750;border-radius:99px;vertical-align:middle;
}
.rail-fill{
  display:block;height:100%;background:#ffb21c;border-radius:99px;
}
.rail-fill.break{background:#18df82}

/* ---------- STOCK DETAIL ---------- */
.detail-panel{
  background:#091729;
  border:1px solid #203653;
  border-radius:8px;
  overflow:hidden;
}
.detail-hero{
  display:flex;justify-content:space-between;align-items:center;gap:10px;
  padding:10px 11px;border-bottom:1px solid #203653;background:#0e1d31;
}
.detail-symbol{color:#f2f6fd;font-size:16px!important;font-weight:950!important}
.detail-sub{color:#8fa2bb;font-size:9px!important;margin-top:4px}
.trader-grid{
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding:9px;
}
.trader-card{
  min-height:64px;padding:8px;background:#0f1e33;
  border:1px solid #203a5b;border-radius:7px;
}
.trader-label{color:#9eb0c8;font-size:8px!important;font-weight:950!important;letter-spacing:.08em}
.trader-value{color:#f3f7fd;font-size:16px!important;font-weight:950!important;margin-top:6px}
.trader-note{color:#7e91aa;font-size:7px!important;margin-top:4px}
.interpretation{
  padding:0 9px 9px;color:#aabbd0;font-size:9px!important;line-height:1.45;
}
.news-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:9px}
.news-panel{
  background:#0b192b;border:1px solid #203653;border-radius:7px;
  padding:8px;min-height:120px;
}
.news-item{
  color:#dbe5f3;font-size:9px!important;line-height:1.35;
  padding:6px 0;border-bottom:1px solid #1b2c43;
}
.news-time{display:block;color:#8095b0;font-size:7px!important;margin-top:3px}
.news-empty{color:#7f92ab;font-size:8px!important;padding:8px 0;line-height:1.4}

/* ---------- EXPANDERS / DATAFRAME ---------- */

/* ---------- FINAL GAP PATCH: EXPANDERS / TYPOGRAPHY ---------- */
div[data-testid="stExpander"] details,
div[data-testid="stExpander"] details[open],
div[data-testid="stExpander"] summary{
  background:#091729!important;
  color:#edf3fc!important;
  border-color:#203653!important;
}
div[data-testid="stExpander"] summary{
  min-height:42px!important;
  padding:10px 12px!important;
}
div[data-testid="stExpander"] summary:hover{
  background:#0e1d31!important;
}
div[data-testid="stExpander"] summary p{
  color:#edf3fc!important;
  font-size:13px!important;
  font-weight:950!important;
  letter-spacing:.02em!important;
}
div[data-testid="stExpander"] summary span{
  font-size:0!important;
  color:transparent!important;
  width:0!important;
  min-width:0!important;
  overflow:hidden!important;
}
div[data-testid="stExpander"] summary span svg{
  display:none!important;
}
div[data-testid="stExpander"] [data-testid="stSelectbox"] label{
  color:#a9b8ce!important;
}
div[data-testid="stExpander"] [data-testid="stSelectbox"]>div>div{
  background:#101f35!important;
  color:#eef4fb!important;
  border:1px solid #29405e!important;
}
div[data-testid="stExpander"] [data-baseweb="select"] *{
  color:#eef4fb!important;
}
div[data-testid="stExpander"] .detail-symbol{
  font-size:20px!important;
  font-weight:950!important;
}
div[data-testid="stExpander"] .detail-sub{
  font-size:10px!important;
  color:#9cafc8!important;
}
div[data-testid="stExpander"] .trader-label{
  font-size:10px!important;
}
div[data-testid="stExpander"] .trader-value{
  font-size:20px!important;
}
div[data-testid="stExpander"] .trader-note{
  font-size:9px!important;
}
div[data-testid="stExpander"] .news-item{
  font-size:10px!important;
}

div[data-testid="stExpander"]{
  background:#091729!important;
  border:1px solid #203653!important;
  border-radius:8px!important;
}
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary p{
  color:#edf3fc!important;
  font-size:13px!important;
  font-weight:950!important;
}
div[data-testid="stButton"] button{
  border-radius:7px!important;
  font-size:10px!important;
  font-weight:900!important;
}
div[data-testid="stDataFrame"]{
  border:1px solid #203653!important;
  border-radius:7px!important;
  overflow:hidden!important;
}
div[data-testid="stDataFrame"] *{font-size:11px!important}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================================
# HELPERS
# ============================================================================

def safe_text(value) -> str:
    return html.escape(str(value), quote=True)


def fmt_time(value, full: bool = False) -> str:
    value = to_ist(value)
    if pd.isna(value):
        return "—"
    return value.strftime("%d %b %Y, %H:%M:%S" if full else "%H:%M:%S")


def pct(value) -> str:
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        return "—"
    return f"{float(value):+.2f}%"


def observation_ts(path: Path) -> pd.Timestamp:
    """
    Return the authoritative source observation timestamp.

    SDL uses the source file's filesystem creation/arrival time as the
    observation timestamp. The filename is deliberately ignored so historical
    and future filename conventions cannot alter chronology.
    """
    try:
        return parse_observation_timestamp(Path(path))
    except Exception:
        return pd.NaT

def snapshot_files(trading_date: str | None = None) -> list[Path]:
    try:
        return sorted(
            [Path(p) for p in discover_historical_snapshots(trading_date)],
            key=lambda p: (observation_ts(p), str(p).lower()),
        )
    except Exception:
        return []


def logo(symbol) -> str:
    text = str(symbol or "").strip().upper()
    if not text or text == "NAN":
        return '<span class="logo">—</span>'
    return f'<span class="logo">{safe_text(text[:4])}</span>'


def _daily_evidence(trading_date: str | None = None) -> pd.DataFrame:
    """Load read-only SDL evidence for one trading date."""
    if not trading_date:
        return pd.DataFrame()
    path = Path(REQUIRED_EVIDENCE_DIR) / f"{str(trading_date)[:10]}.csv"
    try:
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame()
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _evidence_timestamp(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty or "observation_timestamp" not in df.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(df["observation_timestamp"], errors="coerce")


def _source_timestamp_set(trading_date: str | None) -> list[pd.Timestamp]:
    """Return authoritative filesystem observation times for one trading day.

    This is a validation boundary only. It does not calculate or alter SDL
    decisions; it prevents stale/non-source timestamps from being displayed
    as factual event times.
    """
    if not trading_date:
        return []
    values = []
    for path in snapshot_files(str(trading_date)[:10]):
        ts = observation_ts(path)
        if pd.notna(ts):
            values.append(pd.Timestamp(ts))
    return values


def _matches_source_snapshot(ts, source_times: list[pd.Timestamp], tolerance_seconds: float = 2.0) -> bool:
    if ts is None or pd.isna(ts) or not source_times:
        return False
    value = pd.Timestamp(ts)
    return any(abs((value - candidate).total_seconds()) <= tolerance_seconds for candidate in source_times)


def first_alert_map(trading_date: str | None = None) -> dict[str, pd.Timestamp]:
    """Return first primary-gate qualification time from persisted evidence.

    Uses the frozen daily opening base, not each later snapshot's Open field.
    This is display-only timestamp reconstruction; the primary SDL candidate
    engine remains authoritative and is not modified.
    """
    evidence = _daily_evidence(trading_date)
    if evidence.empty:
        return {}

    required = {"Symbol", "current_price", "observation_timestamp"}
    if not required.issubset(evidence.columns):
        return {}

    try:
        state = load_state(STATE_JSON)
    except Exception:
        state = {}
    base_map = (
        state.get("daily_opening_straddles", {}).get(str(trading_date)[:10], {})
        if isinstance(state, dict)
        else {}
    )
    if not base_map:
        return {}

    source_times = _source_timestamp_set(trading_date)
    e = evidence.copy()
    e["Symbol"] = e["Symbol"].astype(str).str.strip().str.upper()
    e["observation_timestamp"] = _evidence_timestamp(e)
    e["current_price"] = pd.to_numeric(e["current_price"], errors="coerce")
    e["_frozen_open"] = e["Symbol"].map(
        {k: v.get("open_price") for k, v in base_map.items()}
    )
    e["_frozen_premium"] = e["Symbol"].map(
        {k: v.get("opening_straddle_premium") for k, v in base_map.items()}
    )
    e["_frozen_open"] = pd.to_numeric(e["_frozen_open"], errors="coerce")
    e["_frozen_premium"] = pd.to_numeric(e["_frozen_premium"], errors="coerce")
    e["price_gate"] = (e["current_price"] - e["_frozen_open"]).abs() / e["_frozen_open"] * 100.0
    e["progress"] = (e["current_price"] - e["_frozen_open"]).abs() / e["_frozen_premium"] * 100.0
    e = e[
        e["Symbol"].ne("")
        & e["observation_timestamp"].notna()
        & e["current_price"].notna()
        & e["_frozen_open"].notna()
        & e["_frozen_premium"].gt(0)
        & e["price_gate"].ge(0.75)
        & e["progress"].ge(25.0)
    ]
    if source_times:
        e = e[e["observation_timestamp"].map(lambda x: _matches_source_snapshot(x, source_times))]
    if e.empty:
        return {}
    return e.groupby("Symbol")["observation_timestamp"].min().to_dict()


def breakout_event_map(trading_date: str | None = None) -> dict[str, pd.Timestamp]:
    """Return the first factual breakout observed in the real source snapshots.

    BREAKOUT TIME is reconstructed only from the existing SDL pipeline's
    frozen-base breakout flag.  No persisted event timestamp is used as the
    authority, because older event files may contain timestamps created by
    earlier timestamp implementations.

    This function is display-only: it does not write state, evidence or event
    files, and it does not alter the primary SDL decision engine.
    """
    if not trading_date:
        return {}

    day = str(trading_date)[:10]
    files = snapshot_files(day)
    if not files:
        return {}

    # The already-frozen daily opening base is mandatory.  Never create a new
    # opening base here merely to populate the dashboard.
    try:
        state = load_state(STATE_JSON)
    except Exception:
        state = {}

    base_map = (
        state.get("daily_opening_straddles", {}).get(day, {})
        if isinstance(state, dict)
        else {}
    )
    if not base_map:
        return {}

    # Source chronology is authoritative.  Each source file is evaluated
    # independently using the EXISTING SDL pipeline functions.  Therefore the
    # dashboard does not duplicate or reinterpret the breakout rule.
    source_breakouts: dict[str, pd.Timestamp] = {}

    for path in files:
        ts = observation_ts(path)
        if pd.isna(ts):
            continue

        try:
            snapshot, _ = load_primary_snapshot(path, ts)
            snapshot = sdl_pipeline.derive_straddle_values(
                snapshot,
                breakout_multiplier=getattr(
                    sdl_config,
                    "BREAKOUT_MULTIPLIER",
                    1.0,
                ),
                current_price_field=getattr(
                    sdl_config,
                    "CURRENT_PRICE_FIELD",
                    "Close",
                ),
            )
            evaluated = sdl_pipeline._apply_frozen_base(
                snapshot,
                base_map,
            )
        except Exception:
            # A malformed/unreadable historical source snapshot must not
            # manufacture a breakout timestamp or affect live decisions.
            continue

        if (
            "Symbol" not in evaluated.columns
            or "standard_straddle_breakout" not in evaluated.columns
        ):
            continue

        mask = (
            evaluated["standard_straddle_breakout"]
            .fillna(False)
            .astype(bool)
        )
        if not mask.any():
            continue

        symbols = (
            evaluated.loc[mask, "Symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        for symbol in symbols:
            if symbol and symbol not in source_breakouts:
                source_breakouts[symbol] = pd.Timestamp(ts)

    return source_breakouts

def add_first_times(df: pd.DataFrame, trading_date: str | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    out["first_trigger_timestamp"] = out["symbol"].map(first_alert_map(trading_date))
    out["breakout_timestamp"] = out["symbol"].map(breakout_event_map(trading_date))
    return out


def first_seen(row: pd.Series) -> pd.Timestamp:
    """Display fallback: historical first trigger, then current observation."""
    for key in (
        "first_trigger_timestamp",
        "first_alert_timestamp",
        "first_seen_timestamp",
        "first_detection_timestamp",
        "trigger_timestamp",
        "decision_timestamp",
        "observation_timestamp",
    ):
        value = pd.to_datetime(row.get(key), errors="coerce")
        if pd.notna(value):
            return value
    return pd.NaT


def frozen_base_from_df(df: pd.DataFrame) -> dict:
    if df is None or df.empty or "Symbol" not in df.columns:
        return {}

    result = {}
    for _, row in df.drop_duplicates("Symbol").iterrows():
        symbol = str(row.get("Symbol", "")).strip().upper()
        op = pd.to_numeric(
            row.get("daily_open_reference"), errors="coerce"
        )
        premium = pd.to_numeric(
            row.get("opening_straddle_premium"), errors="coerce"
        )
        if (
            symbol
            and pd.notna(op)
            and pd.notna(premium)
            and float(premium) > 0
        ):
            result[symbol] = {
                "open_price": float(op),
                "opening_straddle_premium": float(premium),
            }
    return result


def candidates(
    df: pd.DataFrame,
    base: dict | None = None,
    snapshot_ts: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = build_current_predictions(
        df,
        base or frozen_base_from_df(df),
    )
    if out is None or out.empty:
        return pd.DataFrame()

    out = normalize_dashboard_predictions(out)

    # The frozen prediction engine intentionally returns prediction fields
    # only. Re-attach source snapshot fields here for dashboard display.
    # This is presentation-only and does not feed anything back into SDL
    # scoring/qualification.
    try:
        source = df.copy()
        source.columns = [str(c).strip() for c in source.columns]

        if "Symbol" in source.columns and "symbol" in out.columns:
            source["__dashboard_symbol"] = (
                source["Symbol"].astype(str).str.strip().str.upper()
            )
            lookup = (
                source.drop_duplicates("__dashboard_symbol")
                .set_index("__dashboard_symbol")
            )

            for column in source.columns:
                if column == "__dashboard_symbol":
                    continue
                if column in out.columns:
                    # Never overwrite authoritative prediction fields.
                    continue
                out[column] = out["symbol"].map(lookup[column])
    except Exception:
        # Dashboard remains functional even if a source field cannot be
        # reattached; missing source data is displayed as "—".
        pass

    # Canonical dashboard timestamp alias.
    # The source dataframe does not reliably carry observation_timestamp,
    # because the authoritative source observation time belongs to the
    # snapshot file. When supplied by the caller, use that exact timestamp
    # for every row in this snapshot.
    if snapshot_ts is not None and pd.notna(snapshot_ts):
        out["observation_timestamp"] = snapshot_ts
    elif "observation_timestamp" not in out.columns:
        for alias in (
            "source_observation_timestamp",
            "snapshot_timestamp",
            "updated_timestamp",
        ):
            if alias in out.columns:
                out["observation_timestamp"] = out[alias]
                break

    day = None
    if "observation_timestamp" in out.columns:
        ts = pd.to_datetime(
            out["observation_timestamp"], errors="coerce"
        ).dropna()
        if not ts.empty:
            day = ts.iloc[0].date().isoformat()

    return add_first_times(out, day)


def normalize_dashboard_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize compatible prediction fields for dashboard presentation only."""
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df

    out = df.copy()

    # Direction label: prefer authoritative label, otherwise derive from direction.
    if "direction_label" not in out.columns:
        if "direction" in out.columns:
            out["direction_label"] = (
                out["direction"].astype(str).str.upper()
                .map({"UP": "BULLISH", "DOWN": "BEARISH"})
                .fillna(out["direction"].astype(str).str.upper())
            )
        elif "decision" in out.columns:
            s = out["decision"].astype(str).str.upper()
            out["direction_label"] = s.map(
                lambda v: "BULLISH" if "BULLISH" in v or "UP" in v
                else "BEARISH" if "BEARISH" in v or "DOWN" in v
                else "WAIT"
            )
        else:
            out["direction_label"] = "WAIT"

    # Strength label: preserve engine value; derive only when absent.
    if "strength_label" not in out.columns:
        strength = pd.to_numeric(out.get("strength"), errors="coerce")
        out["strength_label"] = strength.map(
            lambda v: (
                "STRONG" if pd.notna(v) and v >= 80 else
                "SUPPORTED" if pd.notna(v) and v >= 65 else
                "DEVELOPING" if pd.notna(v) and v >= 50 else
                "WAIT"
            )
        ).fillna("WAIT")

    # Stage from progress when the presentation alias is absent.
    if "stage" not in out.columns:
        progress = pd.to_numeric(out.get("progress"), errors="coerce")
        out["stage"] = progress.map(
            lambda v: (
                "100%+ BREAKOUT" if pd.notna(v) and v >= 100 else
                "75–<100% APPROACHING" if pd.notna(v) and v >= 75 else
                "50–<75%" if pd.notna(v) and v >= 50 else
                "25–<50% EARLY" if pd.notna(v) and v >= 25 else
                "—"
            )
        )

    if "factual_breakout" not in out.columns:
        progress = pd.to_numeric(out.get("progress"), errors="coerce")
        out["factual_breakout"] = progress.ge(100).fillna(False)

    if "symbol" not in out.columns and "Symbol" in out.columns:
        out["symbol"] = out["Symbol"]

    return out


def breakout_series(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(False, index=df.index if df is not None else [])

    return df.get(
        "factual_breakout",
        pd.Series(False, index=df.index),
    ).fillna(False).astype(bool)


# ============================================================================
# FILTERS — DIRECTLY ABOVE THE QUEUE THEY CONTROL
# ============================================================================

def render_live_queue_filters(df: pd.DataFrame, data_ts) -> pd.DataFrame:
    """Render Live Queue title/meta and its four filters in one native row.

    Presentation-only relocation of the existing filter controls. The same
    options and filtering semantics are retained; Replay continues to use
    the independent render_filters() layout.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    progress_opts = ["All", "25%+", "50%+", "70%+", "75%+", "Breakout"]
    direction_opts = ["All", "Bullish", "Bearish"]
    strength_opts = ["All", "Developing", "Strong", "Supported", "Wait / Conflict"]
    stage_opts = [
        "All", "100%+ BREAKOUT", "25–<50% EARLY", "50–<75%",
        "75–<100% APPROACHING",
    ]

    # Keep the queue title/meta on its own aligned header row.
    # The four existing filters then share one equal-width control row.
    # This is presentation-only; filter options and semantics are unchanged.
    st.markdown(
        '<div class="live-queue-header-title">'
        '<div>'
        '<div class="panel-title">LIVE QUEUE</div>'
        f'<div class="panel-meta">Source snapshot {safe_text(fmt_time(data_ts, True))} · '
        f'{len(df)} qualified · filters below control this queue only.</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(4, gap="small")
    selections = {}

    st.markdown('<div class="live-queue-filter-row">', unsafe_allow_html=True)

    groups = [
        (cols[0], "PROGRESS ⓘ", progress_opts, "progress"),
        (cols[1], "DIRECTION ⓘ", direction_opts, "direction"),
        (cols[2], "STRENGTH ⓘ", strength_opts, "strength"),
        (cols[3], "STAGE ⓘ", stage_opts, "stage"),
    ]
    for col, title, options, key in groups:
        with col:
            st.markdown(
                f'<div class="filter-title live-inline-filter-title">{title}</div>',
                unsafe_allow_html=True,
            )
            selections[key] = st.radio(
                title, options, horizontal=True,
                key=f"live_{key}", label_visibility="collapsed",
            )

    st.markdown('</div>', unsafe_allow_html=True)

    out = df.copy()
    if selections["direction"] != "All":
        out = out[out["direction_label"].astype(str).str.upper().eq(selections["direction"].upper())]
    if selections["strength"] != "All":
        wanted = selections["strength"].upper().split("/")[0].strip()
        out = out[out["strength_label"].astype(str).str.upper().str.startswith(wanted)]
    if selections["stage"] != "All":
        out = out[out["stage"].astype(str).eq(selections["stage"])]
    if selections["progress"] != "All":
        progress = pd.to_numeric(out["progress"], errors="coerce").fillna(0)
        if selections["progress"] == "Breakout":
            out = out[breakout_series(out)]
        else:
            threshold = float(selections["progress"].replace("%+", ""))
            out = out[progress.ge(threshold)]
    return out


def render_filters(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    cols = st.columns(4)

    progress_opts = [
        "All", "25%+", "50%+", "70%+", "75%+", "Breakout"
    ]
    direction_opts = ["All", "Bullish", "Bearish"]
    strength_opts = [
        "All", "Developing", "Strong", "Supported", "Wait / Conflict"
    ]
    stage_opts = [
        "All",
        "100%+ BREAKOUT",
        "25–<50% EARLY",
        "50–<75%",
        "75–<100% APPROACHING",
    ]

    selections = {}

    with cols[0]:
        st.markdown(
            '<div class="filter-group"><div class="filter-title">PROGRESS ⓘ</div>',
            unsafe_allow_html=True,
        )
        selections["progress"] = st.radio(
            "Progress",
            progress_opts,
            horizontal=True,
            key=f"{key_prefix}_progress",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with cols[1]:
        st.markdown(
            '<div class="filter-group"><div class="filter-title">DIRECTION ⓘ</div>',
            unsafe_allow_html=True,
        )
        selections["direction"] = st.radio(
            "Direction",
            direction_opts,
            horizontal=True,
            key=f"{key_prefix}_direction",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with cols[2]:
        st.markdown(
            '<div class="filter-group"><div class="filter-title">STRENGTH ⓘ</div>',
            unsafe_allow_html=True,
        )
        selections["strength"] = st.radio(
            "Strength",
            strength_opts,
            horizontal=True,
            key=f"{key_prefix}_strength",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with cols[3]:
        st.markdown(
            '<div class="filter-group"><div class="filter-title">STAGE ⓘ</div>',
            unsafe_allow_html=True,
        )
        selections["stage"] = st.radio(
            "Stage",
            stage_opts,
            horizontal=True,
            key=f"{key_prefix}_stage",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    out = df.copy()

    if selections["direction"] != "All":
        out = out[
            out["direction_label"].astype(str).str.upper().eq(
                selections["direction"].upper()
            )
        ]

    if selections["strength"] != "All":
        wanted = selections["strength"].upper().split("/")[0].strip()
        out = out[
            out["strength_label"].astype(str).str.upper()
            .str.contains(wanted, regex=False, na=False)
        ]

    p = pd.to_numeric(
        out.get("progress"),
        errors="coerce",
    ).fillna(-1)

    choice = selections["progress"]
    if choice == "25%+":
        out = out[p >= 25]
    elif choice == "50%+":
        out = out[p >= 50]
    elif choice == "70%+":
        out = out[p >= 70]
    elif choice == "75%+":
        out = out[p >= 75]
    elif choice == "Breakout":
        out = out[breakout_series(out)]

    if selections["stage"] != "All":
        p = pd.to_numeric(out.get("progress"), errors="coerce")
        stage = selections["stage"]

        if stage == "100%+ BREAKOUT":
            out = out[breakout_series(out)]
        elif stage == "25–<50% EARLY":
            out = out[(p >= 25) & (p < 50)]
        elif stage == "50–<75%":
            out = out[(p >= 50) & (p < 75)]
        elif stage == "75–<100% APPROACHING":
            out = out[(p >= 75) & (p < 100)]

    return out.reset_index(drop=True)


def badge_class(row: pd.Series) -> str:
    direction = str(row.get("direction_label", "")).upper()
    if direction == "BULLISH":
        return "badge-green"
    if direction == "BEARISH":
        return "badge-red"
    return "badge-amber"


# ============================================================================
# QUEUE TABLE
# ============================================================================

def queue_html(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return (
            '<div style="padding:20px;text-align:center;'
            'color:#8293aa;font-size:12px">'
            'No stocks match the current filters.</div>'
        )

    def first_available(row, aliases):
        for alias in aliases:
            if alias in row.index:
                value = row.get(alias)
                if pd.notna(value) and str(value).strip() not in {"", "nan", "NaT"}:
                    return value
        return None

    def row_time(row, aliases):
        value = first_available(row, aliases)
        if value is None:
            return "—"
        ts = pd.to_datetime(value, errors="coerce")
        return fmt_time(ts) if pd.notna(ts) else safe_text(str(value))

    rows = []

    for i, (_, row) in enumerate(df.iterrows(), 1):
        price = pd.to_numeric(row.get("signed_price_move_pct"), errors="coerce")
        progress = pd.to_numeric(row.get("progress"), errors="coerce")
        strength = pd.to_numeric(row.get("strength"), errors="coerce")

        direction = str(row.get("direction_label", "—"))
        strength_label = str(row.get("strength_label", "—"))
        stage = str(row.get("stage", "—"))
        breakout = bool(row.get("factual_breakout", False))

        first = fmt_time(first_seen(row))
        breakout_value = first_available(
            row,
            [
                "breakout_timestamp",
                "factual_breakout_timestamp",
                "breakout_event_timestamp",
                "breakout_time",
            ],
        )
        breakout_time = fmt_time(breakout_value)
        updated = row_time(
            row,
            [
                "observation_timestamp",
                "source_observation_timestamp",
                "updated_timestamp",
                "snapshot_timestamp",
            ],
        )

        price_class = (
            "up"
            if pd.notna(price) and price > 0
            else "down"
            if pd.notna(price) and price < 0
            else ""
        )
        progress = 0 if pd.isna(progress) else float(progress)
        # Preserve the previously deployed confirmation display.
        confirmation_value = row.get("confirmation")
        if confirmation_value is None or pd.isna(confirmation_value) or str(confirmation_value).strip().lower() in {"", "nan", "nat"}:
            # Current SDL prediction_engine exposes strength_label as the
            # authoritative factor-derived confirmation state. Do not invent
            # a fallback such as STRONG.
            confirmation = str(row.get("strength_label", "—"))
        else:
            confirmation = str(confirmation_value)

        rows.append(
            "<tr>"
            f"<td>{i}</td>"
            f'<td><div class="stock-cell">{logo(row.get("symbol"))}'
            f'<span>{safe_text(str(row.get("symbol","")).upper())}</span></div></td>'
            f'<td><span class="badge {badge_class(row)}">'
            f'{safe_text(direction.title())} · '
            f'{safe_text(strength_label.title())}</span></td>'
            f'<td class="{price_class}">{pct(price)}</td>'
            f'<td><b>{progress:.1f}%</b>'
            f'<span class="rail"><span class="rail-fill '
            f'{"break" if breakout else ""}" '
            f'style="width:{min(max(progress,0),100):.0f}%"></span></span></td>'
            f'<td><span class="badge badge-blue">{safe_text(stage)}</span></td>'
            f'<td><span class="badge badge-blue">{safe_text(confirmation)}</span></td>'
            f'<td class="strength">'
            f'{"—" if pd.isna(strength) else f"{float(strength):.0f}"}'
            f'</td>'
            f'<td class="breakout">{"YES" if breakout else "—"}</td>'
            f'<td>{first}</td>'
            f'<td title="First observed factual breakout in source snapshots">{breakout_time}</td>'
            f'<td>{updated}</td>'
            "</tr>"
        )

    return (
        '<div class="queue-wrap"><table class="queue"><thead><tr>'
        '<th style="width:3%">#</th>'
        '<th style="width:12%">STOCK</th>'
        '<th style="width:15%">DIRECTION / STRENGTH</th>'
        '<th style="width:7%">MOMENTUM</th>'
        '<th style="width:12%">STRADDLE PROGRESS</th>'
        '<th style="width:11%">STAGE</th>'
        '<th style="width:9%">CONFIRMATION</th>'
        '<th style="width:5%">STRENGTH</th>'
        '<th style="width:6%">BREAKOUT</th>'
        '<th style="width:6%">FIRST ALERT</th>'
        '<th style="width:8%">FIRST BREAKOUT TIME</th>'
        '<th style="width:7%">UPDATED</th>'
        '</tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></div>"
    )


# ============================================================================
# TRADER-SPECIFIC STOCK DETAIL
# ============================================================================

def metric(row: pd.Series, aliases: list[str]):
    for name in aliases:
        if name in row.index:
            value = pd.to_numeric(row.get(name), errors="coerce")
            if pd.notna(value):
                return float(value)
    return None


def source_level(row: pd.Series, aliases: list[str]):
    for name in aliases:
        if name in row.index and pd.notna(row.get(name)):
            return row.get(name)
    return None


def future_oi_interpretation(
    direction: str,
    value: float | None,
) -> str:
    if value is None:
        return (
            "Futures OI change is not available in the current source snapshot."
        )

    if value > 0:
        if direction == "BULLISH":
            return (
                "Rising futures OI with bullish price direction "
                "→ long-buildup context."
            )
        if direction == "BEARISH":
            return (
                "Rising futures OI with bearish price direction "
                "→ short-buildup context."
            )

    elif value < 0:
        if direction == "BULLISH":
            return (
                "Falling futures OI with bullish price direction "
                "→ short-covering context."
            )
        if direction == "BEARISH":
            return (
                "Falling futures OI with bearish price direction "
                "→ long-unwinding context."
            )

    return "Futures OI is changing without a clear directional buildup interpretation."


def render_stock_detail(
    df: pd.DataFrame,
    page_key: str,
) -> None:
    if (
        df is None
        or df.empty
        or "symbol" not in df.columns
    ):
        return

    symbols = [
        str(x).upper()
        for x in df["symbol"].dropna().astype(str).tolist()
    ]
    if not symbols:
        return

    with st.expander(
        "STOCK DETAIL · trader-specific context · click to expand",
        expanded=False,
    ):
        selected = st.selectbox(
            "Selected live decision",
            symbols,
            index=0,
            key=f"{page_key}_symbol",
            label_visibility="collapsed",
        )

        row = df[
            df["symbol"].astype(str).str.upper().eq(selected)
        ].iloc[0]

        direction = str(
            row.get("direction_label", "")
        ).upper()

        progress = pd.to_numeric(
            row.get("progress"), errors="coerce"
        )
        strength = pd.to_numeric(
            row.get("strength"), errors="coerce"
        )

        first = pd.to_datetime(
            row.get("first_trigger_timestamp"),
            errors="coerce",
        )
        current_ts = pd.to_datetime(
            row.get("observation_timestamp"),
            errors="coerce",
        )
        breakout_ts = pd.to_datetime(
            row.get("breakout_timestamp"),
            errors="coerce",
        )

        fut = metric(
            row,
            [
                "Futures OI Chg %",
                "Future OI Chg %",
                "Futures OI Change %",
                "Future OI Change %",
                "Futures OI Δ %",
                "Future OI Δ %",
                "Futures OI Change %",
                "Future OI Change %",
                "Futures OI Δ %",
                "Future OI Δ %",
                "Futures OI Change",
                "Future OI Change",
                "futures_oi_chg_pct",
                "future_oi_chg_pct",
                "fut_oi_chg_pct",
                "_futures_oi",
            ],
        )
        pcr = metric(
            row,
            [
                "PCR Chg %",
                "PCR Change %",
                "PCR Δ %",
                "PCR Change",
                "PCR Δ %",
                "PCR Change",
                "pcr_chg_pct",
                "pcr_change_pct",
            ],
        )
        iv = metric(
            row,
            [
                "IV Chg %",
                "IV Change %",
                "IV Δ %",
                "IV Δ %",
                "iv_chg_pct",
                "iv_change_pct",
            ],
        )
        pe_ce = metric(
            row,
            [
                "PE−CE OI Chg %",
                "PE-CE OI Chg %",
                "PE−CE OI Change %",
                "PE-CE OI Change %",
                "PE−CE OI Δ %",
                "PE-CE OI Δ %",
                "Tot PE-CE OI Chg %",
                "pe_minus_ce_oi_chg_pct",
                "pe_ce_oi_chg_pct",
                "pe_minus_ce_oi",
            ],
        )

        support = source_level(
            row,
            [
                "Support",
                "Support Level",
                "support_level",
                "S1",
            ],
        )
        resistance = source_level(
            row,
            [
                "Resistance",
                "Resistance Level",
                "resistance_level",
                "R1",
            ],
        )

        st.markdown(
            f"""
            <div class="detail-hero">
              <div>
                <div class="detail-symbol">
                  {logo(selected)} {safe_text(selected)}
                </div>
                <div class="detail-sub">
                  First alert: {fmt_time(first, True)} · Breakout: {fmt_time(breakout_ts, True)} · Data updated: {fmt_time(current_ts, True)}
                </div>
              </div>
              <span class="badge {badge_class(row)}">
                {safe_text(direction.title())}
                · {safe_text(str(row.get("strength_label","—")).title())}
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cards = [
            ("FUTURES OI Δ", fut),
            ("PCR Δ", pcr),
            ("IV Δ", iv),
            ("PE−CE OI Δ", pe_ce),
            ("SUPPORT", support),
            ("RESISTANCE", resistance),
        ]

        card_html = []

        for label, value in cards:
            if value is None or pd.isna(value):
                shown = "—"
                note = "Feed/source unavailable"
            elif label in {"SUPPORT", "RESISTANCE"}:
                shown = safe_text(value)
                note = "Existing source field"
            else:
                shown = f"{float(value):+.2f}%"
                note = "Existing snapshot field"

            card_html.append(
                f'<div class="trader-card">'
                f'<div class="trader-label">{label}</div>'
                f'<div class="trader-value">{shown}</div>'
                f'<div class="trader-note">{note}</div>'
                f'</div>'
            )

        st.markdown(
            f'<div class="trader-grid">{"".join(card_html)}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="interpretation">'
            f'<b>Futures OI interpretation:</b> '
            f'{safe_text(future_oi_interpretation(direction, fut))}<br>'
            f'<b>Trader use:</b> derivative changes and '
            f'support/resistance are context only; they do not '
            f'modify the frozen SDL decision score.'
            f'</div>',
            unsafe_allow_html=True,
        )

        left, right = st.columns(2)

        with left:
            with st.expander(
                f"STOCK-SPECIFIC NEWS · {selected}",
                expanded=False,
            ):
                stock_news = live_nse_stock_news(selected)
                if stock_news:
                    for item in stock_news[:6]:
                        st.markdown(
                            f'<div class="news-item">'
                            f'{safe_text(item["text"])}'
                            f'<span class="news-time">'
                            f'{safe_text(item["time"])} · '
                            f'{safe_text(impact_hint(item["text"]))}'
                            f'</span></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        '<div class="news-empty">'
                        'No current NSE announcement returned for this symbol, '
                        'or the live feed is temporarily unavailable.'
                        '</div>',
                        unsafe_allow_html=True,
                    )

        with right:
            with st.expander(
                "MAJOR NSE / MARKET NEWS · TODAY / NEXT SESSION",
                expanded=False,
            ):
                market_news = live_nse_market_news()
                if market_news:
                    for item in market_news[:6]:
                        st.markdown(
                            f'<div class="news-item">'
                            f'<b>{safe_text(item["symbol"])}</b> · '
                            f'{safe_text(item["text"])}'
                            f'<span class="news-time">'
                            f'{safe_text(item["time"])} · '
                            f'{safe_text(item["impact"])}'
                            f'</span></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        '<div class="news-empty">'
                        'NSE market-wide announcement feed is temporarily unavailable.'
                        '</div>',
                        unsafe_allow_html=True,
                    )


# ============================================================================
# BEST-EFFORT LIVE NSE NEWS
# ============================================================================

def _nse_json(url: str):
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/150 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.nseindia.com/",
        },
    )

    with urlopen(req, timeout=5) as response:
        return json.loads(
            response.read().decode("utf-8", errors="ignore")
        )


def impact_hint(subject: str) -> str:
    text = str(subject).lower()

    if any(k in text for k in ("order", "bagging", "contract")):
        return "Potential business/catalyst relevance — verify filing details."
    if any(k in text for k in ("result", "financial", "earnings")):
        return "Results-related context — verify reported figures and guidance."
    if any(k in text for k in ("dividend", "bonus", "split", "record date")):
        return "Corporate-action context — verify dates and terms."
    if any(k in text for k in ("board meeting", "meeting", "investor")):
        return "Scheduled corporate event — outcome may change context."
    if any(k in text for k in ("fund raising", "fundraising", "capital")):
        return "Capital/financing context — verify size and terms."

    return "Factual filing context only — no automatic trade signal."


def live_nse_stock_news(symbol: str) -> list[dict]:
    symbol = str(symbol).strip().upper()
    if not symbol:
        return []

    cache = st.session_state.setdefault("nse_stock_news", {})
    now = time.time()
    cached = cache.get(symbol)

    if cached and now - cached.get("at", 0) < 90:
        return cached.get("items", [])

    try:
        payload = _nse_json(
            "https://www.nseindia.com/api/corporate-announcements"
            "?index=equities&symbol=" + quote(symbol)
        )

        rows = (
            payload
            if isinstance(payload, list)
            else payload.get("data", [])
            if isinstance(payload, dict)
            else []
        )

        items = []

        for item in rows[:8]:
            subject = str(
                item.get("desc")
                or item.get("subject")
                or item.get("purpose")
                or "Announcement"
            ).strip()

            stamp = str(
                item.get("an_dt")
                or item.get("broadcastDate")
                or item.get("timestamp")
                or "NSE"
            ).strip()

            if subject:
                items.append({
                    "time": stamp,
                    "text": subject,
                })

        cache[symbol] = {"at": now, "items": items}
        return items

    except Exception:
        cache[symbol] = {"at": now, "items": []}
        return []


def live_nse_market_news() -> list[dict]:
    cache = st.session_state.setdefault("nse_market_news", {})
    now = time.time()
    cached = cache.get("all")

    if cached and now - cached.get("at", 0) < 90:
        return cached.get("items", [])

    try:
        payload = _nse_json(
            "https://www.nseindia.com/api/corporate-announcements"
            "?index=equities"
        )

        rows = (
            payload
            if isinstance(payload, list)
            else payload.get("data", [])
            if isinstance(payload, dict)
            else []
        )

        items = []

        for item in rows[:12]:
            symbol = str(
                item.get("symbol")
                or item.get("symbolName")
                or "NSE"
            ).strip().upper()

            subject = str(
                item.get("desc")
                or item.get("subject")
                or item.get("purpose")
                or "Announcement"
            ).strip()

            stamp = str(
                item.get("an_dt")
                or item.get("broadcastDate")
                or item.get("timestamp")
                or "NSE"
            ).strip()

            if subject:
                items.append({
                    "symbol": symbol,
                    "time": stamp,
                    "text": subject,
                    "impact": impact_hint(subject),
                })

        cache["all"] = {"at": now, "items": items}
        return items

    except Exception:
        cache["all"] = {"at": now, "items": []}
        return []


# ============================================================================
# HISTORICAL EVIDENCE — DATE-WISE FACTUAL LAYER
# ============================================================================

def evidence_dates() -> list[str]:
    root = Path(REQUIRED_EVIDENCE_DIR)

    if not root.exists():
        return []

    dates = []

    for path in root.glob("*.csv"):
        try:
            dates.append(
                pd.Timestamp(path.stem).date().isoformat()
            )
        except Exception:
            continue

    return sorted(set(dates), reverse=True)


def load_evidence_for_date(day: str) -> pd.DataFrame:
    path = Path(REQUIRED_EVIDENCE_DIR) / f"{day}.csv"

    if not path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    if "observation_timestamp" in df.columns:
        df["observation_timestamp"] = pd.to_datetime(
            df["observation_timestamp"],
            errors="coerce",
        )

    return df


def historical_view() -> None:
    st.markdown(
        '<div class="panel-head">'
        '<div class="panel-title">HISTORICAL EVIDENCE</div>'
        '<div class="panel-meta">'
        'Factual historical observations only. '
        'This layer is separate from Intraday Replay.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    dates = evidence_dates()

    if not dates:
        st.info("No stored historical evidence is available yet.")
        return

    day = st.selectbox(
        "Historical trading day",
        dates,
        format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y"),
        key="historical_day",
    )

    df = load_evidence_for_date(day)

    if df.empty:
        st.warning(
            "No evidence rows are stored for the selected day."
        )
        return

    display = df.copy()

    if "observation_timestamp" in display.columns:
        display["observation_timestamp"] = display[
            "observation_timestamp"
        ].dt.strftime("%d %b %Y, %H:%M:%S")

    rename = {
        "observation_timestamp": "OBSERVATION TIME",
        "Symbol": "SYMBOL",
        "breakout_direction": "DIRECTION",
        "Price Chg %": "PRICE CHG %",
        "PCR Chg %": "PCR CHG %",
        "IV Chg %": "IV CHG %",
        "OI Chg %": "OI CHG %",
        "opening_straddle_premium": "OPENING STRADDLE",
        "upper_straddle_breakout_level": "UPPER BREAKOUT",
        "lower_straddle_breakout_level": "LOWER BREAKOUT",
        "standard_straddle_breakout": "BREAKOUT",
    }

    keep = [
        c for c in rename
        if c in display.columns
    ]

    display = display[keep].rename(columns=rename)

    st.caption(
        f"{len(display):,} factual observation rows · "
        f"selected day {pd.Timestamp(day).strftime('%d %b %Y')}."
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=430,
    )


# ============================================================================
# READ-ONLY REPLAY — DIFFERENT FROM HISTORICAL EVIDENCE
# ============================================================================

def replay_snapshot_frame(
    path: Path,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    df, ts = load_primary_snapshot(
        path,
        observation_ts(path),
    )

    state = load_state(STATE_JSON)
    day = ts.date().isoformat()

    base = (
        state.get("daily_opening_straddles", {}).get(day)
        if isinstance(state, dict)
        else None
    )

    # Display-only fallback. Nothing is persisted.
    if not base:
        files = snapshot_files(day)

        if files:
            first_df, _first_ts = load_primary_snapshot(
                files[0],
                observation_ts(files[0]),
            )
            first_df = derive_straddle_values(first_df)
            base = frozen_base_from_df(first_df)

    df = derive_straddle_values(df)
    pred = candidates(df, base or {}, snapshot_ts=ts)

    return pred, ts


def replay_view() -> None:
    with st.expander(
        "INTRADAY REPLAY · HISTORICAL SNAPSHOT · LIVE STATE REMAINS UNCHANGED",
        expanded=False,
    ):
        st.markdown(
            '<div class="panel-meta">'
            'Replay loads one existing completed snapshot only. '
            'It does not append events, rewrite evidence, or alter live state.'
            '</div>',
            unsafe_allow_html=True,
        )

        files = snapshot_files()

        if not files:
            st.info("No Daywise snapshots are available for replay.")
            return

        date_values = sorted(
            {
                observation_ts(p).date().isoformat()
                for p in files
                if pd.notna(observation_ts(p))
            },
            reverse=True,
        )

        day = st.selectbox(
            "Trading day",
            date_values,
            format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y"),
            key="replay_day",
        )

        if not date_values:
            st.info("No snapshots have a valid filesystem creation timestamp for replay.")
            return

        day_files = snapshot_files(day)
        if not day_files:
            st.info("No snapshots are available for the selected trading day.")
            return

        selected_idx = st.selectbox(
            "Snapshot time",
            range(len(day_files)),
            format_func=lambda i: fmt_time(
                observation_ts(day_files[i])
            ),
            key="replay_snapshot_index",
        )

        if selected_idx is None or pd.isna(selected_idx):
            st.info("Select a snapshot time to open Replay.")
            return

        path = day_files[int(selected_idx)]

        pred, ts = replay_snapshot_frame(path)

        replay_ts_text = fmt_time(ts, full=True)
        st.caption(
            f"Replay snapshot: {replay_ts_text} · "
            f"source: {path.name}"
        )

        if pred.empty:
            st.info(
                "No eligible SDL decisions exist in this replay snapshot."
            )
            return

        st.markdown(
            '<div class="filter-panel">'
            '<div class="filter-caption">'
            'REPLAY FILTERS · independent from live feed'
            '</div>',
            unsafe_allow_html=True,
        )

        filtered = render_filters(pred, "replay")

        st.markdown("</div>", unsafe_allow_html=True)

        st.caption(
            f"{len(filtered)} matching replay decision(s)."
        )

        st.markdown(
            '<div class="workspace-panel">'
            '<div class="panel-head">'
            '<div class="panel-title">REPLAY QUEUE</div>'
            f'<div class="panel-meta">'
            f'Snapshot time is immutable: '
            f'{safe_text(fmt_time(ts, full=True))}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            queue_html(filtered),
            unsafe_allow_html=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================================
# LIVE DATA
# ============================================================================

def latest_live() -> tuple[
    Path | None,
    pd.DataFrame,
    pd.Timestamp,
    str,
]:
    try:
        result = process_latest_snapshot_for_today()

        if not result or len(result) != 4:
            return (
                None,
                pd.DataFrame(),
                pd.NaT,
                "No current snapshot.",
            )

        path, _events, df, message = result

        if path is None:
            return (
                None,
                pd.DataFrame(),
                pd.NaT,
                message,
            )

        path = Path(path)
        ts = observation_ts(path)
        pred = candidates(df, snapshot_ts=ts)

        return path, pred, ts, message

    except Exception as exc:
        return (
            None,
            pd.DataFrame(),
            pd.NaT,
            f"{type(exc).__name__}: {exc}",
        )


def render_live() -> None:
    path, pred, data_ts, message = latest_live()

    if path is None:
        st.warning(message)
        return


    now = datetime.now()

    market_open = (
        datetime.strptime("09:15", "%H:%M").time()
    )
    market_close = (
        datetime.strptime("15:30", "%H:%M").time()
    )

    session = (
        "OPEN"
        if market_open <= now.time() <= market_close
        else "CLOSED"
    )

    # Compact live context strip.
    # Source-path and input-filename details are intentionally hidden from
    # the Decision Board; the dashboard remains focused on trader-facing
    # live state and source observation time.
    st.markdown(
        f"""
        <div class="utility-strip">
          <div style="display:grid;grid-template-columns:1.35fr 1fr 1fr">
            <div class="utility-cell">
              <div class="utility-label">LATEST SOURCE SNAPSHOT</div>
              <div class="utility-value cyan">
                {safe_text(fmt_time(data_ts, True))}
              </div>
              <div class="utility-note">Actual source observation time</div>
            </div>
            <div class="utility-cell">
              <div class="utility-label">MARKET SESSION</div>
              <div class="utility-value amber">{session}</div>
              <div class="utility-note">NSE session context</div>
            </div>
            <div class="utility-cell">
              <div class="utility-label">DECISION MODE</div>
              <div class="utility-value">FACTS ONLY</div>
              <div class="utility-note">No dashboard re-scoring</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Presentation guard: never allow a missing optional label to crash
    # the Decision Centre. No decision is recalculated here.
    pred = normalize_dashboard_predictions(pred)

    # Agreed order: KPI ribbon first, Priority Radar second.
    total = len(pred)

    bullish = int(
        (
            pred["direction_label"]
            .astype(str)
            .str.upper()
            == "BULLISH"
        ).sum()
    )

    bearish = int(
        (
            pred["direction_label"]
            .astype(str)
            .str.upper()
            == "BEARISH"
        ).sum()
    )

    strong = int(
        (
            pred["strength_label"]
            .astype(str)
            .str.upper()
            == "STRONG"
        ).sum()
    )

    breakout = int(
        pred["factual_breakout"]
        .fillna(False)
        .sum()
    )

    cards = [
        ("QUALIFIED", total, ""),
        ("BULLISH", bullish, "green"),
        ("BEARISH", bearish, "red"),
        ("STRONG", strong, "purple"),
        ("BREAKOUT", breakout, "amber"),
    ]

    cols = st.columns(5)

    for col, (label, value, cls) in zip(cols, cards):
        with col:
            st.markdown(
                f'<div class="kpi-card {cls}">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div>'
                f'<div class="kpi-foot">Current live decision set</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Priority Radar is a prioritisation view, not a filter.
    radar = pred.sort_values(
        ["factual_breakout", "strength", "progress"],
        ascending=[False, False, False],
    ).head(8)

    st.markdown(
        '<div class="radar-panel">'
        '<div class="radar-title">'
        'PRIORITY RADAR · PRIORITISATION VIEW'
        '</div>',
        unsafe_allow_html=True,
    )

    radar_count = len(radar)
    rcols = st.columns(radar_count) if radar_count else []

    for col, (_, row) in zip(
        rcols,
        radar.iterrows(),
    ):
        with col:
            first = pd.to_datetime(
                row.get("first_trigger_timestamp"),
                errors="coerce",
            )
            direction_text = str(row.get("direction_label", "")).lower()
            radar_class = (
                "radar-up" if direction_text.startswith("bull")
                else "radar-down" if direction_text.startswith("bear")
                else ""
            )

            st.markdown(
                f'<div class="radar-card {radar_class}">'
                f'<div class="radar-symbol">'
                f'{safe_text(row.get("symbol"))}'
                f'</div>'
                f'<div class="radar-meta">'
                f'{safe_text(str(row.get("direction_label","")).title())}'
                f' · '
                f'{safe_text(str(row.get("strength_label","")).title())}'
                f'</div>'
                f'<div class="radar-meta">'
                f'{safe_text(str(row.get("stage","—")))}'
                f'</div>'
                f'<div class="radar-progress">'
                f'{float(row.get("progress",0)):.1f}%'
                f'</div>'
                f'<div class="radar-first">'
                f'First alert: {safe_text(fmt_time(first))}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)

    # The existing Live Queue filters are presented in the queue header row.
    filtered = render_live_queue_filters(pred, data_ts)

    st.markdown(
        '<div class="queue-header-note">'
        'Filtering is independent from Priority Radar and never changes the underlying SDL decision score.'
        '</div>'
        '<div class="workspace-panel">'
        + queue_html(filtered)
        + '</div>',
        unsafe_allow_html=True,
    )

    # Default collapsed; expands into a larger trader-specific workspace.
    render_stock_detail(
        filtered if not filtered.empty else pred,
        "live_detail",
    )

    # Default collapsed; remains on the same page.
    replay_view()


# ============================================================================
# HEADER / NAVIGATION
# ============================================================================

if "page" not in st.session_state:
    st.session_state.page = "decision"

header_cols = st.columns(
    [1.35, 1.05, 1.05, .85, .42, .62, .58, .78, .52]
)

with header_cols[0]:
    st.markdown(
        '<div class="sdl-header">'
        '<div class="sdl-brand">◉ NTIS SDL</div>'
        '<div class="sdl-sub">'
        'INTRADAY DECISION CENTRE · STRADDLE BREAKOUT'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

with header_cols[1]:
    st.markdown('<div class="header-nav">', unsafe_allow_html=True)
    if st.button(
        "▣ Decision Board",
        type=(
            "primary"
            if st.session_state.page == "decision"
            else "secondary"
        ),
        use_container_width=True,
        key="nav_decision",
    ):
        st.session_state.page = "decision"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with header_cols[2]:
    st.markdown('<div class="header-nav">', unsafe_allow_html=True)
    if st.button(
        "▤ Historical Evidence",
        type=(
            "primary"
            if st.session_state.page == "historical"
            else "secondary"
        ),
        use_container_width=True,
        key="nav_history",
    ):
        st.session_state.page = "historical"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with header_cols[3]:
    st.markdown('<div class="header-nav">', unsafe_allow_html=True)
    if st.button(
        "⚙ Settings",
        type=(
            "primary"
            if st.session_state.page == "settings"
            else "secondary"
        ),
        use_container_width=True,
        key="nav_settings",
    ):
        st.session_state.page = "settings"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with header_cols[4]:
    st.markdown(
        '<div class="header-control">'
        '<div class="live-pill"><i></i> LIVE</div>'
        '</div>',
        unsafe_allow_html=True,
    )

with header_cols[5]:
    now = datetime.now()
    st.markdown(
        f'<div class="clock-box">'
        f'<b>{safe_text(now.strftime("%I:%M:%S %p"))}</b>'
        f'<small>{safe_text(now.strftime("%d %b %Y"))}</small>'
        f'</div>',
        unsafe_allow_html=True,
    )

with header_cols[6]:
    st.markdown('<div class="header-control">', unsafe_allow_html=True)
    if st.button(
        "↻ Refresh",
        use_container_width=True,
        key="header_refresh",
    ):
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with header_cols[7]:
    st.markdown('<div class="header-control">', unsafe_allow_html=True)
    auto = st.checkbox(
        "Auto Refresh",
        value=bool(_UI.get("auto_refresh", False)),
        key="auto_refresh_control",
    )
    st.markdown("</div>", unsafe_allow_html=True)

with header_cols[8]:
    st.markdown('<div class="header-control">', unsafe_allow_html=True)
    interval = st.selectbox(
        "Refresh interval",
        [30, 60, 180, 300],
        index=(
            [30, 60, 180, 300].index(
                int(_UI.get("refresh_seconds", 60))
            )
            if int(_UI.get("refresh_seconds", 60))
            in [30, 60, 180, 300]
            else 1
        ),
        format_func=lambda x: f"{x}s",
        key="refresh_interval_control",
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

if (
    auto != bool(_UI.get("auto_refresh", False))
    or int(interval) != int(_UI.get("refresh_seconds", 60))
):
    _UI["auto_refresh"] = bool(auto)
    _UI["refresh_seconds"] = int(interval)
    save_ui_settings(
        auto_refresh=bool(auto),
        refresh_seconds=int(interval),
    )


# ============================================================================
# PAGE BODIES
# ============================================================================

if st.session_state.page == "settings":
    st.markdown(
        '<div class="panel-head">'
        '<div class="panel-title">SETTINGS</div>'
        '<div class="panel-meta">'
        'Presentation controls only. Existing SDL decision/qualification '
        'logic is not changed by dashboard settings.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    current_root = str(
        getattr(
            sdl_pipeline,
            "INTRADAY_SOURCE_ROOT",
            "",
        )
    )

    new_root = st.text_input(
        "Active SDL source data folder",
        value=current_root,
        key="settings_source_root",
    )

    st.caption(
        "Source workbooks are read-only. SDL writes only to its "
        "configured output/state directories."
    )

    a, b = st.columns([.22, .78])

    with a:
        if st.button(
            "Apply source folder",
            type="primary",
            use_container_width=True,
            key="apply_source",
        ):
            ok, msg = bind_source_root(new_root)

            if ok:
                _UI["source_root"] = msg
                save_ui_settings(source_root=msg)
                st.success(
                    f"Source folder applied: {msg}"
                )
                st.rerun()
            else:
                st.error(msg)

    with b:
        st.markdown(
            f'<div class="utility-note" '
            f'style="padding:9px 0;color:#9fb1c8">'
            f'Configured SDL source root: '
            f'{safe_text(current_root)}'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="panel-meta" style="margin-top:12px">'
        'Auto Refresh and interval are persisted by the dashboard. '
        'They only control presentation refresh; they do not change '
        'SDL scoring or qualification.'
        '</div>',
        unsafe_allow_html=True,
    )

elif st.session_state.page == "historical":
    historical_view()

else:
    render_live()


# ============================================================================
# AUTO REFRESH — LAST, AFTER ALL PAGE CONTENT
# ============================================================================

if bool(_UI.get("auto_refresh", False)):
    time.sleep(
        max(
            30,
            int(_UI.get("refresh_seconds", 60)),
        )
    )
    st.rerun()
