from __future__ import annotations

from pathlib import Path
from datetime import datetime
import html
import json
import pickle
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

# ADDITIVE ONLY: isolated Sector Analysis page. Existing SDL logic is untouched.
from Sector_Analysis.sector_page import render_sector_analysis_page

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

# One persisted dashboard working snapshot.  Source workbooks are used only
# to detect/ingest a NEW 5-minute observation; once processed, the dashboard
# serves this persisted result and does not reopen the source workbook.
PROCESSED_LIVE_SNAPSHOT_FILE = (
    Path(__file__).resolve().parent / ".sdl_processed_live_snapshot.pkl"
)

# Persistent chronological day cache. Source workbooks remain READ ONLY;
# replay/live consume this cache once a trading-day observation has been processed.
DAY_POINT_CACHE_SCHEMA = 6
DAY_POINT_IN_TIME_CACHE_FILE = (
    Path(__file__).resolve().parent / ".sdl_day_point_in_time_cache.pkl"
)

def _load_persisted_live_snapshot():
    try:
        if not PROCESSED_LIVE_SNAPSHOT_FILE.exists():
            return None
        with PROCESSED_LIVE_SNAPSHOT_FILE.open("rb") as handle:
            value = pickle.load(handle)
        if not isinstance(value, dict):
            return None
        if not isinstance(value.get("pred"), pd.DataFrame):
            return None
        return value
    except Exception:
        return None

def _save_persisted_live_snapshot(path: Path, ts, pred: pd.DataFrame, message: str) -> None:
    tmp = PROCESSED_LIVE_SNAPSHOT_FILE.with_suffix(".tmp")
    payload = {
        "source_path": str(path) if path is not None else None,
        "observation_timestamp": pd.Timestamp(ts).isoformat() if ts is not None and pd.notna(ts) else None,
        "pred": pred.copy(),
        "message": str(message or ""),
        "evidence_status": "pending",
    }
    try:
        with tmp.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(PROCESSED_LIVE_SNAPSHOT_FILE)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass



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
/* Live Queue header: title/meta at left + four aligned native filter groups. */
.live-queue-header-block{
  min-height:66px;
  padding:8px 4px 6px 1px;
}
.live-queue-header-block .panel-title{
  font-size:14px!important;
  line-height:1.05;
}
.live-queue-header-block .panel-meta{
  margin-top:5px;
  font-size:9px!important;
  line-height:1.35;
  color:#9aaec6;
}
.live-inline-filter-title{
  min-height:16px;
  margin-bottom:5px!important;
  white-space:nowrap;
}
.live-queue-header-block + div{}
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

/* ---------- LIVE QUEUE FILTER REFINEMENT (PRESENTATION ONLY) ----------
   Scoped only to the four Live Queue radios whose keys begin with live_.
   Existing options, state, filtering semantics and all other dashboard
   controls remain unchanged. */
div[data-testid="stRadio"]:has(input[id*="live_progress"]),
div[data-testid="stRadio"]:has(input[id*="live_direction"]),
div[data-testid="stRadio"]:has(input[id*="live_strength"]),
div[data-testid="stRadio"]:has(input[id*="live_stage"]){
  padding-top:0!important;
}
div[data-testid="stRadio"]:has(input[id*="live_progress"]) [role="radiogroup"],
div[data-testid="stRadio"]:has(input[id*="live_direction"]) [role="radiogroup"],
div[data-testid="stRadio"]:has(input[id*="live_strength"]) [role="radiogroup"],
div[data-testid="stRadio"]:has(input[id*="live_stage"]) [role="radiogroup"]{
  gap:6px!important;
  align-items:center!important;
}
div[data-testid="stRadio"]:has(input[id*="live_progress"]) [role="radiogroup"] label,
div[data-testid="stRadio"]:has(input[id*="live_direction"]) [role="radiogroup"] label,
div[data-testid="stRadio"]:has(input[id*="live_strength"]) [role="radiogroup"] label,
div[data-testid="stRadio"]:has(input[id*="live_stage"]) [role="radiogroup"] label{
  min-height:30px!important;
  padding:5px 10px!important;
  border-radius:8px!important;
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.025)!important;
  transition:background .12s ease,border-color .12s ease,box-shadow .12s ease!important;
}
div[data-testid="stRadio"]:has(input[id*="live_progress"]) [role="radiogroup"] label:has(input:checked),
div[data-testid="stRadio"]:has(input[id*="live_direction"]) [role="radiogroup"] label:has(input:checked),
div[data-testid="stRadio"]:has(input[id*="live_strength"]) [role="radiogroup"] label:has(input:checked),
div[data-testid="stRadio"]:has(input[id*="live_stage"]) [role="radiogroup"] label:has(input:checked){
  background:#6d38f0!important;
  border-color:#8b63ff!important;
  box-shadow:0 0 0 1px rgba(139,99,255,.22),0 4px 12px rgba(109,56,240,.18)!important;
}
div[data-testid="stRadio"]:has(input[id*="live_progress"]) [role="radiogroup"] label:hover,
div[data-testid="stRadio"]:has(input[id*="live_direction"]) [role="radiogroup"] label:hover,
div[data-testid="stRadio"]:has(input[id*="live_strength"]) [role="radiogroup"] label:hover,
div[data-testid="stRadio"]:has(input[id*="live_stage"]) [role="radiogroup"] label:hover{
  border-color:#466284!important;
}
.live-queue-header-block{
  min-height:58px;
  padding-top:6px!important;
}
.live-inline-filter-title{
  margin-bottom:3px!important;
  line-height:1.1!important;
}
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
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;padding:9px;
}
.snapshot-context-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;padding:0 9px 9px}
.snapshot-context-card{background:#0b192b;border:1px solid #203653;border-radius:7px;padding:8px;min-height:58px}
.snapshot-context-label{color:#8fa4bd;font-size:9px!important;font-weight:950!important;letter-spacing:.08em}
.snapshot-context-value{color:#eef4fb;font-size:15px!important;font-weight:950!important;margin-top:5px}
.snapshot-context-value.up{color:#18df82!important}
.snapshot-context-value.down{color:#ff5960!important}
.trader-card{
  min-height:64px;padding:8px;background:#0f1e33;
  border:1px solid #203a5b;border-radius:7px;
}
.trader-label{color:#a9bad0;font-size:10px!important;font-weight:950!important;letter-spacing:.08em}
.trader-value{color:#f3f7fd;font-size:19px!important;font-weight:950!important;margin-top:6px;line-height:1.05}
.trader-value.up{color:#18df82!important}
.trader-value.down{color:#ff5960!important}
.trader-value.flat{color:#f3f7fd!important}
.trader-secondary-change{display:inline-block;margin-left:6px;font-size:10px!important;font-weight:900!important;vertical-align:baseline;white-space:nowrap}
.trader-secondary-change.up{color:#18df82!important}
.trader-secondary-change.down{color:#ff5960!important}
.trader-secondary-change.flat{color:#a9bad0!important}
.trader-note{color:#8ea1ba;font-size:10px!important;margin-top:5px}
.interpretation{
  padding:0 9px 9px;color:#aabbd0;font-size:10px!important;line-height:1.45;
}
.news-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:9px}
.news-panel{
  background:#0b192b;border:1px solid #203653;border-radius:7px;
  padding:8px;min-height:120px;
}
.news-item{
  color:#dbe5f3;font-size:12px!important;line-height:1.4;
  padding:6px 0;border-bottom:1px solid #1b2c43;
}
.news-time{display:block;color:#8da1ba;font-size:10px!important;margin-top:4px}
.news-empty{color:#8fa2bb;font-size:11px!important;padding:10px 0;line-height:1.45}

.news-catalyst{
  margin:0 9px 9px;padding:9px 10px;border:1px solid #29476e;border-radius:7px;
  background:#0e1d31;
}
.news-catalyst.major-up{border-color:#0f7550;background:#073324}
.news-catalyst.major-down{border-color:#a33b48;background:#35151c}
.news-catalyst.mixed{border-color:#8b6114;background:#30230b}
.catalyst-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.catalyst-title{color:#eef4fb;font-size:11px!important;font-weight:950!important;letter-spacing:.06em}
.catalyst-star{font-size:18px!important;line-height:1;color:#ffcf33}
.catalyst-bias-up{color:#18df82;font-weight:950!important}
.catalyst-bias-down{color:#ff5960;font-weight:950!important}
.catalyst-bias-neutral{color:#ffb21c;font-weight:950!important}
.catalyst-body{color:#c7d5e6;font-size:11px!important;line-height:1.45;margin-top:4px}
.catalyst-note{color:#8fa2bb;font-size:10px!important;margin-top:5px}
.news-item.major-news{background:rgba(255,193,7,.045);border-left:3px solid #ffcf33;padding-left:8px}
.news-scope{display:inline-block;margin-left:6px;color:#8fa2bb;font-size:9px!important}

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
  font-size:10px!important;
}
div[data-testid="stExpander"] .news-item{
  font-size:12px!important;
}
div[data-testid="stExpander"] .news-time{font-size:10px!important}
div[data-testid="stExpander"] .snapshot-context-value{font-size:16px!important}

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


@st.cache_data(ttl=30, show_spinner=False)
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

@st.cache_data(ttl=30, show_spinner=False)
def snapshot_files(trading_date: str | None = None) -> list[Path]:
    try:
        return sorted(
            [Path(p) for p in discover_historical_snapshots(trading_date)],
            key=lambda p: (observation_ts(p), str(p).lower()),
        )
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)



def _load_day_point_cache() -> dict:
    try:
        if not DAY_POINT_IN_TIME_CACHE_FILE.exists():
            return {}
        with DAY_POINT_IN_TIME_CACHE_FILE.open("rb") as handle:
            value = pickle.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save_day_point_cache(cache: dict) -> None:
    tmp = DAY_POINT_IN_TIME_CACHE_FILE.with_suffix(".tmp")
    try:
        with tmp.open("wb") as handle:
            pickle.dump(cache, handle, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(DAY_POINT_IN_TIME_CACHE_FILE)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _canonical_header_map(columns) -> dict[str, object]:
    return {str(c).strip().casefold(): c for c in columns}


def _named_column(df: pd.DataFrame, *names: str):
    lookup = _canonical_header_map(df.columns)
    for name in names:
        col = lookup.get(str(name).strip().casefold())
        if col is not None:
            return col
    return None


def _numeric_series(df: pd.DataFrame, column) -> pd.Series:
    if column is None:
        return pd.Series(pd.NA, index=df.index, dtype="Float64")
    return pd.to_numeric(
        df[column].astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False),
        errors="coerce",
    )


@st.cache_data(ttl=60, show_spinner=False)




def _day_ivrp_candidates(day: str) -> list[Path]:
    """Find IVR/IVP periodic workbooks by filename, without column positions."""
    root = Path(getattr(sdl_config, "INTRADAY_SOURCE_ROOT", ""))
    if not root.exists():
        return []
    found = []
    patterns = (
        f"IVR-IVP*{day}*.xlsx",
        f"IVR_IVP*{day}*.xlsx",
        f"IVRIVP*{day}*.xlsx",
    )
    for pattern in patterns:
        try:
            found.extend(root.rglob(pattern))
        except Exception:
            continue
    return sorted({Path(x) for x in found}, key=lambda x: (observation_ts(x), str(x).lower()))


def _source_filename_timestamp_key(path: Path) -> str | None:
    """Extract the explicit YYYY-MM-DD_HHMMSS capture token from a source name."""
    if path is None:
        return None
    m = re.search(r"(20\d{2}-\d{2}-\d{2})[_-](\d{6})(?:\D|$)", Path(path).name)
    if not m:
        return None
    return f"{m.group(1)}_{m.group(2)}"


def _normalize_ivrp_export(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize IVR/IVP exports whose first row contains the real headers."""
    if raw is None or raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    out.columns = [str(c).strip() for c in out.columns]
    first = out.iloc[0].astype(str).str.strip().tolist()
    if first and first[0].lower() == "symbol":
        out = out.iloc[1:].copy()
        out.columns = first
        out.columns = [str(c).strip() for c in out.columns]
    return out.reset_index(drop=True)


@st.cache_data(ttl=30, show_spinner=False)
def _read_ivrp_for_timestamp(day: str, target: pd.Timestamp) -> pd.DataFrame:
    """Read authoritative Futures OI evidence from IVR/IVP for one snapshot.

    Matching is deliberately centralized for both LIVE and Replay:
      1) exact capture token (YYYY-MM-DD_HHMMSS), when available;
      2) otherwise the first IVR/IVP workbook arriving from target through
         +300 seconds. Older companions are never substituted.

    The IVR/IVP physical fields ``Total OI Chg`` and ``Total OI Chg (%)`` are
    authoritative for Futures OI Change. Missing evidence remains pending.
    """
    if not day or target is None or pd.isna(target):
        return pd.DataFrame()
    candidates = _day_ivrp_candidates(str(day)[:10])
    if not candidates:
        return pd.DataFrame()

    target = pd.Timestamp(target)
    target_key = target.strftime("%Y-%m-%d_%H%M%S")
    exact_name = []
    forward = []
    for path in candidates:
        ckey = _source_filename_timestamp_key(path)
        if ckey == target_key:
            exact_name.append(path)
            continue
        ts = observation_ts(path)
        if pd.isna(ts):
            continue
        delta = (pd.Timestamp(ts) - target).total_seconds()
        if 0.0 <= delta <= 300.0:
            forward.append((delta, path))

    if exact_name:
        path = sorted(exact_name, key=lambda p: str(p).lower())[0]
    elif forward:
        _, path = sorted(forward, key=lambda x: (x[0], str(x[1]).lower()))[0]
    else:
        return pd.DataFrame()

    try:
        raw = _normalize_ivrp_export(pd.read_excel(path))
        symbol_col = _named_column(raw, "Symbol", "symbol", "Ticker", "ticker")
        # These are the authoritative physical IVR/IVP fields.
        oi_col = _named_column(
            raw,
            "Total OI Chg", "Total OI Change", "total_oi_chg",
            "Fut OI Chg", "Futures OI Chg", "Future OI Chg",
            "fut_oi_chg", "futures_oi_chg",
        )
        oi_pct_col = _named_column(
            raw,
            "Total OI Chg (%)", "Total OI Chg %", "Total OI Change (%)",
            "Total OI Change %", "total_oi_chg_pct",
            "Fut OI Chg %", "Futures OI Chg %", "Future OI Chg %",
            "fut_oi_chg_pct", "futures_oi_chg_pct",
        )
        if symbol_col is None:
            return pd.DataFrame()
        out = pd.DataFrame({
            "symbol": raw[symbol_col].astype(str).str.strip().str.upper(),
            "futures_oi_chg": _numeric_series(raw, oi_col),
            "futures_oi_chg_pct": _numeric_series(raw, oi_pct_col),
        })
        out = out[out["symbol"].ne("") & out["symbol"].ne("NAN")].copy()
        return out.drop_duplicates("symbol")
    except Exception:
        return pd.DataFrame()

def _day_option_evidence(daywise: pd.DataFrame) -> pd.DataFrame:
    """Extract Daywise option/PCR evidence for dashboard presentation.

    Futures OI is intentionally not sourced here: IVR/IVP is authoritative.
    """
    if daywise is None or daywise.empty:
        return pd.DataFrame()
    symbol_col = _named_column(daywise, "Symbol", "symbol", "Ticker", "ticker")
    if symbol_col is None:
        return pd.DataFrame()

    out = pd.DataFrame({
        "symbol": daywise[symbol_col].astype(str).str.strip().str.upper()
    })
    out["futures_oi_chg"] = pd.NA
    out["futures_oi_chg_pct"] = pd.NA

    pece_col = _named_column(
        daywise, "Tot PE-CE OI Chg", "PE-CE OI Chg", "PE_CE_OI_Chg"
    )
    pe_pct_col = _named_column(
        daywise, "Tot PE OI Chg %", "PE OI Chg %", "PE OI Change %"
    )
    ce_pct_col = _named_column(
        daywise, "Tot CE OI Chg %", "CE OI Chg %", "CE OI Change %"
    )
    pcr_pct_col = _named_column(
        daywise, "PCR Chg %", "PCR Change %", "PCR Δ %"
    )

    out["pe_minus_ce_oi_chg"] = _numeric_series(daywise, pece_col)
    pe_pct = _numeric_series(daywise, pe_pct_col)
    ce_pct = _numeric_series(daywise, ce_pct_col)
    out["pe_minus_ce_oi_chg_pct"] = pe_pct - ce_pct
    out["pcr_chg_pct"] = _numeric_series(daywise, pcr_pct_col)

    return out[out["symbol"].ne("") & out["symbol"].ne("NAN")].drop_duplicates("symbol")

def _merge_snapshot_evidence(
    df: pd.DataFrame,
    option_evidence: pd.DataFrame | None,
    futures_evidence: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge one snapshot's Daywise + authoritative IVR/IVP evidence.

    IVR/IVP Futures OI values override any same-named Daywise values whenever
    present. All other requested presentation fields remain Daywise-derived.
    """
    if df is None or df.empty or "symbol" not in df.columns:
        return df, pd.DataFrame()
    opt = option_evidence.copy() if isinstance(option_evidence, pd.DataFrame) else pd.DataFrame()
    fut = futures_evidence.copy() if isinstance(futures_evidence, pd.DataFrame) else pd.DataFrame()

    if opt.empty and fut.empty:
        return df.copy(), pd.DataFrame()
    if opt.empty:
        evidence = fut.copy()
    elif fut.empty:
        evidence = opt.copy()
    else:
        evidence = opt.merge(fut, on="symbol", how="outer", suffixes=("", "_ivrp"))
        for col in ("futures_oi_chg", "futures_oi_chg_pct"):
            ivrp_col = f"{col}_ivrp"
            if ivrp_col in evidence.columns:
                # IVR/IVP is authoritative: use it whenever populated.
                incoming = pd.to_numeric(evidence[ivrp_col], errors="coerce")
                evidence[col] = incoming
                evidence.drop(columns=[ivrp_col], inplace=True)
    return _enrich_snapshot_from_day_cache(df, evidence), evidence


def _enrich_snapshot_from_day_cache(df: pd.DataFrame, evidence: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or evidence is None or evidence.empty or "symbol" not in df.columns:
        return df
    out = df.copy()
    lookup = evidence.drop_duplicates("symbol").set_index("symbol")
    for col in (
        "futures_oi_chg", "futures_oi_chg_pct",
        "pe_minus_ce_oi_chg", "pe_minus_ce_oi_chg_pct", "pcr_chg_pct",
    ):
        if col not in out.columns:
            out[col] = pd.NA
        existing = pd.to_numeric(out[col], errors="coerce")
        incoming = (
            pd.to_numeric(out["symbol"].map(lookup[col]), errors="coerce")
            if col in lookup.columns else pd.Series(pd.NA, index=out.index)
        )
        # Presentation evidence only: fill missing values. IVR/IVP
        # precedence is enforced before this helper by _merge_snapshot_evidence.
        out[col] = existing.where(existing.notna(), incoming)
    return out

@st.cache_data(ttl=60, show_spinner=False)
def build_day_point_in_time_cache(trading_date: str) -> dict:
    """Build/load one complete chronological trading-day cache.

    Each entry contains the already-processed SDL prediction plus the source
    evidence available at that exact observation.  Existing SDL qualification
    logic is reused unchanged; this function only packages its point-in-time
    inputs/results for replay and presentation.
    """
    day = str(trading_date)[:10]
    if not day:
        return {}
    cache = _load_day_point_cache()
    day_cache = cache.get(day, {}) if isinstance(cache.get(day), dict) else {}
    if day_cache.get("cache_schema") != DAY_POINT_CACHE_SCHEMA:
        # Rebuild this day once after the corrected point-in-time evidence mapping.
        # No source files are modified.
        day_cache = {}
    entries = day_cache.get("snapshots", {}) if isinstance(day_cache.get("snapshots"), dict) else {}
    files = snapshot_files(day)
    if not files:
        return day_cache

    state = load_state(STATE_JSON)
    base = state.get("daily_opening_straddles", {}).get(day) if isinstance(state, dict) else None
    if not base:
        first_df, first_ts = load_primary_snapshot(files[0], observation_ts(files[0]))
        first_df = derive_straddle_values(first_df)
        base = frozen_base_from_df(first_df)

    changed = False
    for path in files:
        ts = observation_ts(path)
        if pd.isna(ts):
            continue
        key = pd.Timestamp(ts).isoformat()
        existing_entry = entries.get(key) if isinstance(entries, dict) else None
        existing_pending = bool(
            isinstance(existing_entry, dict)
            and existing_entry.get("evidence_status") == "pending"
        )
        existing_complete = bool(
            isinstance(existing_entry, dict)
            and existing_entry.get("evidence_status") == "complete"
        )
        if key in entries and existing_complete and not existing_pending:
            continue
        try:
            raw, loaded_ts = load_primary_snapshot(path, ts)
            ts = pd.to_datetime(loaded_ts, errors="coerce")
            if pd.isna(ts):
                continue
            raw = derive_straddle_values(raw)
            option_ev = _day_option_evidence(raw)
            future_ev = _read_ivrp_for_timestamp(day, ts)
            pred = candidates(raw, base or {}, snapshot_ts=ts, snapshot_path=None)
            pred, evidence = _merge_snapshot_evidence(pred, option_ev, future_ev)
            futures_available = _futures_evidence_available(future_ev)
            entries[key] = {
                "timestamp": pd.Timestamp(ts).isoformat(),
                "source_path": str(path),
                "pred": pred.copy(),
                "evidence": evidence.copy(),
                "evidence_status": "complete" if futures_available else "pending",
            }
            changed = True
        except Exception:
            continue

    ordered = dict(sorted(entries.items(), key=lambda kv: kv[0]))
    day_cache = {
        "cache_schema": DAY_POINT_CACHE_SCHEMA,
        "trading_date": day,
        "latest_timestamp": next(reversed(ordered), None) if ordered else None,
        "snapshots": ordered,
        "source_count": len(files),
    }
    if changed:
        cache[day] = day_cache
        _save_day_point_cache(cache)
    return day_cache



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


@st.cache_data(ttl=60, show_spinner=False)
def first_alert_map(
    trading_date: str | None = None,
    cutoff_ts: pd.Timestamp | None = None,
) -> dict[str, pd.Timestamp]:
    """Return only carried, source-backed first-alert timestamps.

    Provenance order is: durable SDL ``first_alerts`` state, then required
    evidence.  Neither source is allowed to create an alert time.  A carried
    timestamp is accepted only when it matches an actual source observation
    timestamp for the same trading day and is not later than the selected
    replay cutoff.
    """
    if not trading_date:
        return {}

    source_times = _source_timestamp_set(trading_date)
    if not source_times:
        return {}

    cutoff = pd.Timestamp(cutoff_ts) if cutoff_ts is not None and pd.notna(cutoff_ts) else None
    result: dict[str, pd.Timestamp] = {}

    # ------------------------------------------------------------------
    # 1) Durable SDL first_alerts state — established carried provenance.
    # ------------------------------------------------------------------
    try:
        state = load_state(STATE_JSON)
    except Exception:
        state = {}

    day_state = (
        state.get("first_alerts", {}).get(str(trading_date)[:10], {})
        if isinstance(state, dict)
        else {}
    )
    # Some SDL state layouts store first_alerts under the per-day state.
    if not isinstance(day_state, dict) or not day_state:
        day_state = (
            state.get(str(trading_date)[:10], {}).get("first_alerts", {})
            if isinstance(state, dict) and isinstance(state.get(str(trading_date)[:10]), dict)
            else {}
        )
    if not isinstance(day_state, dict) or not day_state:
        day_state = (
            state.get("decision_state", {}).get(str(trading_date)[:10], {}).get("first_alerts", {})
            if isinstance(state, dict) and isinstance(state.get("decision_state"), dict)
            else {}
        )

    if isinstance(day_state, dict):
        for symbol, payload in day_state.items():
            symbol = str(symbol).strip().upper()
            if not symbol:
                continue
            raw_ts = payload.get("timestamp") if isinstance(payload, dict) else payload
            ts = pd.to_datetime(raw_ts, errors="coerce")
            if pd.isna(ts):
                continue
            if not _matches_source_snapshot(ts, source_times):
                continue
            if cutoff is not None and ts > cutoff:
                continue
            result[symbol] = pd.Timestamp(ts)

    # ------------------------------------------------------------------
    # 2) Required evidence — secondary carried source, never a generator.
    # ------------------------------------------------------------------
    evidence = _daily_evidence(trading_date)
    if (
        not evidence.empty
        and "Symbol" in evidence.columns
        and "observation_timestamp" in evidence.columns
    ):
        alert_aliases = (
            "first_trigger_timestamp",
            "first_alert_timestamp",
            "first_seen_timestamp",
            "first_detection_timestamp",
            "trigger_timestamp",
            "decision_timestamp",
            "alert_timestamp",
            "alert_time",
        )
        alert_column = next((name for name in alert_aliases if name in evidence.columns), None)
        if alert_column is not None:
            e = evidence[["Symbol", "observation_timestamp", alert_column]].copy()
            e["Symbol"] = e["Symbol"].astype(str).str.strip().str.upper()
            e["observation_timestamp"] = _evidence_timestamp(e)
            e["_alert_timestamp"] = pd.to_datetime(e[alert_column], errors="coerce")
            e = e[
                e["Symbol"].ne("")
                & e["observation_timestamp"].notna()
                & e["_alert_timestamp"].notna()
                & (e["_alert_timestamp"] <= e["observation_timestamp"])
            ]
            e = e[
                e["observation_timestamp"].map(lambda x: _matches_source_snapshot(x, source_times))
                & e["_alert_timestamp"].map(lambda x: _matches_source_snapshot(x, source_times))
            ]
            if cutoff is not None:
                e = e[e["_alert_timestamp"] <= cutoff]
            if not e.empty:
                for symbol, ts in e.groupby("Symbol")["_alert_timestamp"].min().items():
                    # Durable state wins when both sources contain a value.
                    result.setdefault(symbol, pd.Timestamp(ts))

    return result


@st.cache_data(ttl=60, show_spinner=False)
def breakout_event_map(
    trading_date: str | None = None,
    cutoff_ts: pd.Timestamp | None = None,
) -> dict[str, pd.Timestamp]:
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
        if cutoff_ts is not None and pd.notna(cutoff_ts):
            if pd.Timestamp(ts) > pd.Timestamp(cutoff_ts):
                break

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

def add_first_times(
    df: pd.DataFrame,
    trading_date: str | None = None,
    cutoff_ts: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    out["first_trigger_timestamp"] = out["symbol"].map(
        first_alert_map(trading_date, cutoff_ts)
    )
    out["breakout_timestamp"] = out["symbol"].map(
        breakout_event_map(trading_date, cutoff_ts)
    )

    # Point-in-time invariant: no carried event may be later than the
    # selected source snapshot.  Invalid future timestamps are suppressed,
    # never shifted, rounded, or replaced with the current time.
    if cutoff_ts is not None and pd.notna(cutoff_ts):
        cutoff = pd.Timestamp(cutoff_ts)
        for column in ("first_trigger_timestamp", "breakout_timestamp"):
            if column in out.columns:
                # A symbol-map with no matching event can create a float64
                # column containing NaN. Convert it to datetime64 before the
                # point-in-time mask so pandas never receives NaT in float64.
                values = pd.to_datetime(out[column], errors="coerce")
                out[column] = values
                out[column] = values.mask(values > cutoff, pd.NaT)
    return out


def first_seen(row: pd.Series) -> pd.Timestamp:
    """Return only an explicit carried first-alert timestamp.

    Never fall back to the current observation timestamp: that would make a
    missing alert look like an alert occurring at the selected snapshot.
    """
    for key in (
        "first_trigger_timestamp",
        "first_alert_timestamp",
        "first_seen_timestamp",
        "first_detection_timestamp",
        "trigger_timestamp",
        "decision_timestamp",
        "alert_timestamp",
        "alert_time",
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


@st.cache_data(ttl=60, show_spinner=False)
def candidates(
    df: pd.DataFrame,
    base: dict | None = None,
    snapshot_ts: pd.Timestamp | None = None,
    snapshot_path: Path | None = None,
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


    return add_first_times(out, day, snapshot_ts)

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

def _parse_optional_number(value: str):
    try:
        text = str(value).strip().replace(",", "")
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def apply_data_filters(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    """Optional numeric filters for the requested OI/PCR table fields only."""
    if df is None or df.empty:
        return df

    with st.expander("DATA FILTERS · OI / PCR", expanded=False):
        cols = st.columns(3)
        specs = [
            (cols[0], "FUTURES OI CHANGE", "futures_oi_chg", [
                "futures_oi_chg", "Futures OI Change", "Future OI Change",
                "Futures OI Δ", "Future OI Δ", "futures_oi_change", "future_oi_change",
            ]),
            (cols[1], "OPTION OI CHANGE", "pe_minus_ce_oi_chg", [
                "pe_minus_ce_oi_chg", "PE_CE_OI_Chg", "PE-CE OI Change",
                "PE−CE OI Change", "PE-CE OI Δ", "PE−CE OI Δ", "pe_minus_ce_oi",
                "pe_ce_oi_change", "pe_minus_ce_oi_change",
            ]),
            (cols[2], "PCR CHANGE %", "pcr_chg_pct", [
                "pcr_chg_pct", "PCR Chg %", "PCR Change %", "PCR Δ %", "PCR_Chg_Pct",
                "pcr_change_pct",
            ]),
        ]
        filters = {}
        for col, label, canonical, aliases in specs:
            with col:
                st.markdown(f'<div class="filter-title">{label}</div>', unsafe_allow_html=True)
                source = next((a for a in aliases if a in df.columns), None)
                if source is None:
                    st.caption("No data")
                    filters[canonical] = (None, None)
                    continue
                vals = pd.to_numeric(df[source], errors="coerce").dropna()
                if vals.empty:
                    st.caption("No data")
                    filters[canonical] = (None, None)
                    continue
                a, b = st.columns(2)
                with a:
                    lo = st.text_input("Min", key=f"{key_prefix}_{canonical}_min", placeholder="Min", label_visibility="collapsed")
                with b:
                    hi = st.text_input("Max", key=f"{key_prefix}_{canonical}_max", placeholder="Max", label_visibility="collapsed")
                filters[canonical] = (_parse_optional_number(lo), _parse_optional_number(hi))

    aliases_by_canonical = {
        "futures_oi_chg": ["futures_oi_chg", "Futures OI Change", "Future OI Change", "Futures OI Δ", "Future OI Δ", "futures_oi_change", "future_oi_change"],
        "pe_minus_ce_oi_chg": ["pe_minus_ce_oi_chg", "PE_CE_OI_Chg", "PE-CE OI Change", "PE−CE OI Change", "PE-CE OI Δ", "PE−CE OI Δ", "pe_minus_ce_oi", "pe_ce_oi_change", "pe_minus_ce_oi_change"],
        "pcr_chg_pct": ["pcr_chg_pct", "PCR Chg %", "PCR Change %", "PCR Δ %", "PCR_Chg_Pct", "pcr_change_pct"],
    }
    out = df.copy()
    for canonical, (lo, hi) in filters.items():
        source = next((a for a in aliases_by_canonical[canonical] if a in out.columns), None)
        if source is None:
            continue
        values = pd.to_numeric(out[source], errors="coerce")
        if lo is not None:
            out = out[values.ge(lo)]
        if hi is not None:
            values = pd.to_numeric(out[source], errors="coerce")
            out = out[values.le(hi)]
    return out


def render_live_queue_filters(df: pd.DataFrame, data_ts) -> pd.DataFrame:
    """Render the Live Queue title and its four filters as one aligned header.

    Presentation-only refinement from V24.  The existing filter options and
    filtering semantics are unchanged.  The left title/meta block is given a
    dedicated column and the four native filter groups occupy the remaining
    header space.
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

    # One five-part header: queue identity on the left, the four existing
    # native filter controls on the right.  No filter option or semantics is
    # changed by this layout.
    cols = st.columns([1.20, 1.04, 0.86, 1.10, 1.36], gap="small")
    selections = {}

    with cols[0]:
        st.markdown(
            '<div class="live-queue-header-block">'
            '<div class="panel-title">LIVE QUEUE</div>'
            f'<div class="panel-meta">Source snapshot {safe_text(fmt_time(data_ts, True))} · '
            f'{len(df)} qualified · filters control this queue only.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    groups = [
        (cols[1], "PROGRESS ⓘ", progress_opts, "progress"),
        (cols[2], "DIRECTION ⓘ", direction_opts, "direction"),
        (cols[3], "STRENGTH ⓘ", strength_opts, "strength"),
        (cols[4], "STAGE ⓘ", stage_opts, "stage"),
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
    return apply_data_filters(out, "live")


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

    out = apply_data_filters(out, key_prefix)
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
        futures_oi = metric(row, [
            "futures_oi_chg", "Futures OI Change", "Future OI Change",
            "Futures OI Δ", "Future OI Δ", "futures_oi_change", "future_oi_change",
        ])
        option_oi = metric(row, [
            "pe_minus_ce_oi_chg", "PE_CE_OI_Chg", "PE-CE OI Change",
            "PE−CE OI Change", "PE-CE OI Δ", "PE−CE OI Δ", "pe_minus_ce_oi",
            "pe_ce_oi_change", "pe_minus_ce_oi_change",
        ])
        pcr_change = metric(row, [
            "pcr_chg_pct", "PCR Chg %", "PCR Change %", "PCR Δ %", "PCR_Chg_Pct",
            "pcr_change_pct",
        ])

        def fmt_oi(value):
            if value is None or pd.isna(value):
                return "—"
            return f"{float(value):+,.0f}"

        def fmt_pct_value(value):
            if value is None or pd.isna(value):
                return "—"
            return f"{float(value):+.2f}%"

        def change_class(value):
            if value is None or pd.isna(value):
                return ""
            return "up" if float(value) > 0 else "down" if float(value) < 0 else ""

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

        futures_delayed = bool(row.get("futures_oi_delayed", False))
        futures_suffix = " D" if futures_delayed and futures_oi is not None and not pd.isna(futures_oi) else ""

        rows.append(
            "<tr>"
            f"<td>{i}</td>"
            f'<td><div class="stock-cell">{logo(row.get("symbol"))}'
            f'<span>{safe_text(str(row.get("symbol","")).upper())}</span></div></td>'
            f'<td><span class="badge {badge_class(row)}">'
            f'{safe_text(direction.title())} · '
            f'{safe_text(strength_label.title())}</span></td>'
            f'<td class="{price_class}">{pct(price)}</td>'
            f'<td class="{change_class(futures_oi)}">{fmt_oi(futures_oi)}{futures_suffix}</td>'
            f'<td class="{change_class(option_oi)}">{fmt_oi(option_oi)}</td>'
            f'<td class="{change_class(pcr_change)}">{fmt_pct_value(pcr_change)}</td>'
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
        '<th style="width:6%">MOMENTUM</th>'
        '<th style="width:7%">FUTURES OI CHG</th>'
        '<th style="width:7%">OPTION OI CHG</th>'
        '<th style="width:7%">PCR CHG %</th>'
        '<th style="width:10%">STRADDLE PROGRESS</th>'
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
                "Futures OI Change",
                "Future OI Change",
                "Futures OI Δ",
                "Future OI Δ",
                "futures_oi_change",
                "future_oi_change",
                "futures_oi_chg",
                "future_oi_chg",
            ],
        )
        fut_pct = metric(
            row,
            [
                "Futures OI Chg %",
                "Future OI Chg %",
                "Futures OI Change %",
                "Future OI Change %",
                "Futures OI Δ %",
                "Future OI Δ %",
                "futures_oi_chg_pct",
                "future_oi_chg_pct",
                "fut_oi_chg_pct",
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
                "PCR_Chg_Pct",
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
                "IV_Chg_Pct",
            ],
        )
        pe_ce = metric(
            row,
            [
                "PE_CE_OI_Chg",
                "PE-CE OI Change",
                "PE−CE OI Change",
                "PE-CE OI Δ",
                "PE−CE OI Δ",
                "pe_minus_ce_oi",
                "pe_ce_oi_change",
                "pe_minus_ce_oi_change",
            ],
        )
        pe_ce_pct = metric(
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
            ],
        )

        support = source_level(
            row,
            [
                "Support",
                "Support Level",
                "support_level",
                "Support Strike",
                "S/R Support",
                "S1",
            ],
        )
        resistance = source_level(
            row,
            [
                "Resistance",
                "Resistance Level",
                "resistance_level",
                "Resistance Strike",
                "S/R Resistance",
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

        snapshot_cards = [
            ("CMP", metric(row, ["Close", "CMP", "Current Price", "close", "current_price"]), "price"),
            ("PRICE CHG %", metric(row, ["Price Chg %", "Price Chg (%)", "Price_Chg_Pct", "price_chg_pct"]), "change"),
            ("ATM STRADDLE %", metric(row, ["ATM Straddle %", "ATM_Straddle_Pct", "atm_straddle_pct"]), "neutral"),
            ("OI CHG %", metric(row, ["OI Chg %", "OI Chg (%)", "OI_Chg_Pct", "oi_chg_pct"]), "change"),
        ]
        snapshot_html = []
        for label, value, kind in snapshot_cards:
            if value is None or pd.isna(value):
                shown = "—"
                cls = ""
            else:
                shown = f"{float(value):+.2f}%" if kind == "change" else f"{float(value):.2f}"
                cls = "up" if kind == "change" and float(value) > 0 else "down" if kind == "change" and float(value) < 0 else ""
            snapshot_html.append(
                f'<div class="snapshot-context-card"><div class="snapshot-context-label">{label}</div>'
                f'<div class="snapshot-context-value {cls}">{shown}</div></div>'
            )
        st.markdown(f'<div class="snapshot-context-grid">{"".join(snapshot_html)}</div>', unsafe_allow_html=True)

        fut = metric(row, ["futures_oi_chg", "Futures OI Change", "Future OI Change", "Futures OI Δ", "Future OI Δ", "futures_oi_change", "future_oi_change", "futures_oi_chg", "future_oi_chg"])
        fut_pct = metric(row, ["futures_oi_chg_pct", "Futures OI Chg %", "Future OI Chg %", "Futures OI Change %", "Future OI Change %", "futures_oi_chg_pct", "future_oi_chg_pct", "fut_oi_chg_pct"])
        pcr_pct = metric(row, ["pcr_chg_pct", "PCR Chg %", "PCR Change %", "PCR Δ %", "PCR_Chg_Pct", "pcr_change_pct"])
        pe_ce = metric(row, ["pe_minus_ce_oi_chg", "PE_CE_OI_Chg", "PE-CE OI Change", "PE−CE OI Change", "PE-CE OI Δ", "PE−CE OI Δ", "pe_minus_ce_oi", "pe_ce_oi_change", "pe_minus_ce_oi_change"])
        pe_ce_pct = metric(row, ["pe_minus_ce_oi_chg_pct", "PE−CE OI Chg %", "PE-CE OI Chg %", "PE−CE OI Change %", "PE-CE OI Change %", "PE−CE OI Δ %", "PE-CE OI Δ %", "pe_minus_ce_oi_chg_pct", "pe_ce_oi_chg_pct"])

        cards = [
            ("FUTURES OI CHANGE", fut, fut_pct),
            ("PCR CHANGE %", pcr_pct, None),
            ("IV Δ", iv, None),
            ("PE−CE OI CHANGE", pe_ce, pe_ce_pct),
            ("SUPPORT", support, None),
            ("RESISTANCE", resistance, None),
        ]

        card_html = []

        for label, value, value_pct in cards:
            if value is None or pd.isna(value):
                shown = "—"
                value_cls = ""
                secondary = ""
                note = "Not supplied by current primary snapshot"
            elif label in {"SUPPORT", "RESISTANCE"}:
                shown = safe_text(value)
                value_cls = ""
                secondary = ""
                note = "Primary snapshot field"
            else:
                numeric_value = float(value)
                value_cls = (
                    "up" if numeric_value > 0
                    else "down" if numeric_value < 0
                    else "flat"
                )
                shown = f"{numeric_value:+,.0f}"
                if label == "FUTURES OI CHANGE" and bool(row.get("futures_oi_delayed", False)):
                    shown += " D"
                if value_pct is not None and pd.notna(value_pct):
                    pct_value = float(value_pct)
                    pct_cls = (
                        "up" if pct_value > 0
                        else "down" if pct_value < 0
                        else "flat"
                    )
                    secondary = (
                        f'<span class="trader-secondary-change {pct_cls}">'
                        f'({pct_value:+.2f}%)</span>'
                    )
                else:
                    secondary = ""
                note = "Primary snapshot field"

            card_html.append(
                f'<div class="trader-card">'
                f'<div class="trader-label">{label}</div>'
                f'<div class="trader-value {value_cls}">{shown}{secondary}</div>'
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
            f'<b>Trader use:</b> derivative changes, support/resistance and news '
            f'catalyst analysis are context layers only; they do not '
            f'modify the frozen SDL decision score.'
            f'</div>',
            unsafe_allow_html=True,
        )

        stock_news = live_nse_stock_news(selected)
        market_news = live_nse_market_news()
        news_analysis = analyze_news_catalyst(selected, row, stock_news, market_news)
        st.markdown(catalyst_panel_html(news_analysis), unsafe_allow_html=True)

        left, right = st.columns(2)

        with left:
            with st.expander(
                f"STOCK-SPECIFIC NEWS · {selected}",
                expanded=False,
            ):
                if stock_news:
                    major_texts = {x.get("text") for x in news_analysis.get("major_items", [])}
                    for item in stock_news[:6]:
                        is_major = item.get("text") in major_texts
                        cls = "news-item major-news" if is_major else "news-item"
                        star = "★ " if is_major else ""
                        st.markdown(
                            f'<div class="{cls}">'
                            f'{star}{safe_text(item["text"])}'
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
                if market_news:
                    major_texts = {x.get("text") for x in news_analysis.get("major_items", [])}
                    for item in market_news[:6]:
                        is_major = item.get("text") in major_texts
                        cls = "news-item major-news" if is_major else "news-item"
                        star = "★ " if is_major else ""
                        st.markdown(
                            f'<div class="{cls}">'
                            f'{star}<b>{safe_text(item["symbol"])}</b> · '
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


POSITIVE_NEWS_TERMS = (
    "order", "contract", "award", "commission", "commissioned", "capacity",
    "project", "investment", "acquisition", "partnership", "expansion",
    "approval", "win", "growth", "profit", "earnings", "results",
    "upgrade", "tariff", "renewable", "solar", "transmission", "record",
)
NEGATIVE_NEWS_TERMS = (
    "loss", "decline", "downgrade", "penalty", "fine", "default", "fraud",
    "litigation", "dispute", "investigation", "resignation", "delay", "cancel",
    "cancellation", "cut", "weak", "miss", "warning", "regulatory action",
)
MAJOR_NEWS_TERMS = (
    "order", "contract", "award", "commissioned", "capacity", "acquisition",
    "fund raising", "fundraising", "capital", "results", "earnings", "profit",
    "loss", "approval", "regulatory", "investigation", "penalty", "tariff",
    "merger", "stake", "project", "investment", "guidance", "rating",
)
GLOBAL_NEWS_TERMS = (
    "iran", "middle east", "oil", "crude", "brent", "fed", "federal reserve",
    "us rates", "tariff", "china", "global", "geopolitical", "war", "monsoon",
)
SECTOR_NEWS_TERMS = (
    "power", "utilities", "energy", "renewable", "solar", "wind", "grid",
    "transmission", "banking", "pharma", "auto", "steel", "metal", "it sector",
)


def _news_terms(text: str, terms: tuple[str, ...]) -> int:
    value = str(text or "").lower()
    return sum(1 for term in terms if term in value)


def _news_direction(text: str) -> int:
    value = str(text or "").lower()
    pos = _news_terms(value, POSITIVE_NEWS_TERMS)
    neg = _news_terms(value, NEGATIVE_NEWS_TERMS)
    if pos > neg:
        return 1
    if neg > pos:
        return -1
    return 0


def _news_scope(text: str, company: bool = False) -> str:
    value = str(text or "").lower()
    if company:
        return "COMPANY"
    if _news_terms(value, GLOBAL_NEWS_TERMS):
        return "GLOBAL / MACRO"
    if _news_terms(value, SECTOR_NEWS_TERMS):
        return "SECTOR / THEME"
    return "MARKET / DOMESTIC"


def analyze_news_catalyst(symbol: str, row: pd.Series, stock_news: list[dict], market_news: list[dict]) -> dict:
    """Presentation-only news catalyst layer.

    It does not alter SDL scoring or qualification. It compares available
    announcement direction with today's frozen SDL direction/price context.
    """
    symbol = str(symbol or "").strip().upper()
    direction = str(row.get("direction_label", "")).upper()
    price_change = pd.to_numeric(row.get("Price Chg %"), errors="coerce")
    if pd.isna(price_change):
        price_change = pd.to_numeric(row.get("Price_Chg_Pct"), errors="coerce")
    if pd.isna(price_change):
        price_change = pd.to_numeric(row.get("price_chg_pct"), errors="coerce")

    candidates = []
    for item in stock_news or []:
        text = str(item.get("text", "")).strip()
        if text:
            candidates.append((text, True, item.get("time", "NSE")))

    for item in market_news or []:
        text = str(item.get("text", "")).strip()
        item_symbol = str(item.get("symbol", "")).strip().upper()
        if not text:
            continue
        # Keep company-specific market feed items and broader sector/macro items.
        if item_symbol == symbol or _news_terms(text, GLOBAL_NEWS_TERMS + SECTOR_NEWS_TERMS):
            candidates.append((text, False, item.get("time", "NSE")))

    scored = []
    for text, company, stamp in candidates:
        bias = _news_direction(text)
        major_hits = _news_terms(text, MAJOR_NEWS_TERMS)
        if bias == 0 and major_hits == 0:
            continue
        score = min(5, major_hits + (1 if bias else 0))
        scored.append({
            "text": text,
            "bias": bias,
            "score": score,
            "major": score >= 3,
            "scope": _news_scope(text, company),
            "time": stamp,
        })

    scored.sort(key=lambda x: (x["major"], x["score"]), reverse=True)
    major = [x for x in scored if x["major"]]
    top = scored[:3]

    news_bias = 0
    for item in top:
        news_bias += item["bias"] * max(1, item["score"])
    news_bias = 1 if news_bias > 0 else -1 if news_bias < 0 else 0

    market_direction = 1 if direction.startswith("BULL") else -1 if direction.startswith("BEAR") else 0
    if pd.notna(price_change) and price_change != 0:
        market_direction = 1 if float(price_change) > 0 else -1

    if news_bias and market_direction:
        alignment = "ALIGNED" if news_bias == market_direction else "CONTRARY"
    else:
        alignment = "NEUTRAL"

    if news_bias > 0:
        impact = "POSITIVE"
    elif news_bias < 0:
        impact = "NEGATIVE"
    else:
        impact = "NEUTRAL"

    return {
        "major": bool(major),
        "impact": impact,
        "alignment": alignment,
        "items": top,
        "major_items": major[:2],
        "headline": major[0]["text"] if major else (top[0]["text"] if top else ""),
    }


def catalyst_badge(analysis: dict) -> str:
    if not analysis.get("major"):
        return ""
    impact = analysis.get("impact")
    alignment = analysis.get("alignment")
    if impact == "POSITIVE":
        return '<span class="catalyst-star" title="Major positive news catalyst">★</span>'
    if impact == "NEGATIVE":
        return '<span class="catalyst-star" title="Major negative news catalyst">★</span>'
    return '<span class="catalyst-star" title="Major mixed/neutral news catalyst">★</span>'


def catalyst_panel_html(analysis: dict) -> str:
    if not analysis.get("major"):
        return (
            '<div class="news-catalyst">'
            '<div class="catalyst-head"><div class="catalyst-title">NEWS CATALYST</div>'
            '<div class="catalyst-bias-neutral">NO MATERIAL CATALYST DETECTED</div></div>'
            '<div class="catalyst-body">No major available news item is strong enough to explain today\'s move. News absence is valid and does not change the SDL decision.</div>'
            '<div class="catalyst-note">Presentation layer only · no SDL re-scoring</div>'
            '</div>'
        )
    impact = analysis.get("impact", "NEUTRAL")
    alignment = analysis.get("alignment", "NEUTRAL")
    cls = "major-up" if impact == "POSITIVE" else "major-down" if impact == "NEGATIVE" else "mixed"
    bias_cls = "catalyst-bias-up" if impact == "POSITIVE" else "catalyst-bias-down" if impact == "NEGATIVE" else "catalyst-bias-neutral"
    scope = analysis.get("major_items", [{}])[0].get("scope", "NEWS") if analysis.get("major_items") else "NEWS"
    return (
        f'<div class="news-catalyst {cls}">'
        f'<div class="catalyst-head"><div class="catalyst-title">★ MAJOR NEWS CATALYST · {safe_text(scope)}</div>'
        f'<div class="{bias_cls}">{impact} · {alignment}</div></div>'
        f'<div class="catalyst-body">{safe_text(analysis.get("headline", ""))}</div>'
        '<div class="catalyst-note">Compared with today\'s price direction/SDL direction · does not modify the frozen decision score</div>'
        '</div>'
    )


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


def _process_single_snapshot_for_dashboard(
    path: Path,
    ts: pd.Timestamp,
    df: pd.DataFrame,
    message: str = "",
) -> tuple[pd.DataFrame, str]:
    """Materialize one snapshot for both LIVE and Replay using one evidence path."""
    ts = pd.to_datetime(ts, errors="coerce")
    if path is None or pd.isna(ts) or df is None or df.empty:
        return pd.DataFrame(), "No current snapshot."

    day = ts.date().isoformat()
    state = load_state(STATE_JSON)
    base = state.get("daily_opening_straddles", {}).get(day) if isinstance(state, dict) else None
    if not base:
        base = frozen_base_from_df(derive_straddle_values(df))

    raw = derive_straddle_values(df)
    pred = candidates(raw, base or {}, snapshot_ts=ts, snapshot_path=None)
    option_evidence = _day_option_evidence(raw)
    futures_evidence = _read_ivrp_for_timestamp(day, ts)
    pred, evidence = _merge_snapshot_evidence(pred, option_evidence, futures_evidence)
    futures_available = _futures_evidence_available(futures_evidence)

    _upsert_day_point_cache_entry(
        day, ts, path, pred, evidence,
        "complete" if futures_available else "pending",
    )
    return pred, str(message or "")


def _futures_evidence_available(evidence: pd.DataFrame | None) -> bool:
    if evidence is None or evidence.empty:
        return False
    return (
        "futures_oi_chg" in evidence.columns
        and pd.to_numeric(evidence["futures_oi_chg"], errors="coerce").notna().any()
    ) or (
        "futures_oi_chg_pct" in evidence.columns
        and pd.to_numeric(evidence["futures_oi_chg_pct"], errors="coerce").notna().any()
    )


def _upsert_day_point_cache_entry(
    day: str,
    ts: pd.Timestamp,
    path: Path,
    pred: pd.DataFrame,
    evidence: pd.DataFrame,
    evidence_status: str,
) -> None:
    """Persist exactly one point-in-time record without rebuilding the day."""
    try:
        cache = _load_day_point_cache()
        day_cache = cache.get(day, {}) if isinstance(cache.get(day), dict) else {}
        entries = day_cache.get("snapshots", {}) if isinstance(day_cache.get("snapshots"), dict) else {}
        key = pd.Timestamp(ts).isoformat()
        entries[key] = {
            "timestamp": key,
            "source_path": str(path),
            "pred": pred.copy(),
            "evidence": evidence.copy() if isinstance(evidence, pd.DataFrame) else pd.DataFrame(),
            "evidence_status": str(evidence_status or "pending"),
        }
        ordered = dict(sorted(entries.items(), key=lambda kv: kv[0]))
        cache[day] = {
            "cache_schema": DAY_POINT_CACHE_SCHEMA,
            "trading_date": day,
            "latest_timestamp": next(reversed(ordered), None) if ordered else None,
            "snapshots": ordered,
            "source_count": day_cache.get("source_count", 0),
        }
        _save_day_point_cache(cache)
    except Exception:
        pass

@st.cache_data(ttl=300, show_spinner=False)
def replay_snapshot_frame(
    path: Path,
    snapshot_ts: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    ts = pd.to_datetime(snapshot_ts, errors="coerce")
    if pd.isna(ts):
        ts = observation_ts(path)
    day = pd.Timestamp(ts).date().isoformat() if pd.notna(ts) else ""
    key = pd.Timestamp(ts).isoformat() if pd.notna(ts) else ""

    cache = _load_day_point_cache()
    day_cache = cache.get(day, {}) if isinstance(cache, dict) else {}
    entries = day_cache.get("snapshots", {}) if isinstance(day_cache.get("snapshots"), dict) else {}
    entry = entries.get(key)

    if isinstance(entry, dict) and isinstance(entry.get("pred"), pd.DataFrame):
        replay_pred = entry["pred"].copy()
        status = str(entry.get("evidence_status", "pending")).lower()
        # Pending means the Daywise snapshot is known but IVR/IVP had not yet
        # arrived. Retry only the same authoritative companion resolver.
        if status != "complete":
            futures_evidence = _read_ivrp_for_timestamp(day, pd.Timestamp(ts))
            if not futures_evidence.empty:
                option_evidence = entry.get("evidence")
                replay_pred, evidence = _merge_snapshot_evidence(
                    replay_pred,
                    option_evidence if isinstance(option_evidence, pd.DataFrame) else pd.DataFrame(),
                    futures_evidence,
                )
                status = "complete" if _futures_evidence_available(futures_evidence) else "pending"
                _upsert_day_point_cache_entry(day, pd.Timestamp(ts), path, replay_pred, evidence, status)
        return replay_pred, pd.Timestamp(entry.get("timestamp", ts))

    # Uncached point: materialize it through the exact same path used by LIVE.
    df, loaded_ts = load_primary_snapshot(path, ts)
    ts = pd.to_datetime(loaded_ts, errors="coerce")
    if pd.isna(ts):
        return pd.DataFrame(), pd.NaT
    state = load_state(STATE_JSON)
    base = state.get("daily_opening_straddles", {}).get(day) if isinstance(state, dict) else None
    if not base:
        files = snapshot_files(day)
        if files:
            first_df, _ = load_primary_snapshot(files[0], observation_ts(files[0]))
            base = frozen_base_from_df(derive_straddle_values(first_df))
    raw = derive_straddle_values(df)
    pred = candidates(raw, base or {}, snapshot_ts=ts, snapshot_path=None)
    option_evidence = _day_option_evidence(raw)
    futures_evidence = _read_ivrp_for_timestamp(day, ts)
    pred, evidence = _merge_snapshot_evidence(pred, option_evidence, futures_evidence)
    status = "complete" if _futures_evidence_available(futures_evidence) else "pending"
    _upsert_day_point_cache_entry(day, pd.Timestamp(ts), path, pred, evidence, status)
    return pred, pd.Timestamp(ts)

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

        pred, ts = replay_snapshot_frame(
            path,
            observation_ts(path),
        )

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

        # Replay uses the same presentation/filter layer as Live Queue.
        # The underlying prediction snapshot remains immutable.
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
def _hydrate_live_from_point_cache(
    day: str,
    ts: pd.Timestamp,
    pred: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    """Use the exact persisted snapshot record as the LIVE presentation source."""
    if pred is None or pred.empty or pd.isna(ts):
        return pred, "pending"
    try:
        cache = _load_day_point_cache()
        day_cache = cache.get(day, {}) if isinstance(cache, dict) else {}
        entries = day_cache.get("snapshots", {}) if isinstance(day_cache.get("snapshots"), dict) else {}
        entry = entries.get(pd.Timestamp(ts).isoformat())
        if not isinstance(entry, dict):
            return pred, "pending"
        cached_pred = entry.get("pred")
        if not isinstance(cached_pred, pd.DataFrame) or cached_pred.empty:
            return pred, str(entry.get("evidence_status", "pending"))
        status = str(entry.get("evidence_status", "pending")).lower()
        # Cached record is authoritative for this exact snapshot. It already
        # contains the unified Daywise + IVR/IVP materialization.
        return cached_pred.copy(), ("complete" if _futures_evidence_available(entry.get("evidence")) else status)
    except Exception:
        return pred, "pending"

# ============================================================================
# LIVE-ONLY FUTURES / IVR-IVP RESOLVER
# ============================================================================
# Replay remains frozen on _read_ivrp_for_timestamp(). LIVE is allowed to use
# the nearest IVR/IVP workbook that has actually arrived by wall-clock time.
LIVE_IVRP_LOOKBACK_SECONDS = 900
LIVE_IVRP_LOOKAHEAD_SECONDS = 900

@st.cache_data(ttl=30, show_spinner=False)
def _read_ivrp_for_live_timestamp(day: str, target: pd.Timestamp) -> pd.DataFrame:
    """Resolve LIVE Futures OI from the nearest already-arrived IVR/IVP file."""
    if not day or target is None or pd.isna(target):
        return pd.DataFrame()
    candidates = _day_ivrp_candidates(str(day)[:10])
    if not candidates:
        return pd.DataFrame()
    target = pd.Timestamp(target)
    now = pd.Timestamp.now()
    ranked = []
    for path in candidates:
        ts = observation_ts(path)
        if pd.isna(ts) or pd.Timestamp(ts) > now:
            continue
        delta = (pd.Timestamp(ts) - target).total_seconds()
        if delta <= 0 and abs(delta) <= LIVE_IVRP_LOOKBACK_SECONDS:
            ranked.append((abs(delta), 0, -pd.Timestamp(ts).value, path))
        elif delta > 0 and delta <= LIVE_IVRP_LOOKAHEAD_SECONDS:
            ranked.append((delta, 1, -pd.Timestamp(ts).value, path))
    if not ranked:
        return pd.DataFrame()
    _, _, _, path = sorted(ranked, key=lambda x: (x[0], x[1], x[2], str(x[3]).lower()))[0]
    try:
        raw = _normalize_ivrp_export(pd.read_excel(path))
        symbol_col = _named_column(raw, "Symbol", "symbol", "Ticker", "ticker")
        oi_col = _named_column(raw, "Total OI Chg", "Total OI Change", "total_oi_chg", "Fut OI Chg", "Futures OI Chg", "Future OI Chg", "fut_oi_chg", "futures_oi_chg")
        oi_pct_col = _named_column(raw, "Total OI Chg (%)", "Total OI Chg %", "Total OI Change (%)", "Total OI Change %", "total_oi_chg_pct", "Fut OI Chg %", "Futures OI Chg %", "Future OI Chg %", "fut_oi_chg_pct", "futures_oi_chg_pct")
        if symbol_col is None:
            return pd.DataFrame()
        out = pd.DataFrame({
            "symbol": raw[symbol_col].astype(str).str.strip().str.upper(),
            "futures_oi_chg": _numeric_series(raw, oi_col),
            "futures_oi_chg_pct": _numeric_series(raw, oi_pct_col),
        })
        out = out[out["symbol"].ne("") & out["symbol"].ne("NAN")].copy()
        return out.drop_duplicates("symbol")
    except Exception:
        return pd.DataFrame()

# ============================================================================
# LIVE FUTURES / IVR-IVP DELAY DISPLAY POLICY
# ============================================================================
LIVE_FUTURES_DELAY_SECONDS = 300
LIVE_FUTURES_STATE_FILE = Path(__file__).resolve().parent / ".sdl_live_futures_state.pkl"


def _load_live_futures_state() -> dict:
    try:
        if not LIVE_FUTURES_STATE_FILE.exists():
            return {}
        obj = pd.read_pickle(LIVE_FUTURES_STATE_FILE)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _save_live_futures_state(state: dict) -> None:
    try:
        tmp = LIVE_FUTURES_STATE_FILE.with_suffix(".tmp")
        pd.to_pickle(state, tmp)
        tmp.replace(LIVE_FUTURES_STATE_FILE)
    except Exception:
        pass


def _live_futures_present(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    cols = [c for c in ("futures_oi_chg", "futures_oi_chg_pct") if c in df.columns]
    return bool(cols) and any(
        pd.to_numeric(df[c], errors="coerce").notna().any() for c in cols
    )


def _apply_live_futures_delay_policy(
    pred: pd.DataFrame,
    snapshot_ts: pd.Timestamp,
    futures_fresh: bool = False,
) -> pd.DataFrame:
    """LIVE-only: after 300s without new Futures data, retain last value and flag D."""
    if pred is None or pred.empty:
        return pred

    out = pred.copy()
    state = _load_live_futures_state()

    if futures_fresh and _live_futures_present(out):
        cols = [c for c in ("futures_oi_chg", "futures_oi_chg_pct") if c in out.columns]
        if "symbol" in out.columns:
            state = {
                "status": "FRESH",
                "processed_snapshot_ts": str(snapshot_ts),
                "values": out[["symbol"] + cols].to_dict("records"),
            }
            _save_live_futures_state(state)
        out["futures_oi_status"] = "FRESH"
        out["futures_oi_delayed"] = False
        return out

    last_ts = (
        pd.to_datetime(state.get("processed_snapshot_ts"), errors="coerce")
        if state.get("processed_snapshot_ts") else pd.NaT
    )
    age = (
        (pd.Timestamp(snapshot_ts) - last_ts).total_seconds()
        if pd.notna(last_ts) and pd.notna(snapshot_ts) else None
    )
    delayed = age is not None and age > LIVE_FUTURES_DELAY_SECONDS

    if delayed and state.get("values") and "symbol" in out.columns:
        saved = pd.DataFrame(state["values"])
        if not saved.empty and "symbol" in saved.columns:
            saved = saved.drop_duplicates("symbol").set_index("symbol")
            idx = out["symbol"].astype(str)
            for col in ("futures_oi_chg", "futures_oi_chg_pct"):
                if col in saved.columns:
                    restored = idx.map(saved[col])
                    current = (
                        pd.to_numeric(out[col], errors="coerce")
                        if col in out.columns
                        else pd.Series(index=out.index, dtype=float)
                    )
                    out[col] = pd.to_numeric(restored, errors="coerce").combine_first(current)

    out["futures_oi_status"] = "DELAYED" if delayed else "PENDING"
    out["futures_oi_delayed"] = delayed
    return out



def latest_live() -> tuple[
    Path | None,
    pd.DataFrame,
    pd.Timestamp,
    str,
]:
    """Return the latest dashboard snapshot with bounded LIVE work.

    LIVE never rebuilds the complete trading-day cache. A genuinely new
    observation is processed once. If the same observation is still pending
    IVR/IVP evidence, only the lightweight companion lookup is retried.
    """
    try:
        available = [
            path for path in snapshot_files()
            if pd.notna(observation_ts(path))
        ]

        persisted = _load_persisted_live_snapshot()

        if not available:
            if persisted and persisted.get("pred") is not None:
                ts = pd.to_datetime(
                    persisted.get("observation_timestamp"), errors="coerce"
                )
                path = (
                    Path(persisted["source_path"])
                    if persisted.get("source_path") else None
                )
                return path, persisted["pred"], ts, persisted.get("message", "")
            return None, pd.DataFrame(), pd.NaT, "No current snapshot."

        latest = available[-1]
        latest_ts = observation_ts(latest)
        persisted_ts = (
            pd.to_datetime(
                persisted.get("observation_timestamp"), errors="coerce"
            )
            if persisted else pd.NaT
        )

        # Same observation: return immediately when already complete.
        if (
            persisted
            and pd.notna(persisted_ts)
            and pd.notna(latest_ts)
            and pd.Timestamp(persisted_ts) == pd.Timestamp(latest_ts)
            and isinstance(persisted.get("pred"), pd.DataFrame)
        ):
            persisted_pred = persisted["pred"].copy()
            status = str(persisted.get("evidence_status", "")).lower()

            # First consult the exact persistent point-in-time cache. This is
            # the bridge that keeps LIVE identical to Snapshot Replay when
            # Replay has already obtained the IVR/IVP Futures OI companion.
            hydrated_pred, hydrated_status = _hydrate_live_from_point_cache(
                pd.Timestamp(latest_ts).date().isoformat(),
                pd.Timestamp(latest_ts),
                persisted_pred,
            )
            if hydrated_status == "complete":
                _save_persisted_live_snapshot(
                    latest,
                    pd.Timestamp(latest_ts),
                    hydrated_pred,
                    persisted.get("message", ""),
                )
                try:
                    with PROCESSED_LIVE_SNAPSHOT_FILE.open("rb") as handle:
                        payload = pickle.load(handle)
                    if isinstance(payload, dict):
                        payload["evidence_status"] = "complete"
                        tmp = PROCESSED_LIVE_SNAPSHOT_FILE.with_suffix(".tmp")
                        with tmp.open("wb") as handle:
                            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
                        tmp.replace(PROCESSED_LIVE_SNAPSHOT_FILE)
                except Exception:
                    pass
                hydrated_pred = _apply_live_futures_delay_policy(
                    hydrated_pred, pd.Timestamp(latest_ts)
                )
                return (
                    latest, hydrated_pred, pd.Timestamp(latest_ts),
                    persisted.get("message", ""),
                )

            persisted_pred = hydrated_pred
            status = hydrated_status

            if status == "complete":
                persisted_pred = _apply_live_futures_delay_policy(
                    persisted_pred, pd.Timestamp(latest_ts)
                )
                return (
                    latest, persisted_pred, pd.Timestamp(latest_ts),
                    persisted.get("message", ""),
                )

            # Pending/missing evidence: retry only the IVR/IVP companion.
            # No Daywise rebuild and no full-day replay cache build.
            day = pd.Timestamp(latest_ts).date().isoformat()
            futures_evidence = _read_ivrp_for_live_timestamp(day, pd.Timestamp(latest_ts))
            if futures_evidence is not None and not futures_evidence.empty:
                cache = _load_day_point_cache()
                day_cache = cache.get(day, {}) if isinstance(cache, dict) else {}
                entries = day_cache.get("snapshots", {}) if isinstance(day_cache.get("snapshots"), dict) else {}
                cached_entry = entries.get(pd.Timestamp(latest_ts).isoformat())
                cached_option = cached_entry.get("evidence") if isinstance(cached_entry, dict) else pd.DataFrame()
                refreshed, evidence = _merge_snapshot_evidence(
                    persisted_pred,
                    cached_option if isinstance(cached_option, pd.DataFrame) else pd.DataFrame(),
                    futures_evidence,
                )
                futures_available = _futures_evidence_available(futures_evidence)
                _upsert_day_point_cache_entry(
                    day, pd.Timestamp(latest_ts), latest, refreshed, evidence,
                    "complete" if futures_available else "pending",
                )
                _save_persisted_live_snapshot(
                    latest,
                    pd.Timestamp(latest_ts),
                    refreshed,
                    persisted.get("message", ""),
                )
                # Preserve pending/complete state in the persisted payload
                try:
                    with PROCESSED_LIVE_SNAPSHOT_FILE.open("rb") as handle:
                        payload = pickle.load(handle)
                    if isinstance(payload, dict):
                        payload["evidence_status"] = (
                            "complete" if futures_available else "pending"
                        )
                        tmp = PROCESSED_LIVE_SNAPSHOT_FILE.with_suffix(".tmp")
                        with tmp.open("wb") as handle:
                            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
                        tmp.replace(PROCESSED_LIVE_SNAPSHOT_FILE)
                except Exception:
                    pass
                refreshed = _apply_live_futures_delay_policy(
                    refreshed, pd.Timestamp(latest_ts), futures_fresh=futures_available
                )
                return (
                    latest, refreshed, pd.Timestamp(latest_ts),
                    persisted.get("message", ""),
                )

            persisted_pred = _apply_live_futures_delay_policy(
                persisted_pred, pd.Timestamp(latest_ts), futures_fresh=False
            )
            return (
                latest, persisted_pred, pd.Timestamp(latest_ts),
                persisted.get("message", ""),
            )

        # Genuinely newer observation: authoritative frozen pipeline is run
        # once for that observation only.
        result = process_latest_snapshot_for_today()
        if not result or len(result) != 4:
            return None, pd.DataFrame(), pd.NaT, "No current snapshot."

        path, _events, df, message = result
        if path is not None and df is not None and not df.empty:
            path = Path(path)
            ts = observation_ts(path)
            if pd.notna(ts):
                pred, msg = _process_single_snapshot_for_dashboard(
                    path, pd.Timestamp(ts), df, message
                )
                live_futures = _read_ivrp_for_live_timestamp(
                    pd.Timestamp(ts).date().isoformat(), pd.Timestamp(ts)
                )
                if live_futures is not None and not live_futures.empty:
                    live_option = _day_option_evidence(derive_straddle_values(df))
                    pred, _live_evidence = _merge_snapshot_evidence(
                        pred, live_option, live_futures
                    )
                    futures_available = _futures_evidence_available(live_futures)
                else:
                    futures_available = False
                futures_available = (
                    "futures_oi_chg" in pred.columns
                    and pd.to_numeric(
                        pred["futures_oi_chg"], errors="coerce"
                    ).notna().any()
                ) or (
                    "futures_oi_chg_pct" in pred.columns
                    and pd.to_numeric(
                        pred["futures_oi_chg_pct"], errors="coerce"
                    ).notna().any()
                )
                _save_persisted_live_snapshot(path, ts, pred, msg)
                try:
                    with PROCESSED_LIVE_SNAPSHOT_FILE.open("rb") as handle:
                        payload = pickle.load(handle)
                    if isinstance(payload, dict):
                        payload["evidence_status"] = (
                            "complete" if futures_available else "pending"
                        )
                        tmp = PROCESSED_LIVE_SNAPSHOT_FILE.with_suffix(".tmp")
                        with tmp.open("wb") as handle:
                            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
                        tmp.replace(PROCESSED_LIVE_SNAPSHOT_FILE)
                except Exception:
                    pass
                pred = _apply_live_futures_delay_policy(
                    pred, pd.Timestamp(ts), futures_fresh=futures_available
                )
                return path, pred, ts, msg

        # Preserve rollover fallback, but keep it lazy.
        fallback_path = latest
        fallback_ts = latest_ts
        fallback_pred, _ = replay_snapshot_frame(
            fallback_path, fallback_ts
        )
        fallback_day = fallback_ts.strftime("%d %b %Y")
        return (
            fallback_path,
            fallback_pred,
            fallback_ts,
            message or f"Showing last available session: {fallback_day}.",
        )

    except Exception as exc:
        return None, pd.DataFrame(), pd.NaT, f"{type(exc).__name__}: {exc}"



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
    current_day = pd.Timestamp.now(tz=IST).date()
    preserved_session = pd.notna(data_ts) and data_ts.date() != current_day
    snapshot_label = (
        "LAST AVAILABLE SESSION"
        if preserved_session
        else "LATEST SOURCE SNAPSHOT"
    )
    snapshot_note = (
        "Preserved until today's first source snapshot arrives"
        if preserved_session
        else "Actual source observation time"
    )
    if preserved_session:
        st.markdown(
            '<div class="queue-header-note" style="margin:0 0 8px 0">'
            '<b>PREVIOUS SESSION PRESERVED</b> · No Daywise snapshot is available for today yet. '
            'Live Queue and Intraday Replay remain on the last completed session and will switch '
            'to today automatically when the first new source snapshot arrives.'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="utility-strip">
          <div style="display:grid;grid-template-columns:1.35fr 1fr 1fr">
            <div class="utility-cell">
              <div class="utility-label">{snapshot_label}</div>
              <div class="utility-value cyan">
                {safe_text(fmt_time(data_ts, True))}
              </div>
              <div class="utility-note">{snapshot_note}</div>
            </div>
            <div class="utility-cell">
              <div class="utility-label">MARKET SESSION</div>
              <div class="utility-value amber">{session}</div>
              <div class="utility-note">NSE session context</div>
            </div>
            <div class="utility-cell">
              <div class="utility-label">DECISION MODE</div>
              <div class="utility-value">
                {"PRESERVED SESSION" if preserved_session else "FACTS ONLY"}
              </div>
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

    # A valid source snapshot can legitimately contain zero eligible SDL
    # decisions. Treat that as an explicit empty state rather than indexing
    # optional prediction columns on a zero-column DataFrame.
    if pred is None or pred.empty:
        st.info(
            "No SDL decisions are currently qualified for this source snapshot. "
            "The source snapshot was processed successfully; no decision is "
            "being manufactured for display."
        )
        return

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
    radar_market_news = live_nse_market_news()

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
            radar_news = live_nse_stock_news(str(row.get("symbol", "")))
            radar_catalyst = analyze_news_catalyst(
                str(row.get("symbol", "")), row, radar_news, radar_market_news
            )
            radar_star = catalyst_badge(radar_catalyst)

            st.markdown(
                f'<div class="radar-card {radar_class}">'
                f'<div class="radar-symbol">'
                f'{radar_star}{safe_text(row.get("symbol"))}'
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
# SECTOR ANALYSIS — EXISTING NEWS FEED ADAPTER (PRESENTATION ONLY)
# ============================================================================

def sector_analysis_news_provider() -> list[dict]:
    """Reuse the dashboard's existing NSE market-news feed for Sector Analysis.

    No new provider, scoring path, source workbook, or SDL decision dependency
    is introduced here. Sector Analysis consumes this as contextual evidence.
    """
    try:
        items = live_nse_market_news()
    except Exception:
        return []

    return [
        {
            "title": (
                f"{str(item.get('symbol', '')).strip().upper()} · "
                f"{str(item.get('text', '')).strip()}"
            ).strip(" ·"),
            "timestamp": item.get("time"),
            "source": "NSE Corporate Announcements",
        }
        for item in items
        if str(item.get("text", "")).strip()
    ]


# ============================================================================
# HEADER / NAVIGATION
# ============================================================================

if "page" not in st.session_state:
    st.session_state.page = "decision"

header_cols = st.columns(
    [1.35, 1.00, 1.00, 1.00, .80, .42, .62, .58, .78, .52]
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
        "▦ Sector Analysis",
        type=(
            "primary"
            if st.session_state.page == "sector"
            else "secondary"
        ),
        use_container_width=True,
        key="nav_sector",
    ):
        st.session_state.page = "sector"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with header_cols[3]:
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

with header_cols[4]:
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

with header_cols[5]:
    st.markdown(
        '<div class="header-control">'
        '<div class="live-pill"><i></i> LIVE</div>'
        '</div>',
        unsafe_allow_html=True,
    )

with header_cols[6]:
    now = datetime.now()
    st.markdown(
        f'<div class="clock-box">'
        f'<b>{safe_text(now.strftime("%I:%M:%S %p"))}</b>'
        f'<small>{safe_text(now.strftime("%d %b %Y"))}</small>'
        f'</div>',
        unsafe_allow_html=True,
    )

with header_cols[7]:
    st.markdown('<div class="header-control">', unsafe_allow_html=True)
    if st.button(
        "↻ Refresh",
        use_container_width=True,
        key="header_refresh",
    ):
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with header_cols[8]:
    st.markdown('<div class="header-control">', unsafe_allow_html=True)
    auto = st.checkbox(
        "Auto Refresh",
        value=bool(_UI.get("auto_refresh", False)),
        key="auto_refresh_control",
    )
    st.markdown("</div>", unsafe_allow_html=True)

with header_cols[9]:
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

elif st.session_state.page == "sector":
    render_sector_analysis_page(
        getattr(
            sdl_pipeline,
            "INTRADAY_SOURCE_ROOT",
            sdl_config.INTRADAY_SOURCE_ROOT,
        ),
        news_provider=sector_analysis_news_provider,
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
