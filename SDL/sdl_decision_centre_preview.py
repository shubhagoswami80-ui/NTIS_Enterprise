from __future__ import annotations

from pathlib import Path
from datetime import datetime
import calendar
import html
import json
import pickle
import re
import time
import os
import threading
import hashlib
from urllib.parse import quote
from urllib.parse import urlencode
from xml.etree import ElementTree as ET
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

# ============================================================================
# CONSOLIDATED B4 BUNDLE — 23-SEP-2026
# Alert runtime, persistent edge evaluation, approved rule defaults, on-demand
# external news, on-demand price timeline, and performance-safe cold paths.
# Frozen SDL scoring/gates, First Alert, Replay/Futures/cache architecture,
# Priority Radar and LIVE Queue datasets remain untouched.
# ============================================================================

# ADDITIVE ONLY: isolated Sector Analysis page. Existing SDL logic is untouched.
from Sector_Analysis.sector_page import render_sector_analysis_page

# ADDITIVE ONLY: isolated B4 alert drawer + optional sound.
_B4_IMPORT_ERROR = None
try:
    from extensions.alert_chart.dashboard_alert_drawer import render_alert_drawer, _render_intraday_evidence_chart
except Exception as exc:
    render_alert_drawer = None
    _B4_IMPORT_ERROR = f"dashboard_alert_drawer: {type(exc).__name__}: {exc}"

try:
    from extensions.alert_chart.alert_store import AlertStore
except Exception as exc:
    AlertStore = None
    _B4_IMPORT_ERROR = (
        f"{_B4_IMPORT_ERROR}; alert_store: {type(exc).__name__}: {exc}"
        if _B4_IMPORT_ERROR else f"alert_store: {type(exc).__name__}: {exc}"
    )

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
# CONTROLLED BUNDLE — First Alert durable-state restoration + Replay UI/performance
# improvements. Frozen decision/scoring/replay point-in-time semantics remain unchanged.
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

# B4 alert sidecar store. This is presentation/event state only; it does not
# participate in SDL scoring, prediction, replay, futures mapping, or cache.
ALERT_STORE_FILE = Path(__file__).resolve().parent / ".sdl_alerts.db"

# One persisted dashboard working snapshot.  Source workbooks are used only
# to detect/ingest a NEW 5-minute observation; once processed, the dashboard
# serves this persisted result and does not reopen the source workbook.
PROCESSED_LIVE_SNAPSHOT_FILE = (
    Path(__file__).resolve().parent / ".sdl_processed_live_snapshot.pkl"
)

# Persistent chronological day cache. Source workbooks remain READ ONLY;
# replay/live consume this cache once a trading-day observation has been processed.
DAY_POINT_IN_TIME_CACHE_FILE = (
    Path(__file__).resolve().parent / ".sdl_day_point_in_time_cache.pkl"
)

DAY_POINT_CACHE_SCHEMA = 7
LIVE_FUTURES_DELAY_SECONDS = 300
LIVE_FUTURES_STATE_FILE = (
    Path(__file__).resolve().parent / ".sdl_live_futures_state.pkl"
)

# PERFORMANCE / SOURCE-CADENCE FREEZE
# News is deliberately refreshed only every 15 minutes.
NEWS_CACHE_SECONDS = 15 * 60

# Futures companions normally arrive with the next 5-minute source batch.
# Successful point-in-time resolutions are retained for the exact Daywise
# timestamp. Pending points are rechecked at most once per minute until the
# existing T+300-second eligibility window expires.
FUTURES_PENDING_RETRY_SECONDS = 60

# Persistent background cache-build coordination. The historical cache builder
# runs in a server-side worker thread so Streamlit reruns/fragment refreshes
# never cancel an in-progress build.
DAY_CACHE_BUILD_STATE_FILE = (
    Path(__file__).resolve().parent / ".sdl_day_cache_build_state.json"
)
_DAY_CACHE_BUILD_LOCK = threading.Lock()
_BACKGROUND_IVRP_TIMESTAMP_CACHE = {}

# Dashboard Auto Refresh is browser-driven so the Streamlit server is never
# blocked by time.sleep().

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
# B4 APPROVED DEFAULT RULES
# ============================================================================


def _default_b4_rules() -> list[dict]:
    """Approved B4 runtime rules; alert layer only, never SDL scoring."""
    return [
        {"name": "Strong Breakout", "field": "Straddle Progress", "operator": ">=", "value": 100.0, "enabled": True, "sound": False},
        {"name": "Breakout", "field": "Straddle Progress", "operator": ">=", "value": 75.0, "enabled": True, "sound": False},
        {"name": "First Alert", "field": "Straddle Progress", "operator": ">=", "value": 25.0, "enabled": True, "sound": False},
        {"name": "Futures OI Spike", "field": "Futures OI Change", "operator": ">", "value": 100000.0, "enabled": True, "sound": False},
        {"name": "PCR Extreme", "field": "PCR", "operator": ">", "value": 3.0, "enabled": True, "sound": False},
        {"name": "High Momentum", "field": "Momentum %", "operator": ">=", "value": 5.0, "enabled": False, "sound": False},
    ]


# ============================================================================
# SETTINGS / SOURCE BINDING
# ============================================================================

def load_ui_settings() -> dict:
    defaults = {
        "source_root": str(getattr(sdl_config, "INTRADAY_SOURCE_ROOT", "")),
        "auto_refresh": False,
        "refresh_seconds": 60,
        "alert_config_schema": 4,
        "alert_sound_enabled": False,
        "alert_sound_volume": 0.35,
        "alert_sound_tone": "soft",
        "alert_rules": _default_b4_rules(),
    }
    try:
        if SETTINGS_FILE.exists():
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                defaults.update(saved)
                # B4 schema migration: preserve explicit user rules, but
                # deterministically restore the approved defaults when the old
                # drawer stored no rules. Never turn sound on during migration.
                saved_schema = int(saved.get("alert_config_schema", 0) or 0)
                saved_rules = saved.get("alert_rules")
                if saved_schema < 4:
                    defaults["alert_config_schema"] = 4
                    defaults["alert_sound_enabled"] = False
                    defaults["alert_sound_volume"] = 0.35
                    defaults["alert_sound_tone"] = "soft"
                    if not isinstance(saved_rules, list) or not saved_rules:
                        defaults["alert_rules"] = _default_b4_rules()
                elif not isinstance(defaults.get("alert_rules"), list) or not defaults.get("alert_rules"):
                    defaults["alert_rules"] = _default_b4_rules()
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

def _normalize_b4_rule(raw: dict, idx: int = 0) -> dict:
    rule = dict(raw) if isinstance(raw, dict) else {}
    name = str(rule.get("name") or f"Rule {idx + 1}").strip() or f"Rule {idx + 1}"
    field = str(rule.get("field") or "PCR").strip()
    operator = str(rule.get("operator") or ">=").strip()
    try:
        value = float(rule.get("value", 0))
    except Exception:
        value = 0.0
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or f"rule-{idx + 1}"
    rule.update({
        "id": str(rule.get("id") or f"b4-{slug}"),
        "name": name, "field": field, "operator": operator, "value": value,
        "enabled": bool(rule.get("enabled", True)), "sound": bool(rule.get("sound", False)),
        "priority": int(rule.get("priority", max(1, 100 - idx))),
        "rearm": rule.get("rearm") or {"mode": "ON_CROSSING", "cooldown_seconds": 0},
    })
    return rule


def _sync_b4_rules_from_store() -> None:
    """Use AlertStore as the durable rule source, migrating legacy UI settings once."""
    if AlertStore is None:
        return
    try:
        store = AlertStore(ALERT_STORE_FILE)
        stored = store.list_rules()
        if stored:
            _UI["alert_rules"] = [_normalize_b4_rule(rule, i) for i, rule in enumerate(stored)]
            _UI["alert_config_schema"] = 4
            save_ui_settings(alert_rules=_UI["alert_rules"], alert_config_schema=4)
            return
        legacy = _UI.get("alert_rules")
        rules = legacy if isinstance(legacy, list) and legacy else _default_b4_rules()
        now = pd.Timestamp.now(tz=IST).isoformat()
        normalized = []
        for i, raw in enumerate(rules):
            rule = _normalize_b4_rule(raw, i)
            store.save_rule(rule, now)
            normalized.append(rule)
        _UI["alert_rules"] = normalized
        _UI["alert_config_schema"] = 4
        save_ui_settings(alert_rules=normalized, alert_config_schema=4)
    except Exception as exc:
        _UI["b4_store_error"] = f"{type(exc).__name__}: {exc}"


_sync_b4_rules_from_store()
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
.replay-calendar-legend{margin:6px 0 8px;padding:7px 9px;background:#0e1d31;border:1px solid #203653;border-radius:7px;color:#9fb1c8;font-size:9px!important;}
.replay-calendar-head{text-align:center;color:#7187a4;font-size:8px!important;font-weight:900!important;padding:3px 0;}
.replay-calendar-empty{min-height:34px;}
.replay-calendar-no-source{min-height:34px;padding:8px 0;text-align:center;color:#42556f;font-size:10px!important;border:1px solid transparent;}

.st-key-replay_calendar_wrap{margin:2px 0 6px!important;padding:3px 4px 5px;background:#091729;border:1px solid #1c3048;border-radius:7px;}
.replay-calendar-head{font-size:7px!important;line-height:1!important;padding:2px 0!important;}
.replay-calendar-day-stats{color:#7187a4;font-size:7px!important;line-height:1.05!important;text-align:center;white-space:nowrap;margin-top:-3px;margin-bottom:2px;}
.replay-calendar-empty{min-height:24px!important;}
.replay-calendar-no-source{min-height:24px!important;padding:5px 0!important;font-size:8px!important;}
.st-key-replay_calendar_wrap div[data-testid="stButton"] button{min-height:25px!important;height:25px!important;padding:1px 3px!important;border-radius:5px!important;font-size:8px!important;line-height:1!important;}
.st-key-replay_calendar_wrap div[data-testid="stHorizontalBlock"]{gap:3px!important;}
/* ---------- COMPACT HISTORICAL CACHE BUILD MONITOR ---------- */
.cache-build-monitor{background:linear-gradient(105deg,#071a30 0%,#0b223c 100%);border:1px solid #28527b;border-radius:7px;padding:5px 8px;margin:5px 0 4px}
.cache-build-monitor-head{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#edf5ff;font-size:10px!important;font-weight:950!important;line-height:1.05!important}
.cache-build-live{margin-left:7px;color:#18df82;font-size:8px!important;font-weight:900!important}
.cache-build-mode{color:#9db2cc;font-size:8px!important;font-weight:900!important}
.cache-build-title{margin-top:2px;color:#b9c9dc;font-size:8px!important;font-weight:850!important;line-height:1.1!important}
.cache-build-compact-note{color:#8298b3;font-size:7.5px!important;line-height:1.15!important;margin-top:2px}
.cache-build-monitor + div[data-testid="stProgress"]{margin:2px 0 3px!important}
.cache-build-monitor + div[data-testid="stProgress"] p{font-size:8px!important;margin:0!important}
.cache-build-monitor + div[data-testid="stProgress"] div[role="progressbar"]{height:5px!important}
.replay-cache-status{margin:5px 0 6px;padding:6px 8px;background:#0b1a2d;border:1px solid #233a57;border-radius:6px;color:#aebed1;font-size:9px!important;line-height:1.25!important;}
.replay-cache-status.ready{border-color:#176647;background:#09271e;color:#8de2b7;}
.replay-cache-status.pending{border-color:#80651a;background:#2a220c;color:#f0ca55;}
.replay-cache-status.partial{border-color:#8a5417;background:#2a1b0c;color:#f0a84c;}
.replay-cache-status.notbuilt{border-color:#8c3540;background:#2b1117;color:#ff7b84;}
.replay-cache-build{margin:5px 0 6px;padding:7px 8px;background:#0d1d31;border:1px solid #35506f;border-radius:6px;}
.replay-cache-running{margin:7px 0 8px!important;padding:9px 10px!important;font-size:10px!important;line-height:1.35!important;border-width:1px!important;box-shadow:0 0 0 1px rgba(240,202,85,.08)!important;}
.replay-cache-running b{font-size:11px!important;color:#fff4cf!important;letter-spacing:.03em!important;}
.replay-cache-finished{margin-top:7px!important;padding:9px 10px!important;font-size:10px!important;line-height:1.35!important;}
.replay-cache-build-label{font-size:9px!important;font-weight:900!important;color:#e7eef8;letter-spacing:.05em;margin-bottom:3px;}
.replay-cache-build-note{font-size:8px!important;color:#8fa3bb;line-height:1.25!important;margin-bottom:5px;}
.live-feed-summary{margin:5px 0 7px;padding:5px 8px;background:#0b1a2d;border:1px solid #203653;border-radius:6px;color:#8fa3bb;font-size:9px!important;}
/* ---------- CACHE UI OCCUPANCY GUARD ---------- */
.replay-cache-status-prominent{margin:3px 0 4px!important;padding:4px 6px!important;font-size:8px!important;line-height:1.15!important}
.replay-cache-build-prominent{margin:2px 0 3px!important;padding:0!important;background:transparent!important;border:0!important}
.replay-cache-build-note{font-size:7.5px!important;line-height:1.1!important;margin:2px 0 4px!important;color:#8196b0!important}
#replay_day_info_panel div[data-testid="stButton"] button{min-height:28px!important;height:28px!important;padding:3px 7px!important;font-size:8px!important}


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

/* REPLAY CONTROLS / MICRO-CALENDAR CONTRAST
   UI-only: no replay logic changes. */
.st-key-replay_calendar_month { margin-bottom:3px!important; }
.st-key-replay_calendar_month label { color:#dce8f7!important; font-size:9px!important; font-weight:900!important; }
.st-key-replay_calendar_month [data-baseweb="select"] > div { background:#132744!important; border:1px solid #4b6f9d!important; color:#f4f8ff!important; min-height:30px!important; }
.st-key-replay_calendar_month [data-baseweb="select"] * { color:#f4f8ff!important; }
.st-key-replay_calendar_wrap div[data-testid="stButton"] button { background:#132744!important; border:1px solid #42648f!important; color:#eef5ff!important; min-height:20px!important; height:20px!important; padding:0 2px!important; font-size:8px!important; }
.st-key-replay_calendar_wrap div[data-testid="stButton"] button:hover { background:#1b365a!important; border-color:#6f9bd0!important; }
.st-key-replay_calendar_wrap div[data-testid="stButton"] button p { color:#eef5ff!important; font-size:8px!important; }


/* CONTROLLED REPLAY PERFORMANCE / READABILITY BUNDLE — 23-Sep-2026 */
.replay-selected-time{
  margin:4px 0 6px!important;padding:6px 9px!important;
  background:#0b1b30!important;border:1px solid #2b4c70!important;border-radius:6px!important;
  color:#a9bdd5!important;font-size:9px!important;line-height:1.2!important;
  letter-spacing:.03em!important;
}
.replay-selected-time b{color:#f0f6ff!important;font-size:11px!important;}
.st-key-replay_change_day button{
  min-height:28px!important;height:28px!important;padding:3px 8px!important;
  font-size:9px!important;font-weight:800!important;
}

/* FINAL COMPACT REPLAY LAYOUT v2 */
.st-key-replay_calendar_panel{margin-bottom:4px!important;}
.st-key-replay_calendar_panel div[data-testid="stExpander"]{margin:0!important;}
.st-key-replay_calendar_panel div[data-testid="stExpander"] summary{min-height:30px!important;padding:6px 9px!important;}
.st-key-replay_calendar_panel div[data-testid="stExpander"] summary p{font-size:10px!important;letter-spacing:.04em!important;}
.st-key-replay_calendar_panel div[data-testid="stExpander"] .st-key-replay_calendar_month{margin:2px 0 2px!important;}
.st-key-replay_calendar_panel .replay-calendar-legend{font-size:7px!important;padding:3px 6px!important;margin:2px 0 3px!important;line-height:1.1!important;}
.st-key-replay_calendar_wrap{padding:2px 4px 3px!important;margin:0!important;}
.st-key-replay_calendar_wrap div[data-testid="stHorizontalBlock"]{gap:2px!important;margin-bottom:1px!important;}
.st-key-replay_calendar_wrap div[data-testid="stButton"]{margin:0!important;}
.st-key-replay_calendar_wrap div[data-testid="stButton"] button{min-height:19px!important;height:19px!important;padding:0 2px!important;font-size:7px!important;border-radius:4px!important;}
.st-key-replay_calendar_wrap .replay-calendar-head{font-size:6px!important;padding:1px 0!important;}
.st-key-replay_calendar_wrap .replay-calendar-empty,.st-key-replay_calendar_wrap .replay-calendar-no-source{min-height:19px!important;height:19px!important;padding:2px 0!important;font-size:7px!important;}
.st-key-replay_day_info_panel{margin-top:0!important;}
.st-key-replay_day_info_panel .replay-day-heading{padding:5px 8px!important;margin-bottom:3px!important;}
.st-key-replay_day_info_panel .replay-day-heading span{font-size:7px!important;}
.st-key-replay_day_info_panel .replay-day-heading b{font-size:11px!important;}
.st-key-replay_day_info_panel .replay-cache-status-prominent{margin:3px 0!important;padding:5px 7px!important;font-size:8px!important;line-height:1.2!important;}
.st-key-replay_day_info_panel .replay-cache-build-prominent{margin:3px 0!important;padding:5px 7px!important;}
.st-key-replay_day_info_panel .replay-cache-build-label{font-size:8px!important;margin-bottom:1px!important;}
.st-key-replay_day_info_panel .replay-cache-build-note{font-size:7px!important;margin-bottom:2px!important;}
.st-key-replay_day_info_panel div[data-testid="stButton"] button{min-height:27px!important;height:27px!important;padding:3px 6px!important;font-size:8px!important;}
.st-key-replay_day_info_panel .replay-selected-snapshot{margin-top:4px!important;}
/* FINAL MICRO REPLAY CALENDAR
   UI-only: keep calendar logic/status statistics unchanged. */
.replay-calendar-wrap {
    margin: 4px 0 6px 0 !important;
    padding: 5px 7px 4px 7px !important;
}
.replay-calendar-legend {
    padding: 3px 6px !important;
    margin: 2px 0 4px 0 !important;
    font-size: 9px !important;
    line-height: 1.1 !important;
}
.replay-calendar-head {
    font-size: 8px !important;
    line-height: 1 !important;
    margin-bottom: 2px !important;
}
.replay-calendar-grid {
    gap: 2px !important;
}
.replay-calendar-day {
    min-height: 20px !important;
    height: 20px !important;
    padding: 1px 2px !important;
    border-radius: 4px !important;
    font-size: 9px !important;
    line-height: 1 !important;
}
.replay-calendar-day .day-number,
.replay-calendar-day .calendar-day-number {
    font-size: 9px !important;
    line-height: 10px !important;
}
.replay-calendar-day .day-stats,
.replay-calendar-day .calendar-day-stats {
    font-size: 6.5px !important;
    line-height: 7px !important;
    margin-top: 1px !important;
}
.replay-calendar-empty,
.replay-calendar-no-source {
    min-height: 20px !important;
    height: 20px !important;
}


/* REPLAY SELECTED-DAY / CACHE ACTION VISIBILITY */
.replay-day-heading { margin:0 0 6px !important; padding:8px 10px !important; background:#10233d !important; border:1px solid #3d6190 !important; border-radius:7px !important; color:#dce8f7 !important; font-size:9px !important; line-height:1.25 !important; }
.replay-day-heading span { color:#8fa8c4 !important; font-size:8px !important; font-weight:900 !important; letter-spacing:.08em !important; }
.replay-day-heading b { display:block; color:#f3f7fd !important; font-size:14px !important; margin-top:3px !important; }
.replay-cache-status-prominent { margin:6px 0 8px !important; padding:9px 10px !important; font-size:10px !important; line-height:1.35 !important; }
.replay-cache-build-prominent { margin:7px 0 8px !important; padding:10px !important; background:#122945 !important; border:1px solid #587ba7 !important; border-radius:8px !important; box-shadow:0 0 0 1px rgba(88,123,167,.12) !important; }
.replay-cache-build-prominent .replay-cache-build-label { color:#f5f8fd !important; font-size:11px !important; letter-spacing:.08em !important; margin-bottom:4px !important; }
.replay-cache-build-prominent .replay-cache-build-note { color:#b9cbe0 !important; font-size:9px !important; line-height:1.35 !important; }
[class*="st-key-build_replay_cache_"] button { min-height:42px !important; font-size:11px !important; font-weight:950 !important; }
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
def point_in_time_oi_evidence(
    snapshot_path: Path,
    snapshot_ts: pd.Timestamp,
) -> pd.DataFrame:
    """Read only exact-time OI evidence from companion workbooks.

    This enrichment is deliberately point-in-time strict: a companion
    workbook is eligible only when its filesystem observation time matches
    the selected Daywise snapshot time within two seconds.  Later files are
    never used, and missing values remain missing.
    """
    if snapshot_path is None or pd.isna(snapshot_ts):
        return pd.DataFrame()
    folder = Path(snapshot_path).parent
    target = pd.Timestamp(snapshot_ts)
    frames = []

    aliases = {
        "futures_oi_chg": (
            "futures_oi_chg", "Fut OI Chg", "Futures OI Chg",
            "Future OI Chg", "OI Chg(Value)", "OI Chg (Value)",
        ),
        "futures_oi_chg_pct": (
            "futures_oi_chg_pct", "Fut OI Chg %", "Futures OI Chg %",
            "Future OI Chg %", "OI Chg %",
        ),
        "pe_minus_ce_oi_chg": (
            "pe_minus_ce_oi_chg", "PE-CE OI Chg", "PE_CE_OI_Chg",
            "Tot PE-CE OI Chg",
        ),
        "pe_minus_ce_oi_chg_pct": (
            "pe_minus_ce_oi_chg_pct", "PE-CE OI Chg %",
            "PE−CE OI Chg %", "Tot PE-CE OI Chg %",
        ),
    }

    def norm(v):
        return re.sub(r"[^a-z0-9]+", "", str(v).lower())

    def is_pct(v):
        t = str(v).lower()
        return "%" in t or "pct" in norm(t) or "percent" in t

    def resolve(cols, wanted):
        for alias in wanted:
            for c in cols:
                if str(c).strip().lower() == str(alias).strip().lower() and is_pct(c) == is_pct(alias):
                    return c
        for alias in wanted:
            for c in cols:
                if norm(c) == norm(alias) and is_pct(c) == is_pct(alias):
                    return c
        return None

    for candidate in sorted(folder.glob("*.xlsx"), key=lambda x: str(x).lower()):
        try:
            if candidate.resolve() == Path(snapshot_path).resolve():
                continue
            cts = observation_ts(candidate)
            if pd.isna(cts) or abs((pd.Timestamp(cts) - target).total_seconds()) > 2.0:
                continue
            raw = pd.read_excel(candidate)
            raw.columns = [str(c).strip() for c in raw.columns]
            if "Symbol" not in raw.columns:
                continue
            symbol = raw["Symbol"].astype(str).str.strip().str.upper()
            part = pd.DataFrame({"symbol": symbol})
            found = False
            for canonical, wanted in aliases.items():
                col = resolve(raw.columns, wanted)
                if col is None:
                    continue
                values = pd.to_numeric(
                    raw[col].astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False),
                    errors="coerce",
                )
                part[canonical] = values
                found = True
            if found:
                part = part[part["symbol"].ne("") & part["symbol"].ne("NAN")].copy()
                part["_source_file"] = str(candidate)
                part["_source_ts"] = pd.Timestamp(cts)
                frames.append(part)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    value_cols = [
        "futures_oi_chg", "futures_oi_chg_pct",
        "pe_minus_ce_oi_chg", "pe_minus_ce_oi_chg_pct",
    ]
    for col in value_cols:
        if col not in combined.columns:
            combined[col] = pd.NA
    # Same symbol + exact source time: first non-null physical value wins.
    rows = []
    for symbol, grp in combined.groupby("symbol", sort=False):
        row = {"symbol": symbol}
        for col in value_cols:
            vals = grp[col].dropna()
            row[col] = vals.iloc[0] if not vals.empty else pd.NA
        rows.append(row)
    return pd.DataFrame(rows)



def _load_day_point_cache() -> dict:
    try:
        if not DAY_POINT_IN_TIME_CACHE_FILE.exists():
            return {}
        with DAY_POINT_IN_TIME_CACHE_FILE.open("rb") as handle:
            value = pickle.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def _symbol_price_timeline(day: str, symbol: str, cutoff_iso: str | None, cache_sig: tuple) -> pd.DataFrame:
    """Build a point-in-time intraday evidence timeline for one symbol.

    Every evidence value belongs to the exact observation timestamp. No
    day-to-date accumulation is calculated here. This is a cold-path chart
    provider only; normal LIVE/Replay rendering does not execute it.
    """
    cache = _load_day_point_cache()
    day_cache = cache.get(str(day), {}) if isinstance(cache, dict) else {}
    entries = day_cache.get("snapshots", {}) if isinstance(day_cache, dict) else {}
    cutoff = pd.to_datetime(cutoff_iso, errors="coerce") if cutoff_iso else pd.NaT
    rows = []
    wanted = str(symbol).strip().upper()

    def _value(row: pd.Series, aliases: tuple[str, ...]):
        try:
            return metric(row, list(aliases))
        except Exception:
            for name in aliases:
                if name in row.index:
                    value = pd.to_numeric(pd.Series([row.get(name)]), errors="coerce").iloc[0]
                    if pd.notna(value):
                        return float(value)
        return None

    for key, entry in sorted(entries.items()):
        if not isinstance(entry, dict) or not isinstance(entry.get("pred"), pd.DataFrame):
            continue
        ts = pd.to_datetime(entry.get("timestamp", key), errors="coerce")
        if pd.isna(ts) or (pd.notna(cutoff) and ts > cutoff):
            continue
        frame = entry["pred"]
        if "symbol" in frame.columns:
            hit = frame[frame["symbol"].astype(str).str.upper().eq(wanted)]
        elif "Symbol" in frame.columns:
            hit = frame[frame["Symbol"].astype(str).str.upper().eq(wanted)]
        else:
            hit = pd.DataFrame()
        if hit.empty:
            continue
        row = hit.iloc[0]
        price = _value(row, ("Close", "CMP", "Current Price", "close", "current_price"))
        if price is None or pd.isna(price):
            continue
        rows.append({
            "Observation": ts,
            "Open": _value(row, ("Open", "open", "OPEN", "Open Price", "open_price")),
            "High": _value(row, ("High", "high", "HIGH", "High Price", "high_price")),
            "Low": _value(row, ("Low", "low", "LOW", "Low Price", "low_price")),
            "Close": float(price),
            "Futures OI Change": _value(row, ("futures_oi_chg", "Futures OI Change", "Future OI Change", "futures_oi_change")),
            "Futures OI Change %": _value(row, ("futures_oi_chg_pct", "Futures OI Change %", "Future OI Change %", "futures_oi_change_pct")),
            "PE-CE OI Change": _value(row, ("pe_minus_ce_oi_chg", "PE_CE_OI_Chg", "PE-CE OI Change", "PE−CE OI Change")),
            "PE-CE OI Change %": _value(row, ("pe_minus_ce_oi_chg_pct", "PE_CE_OI_Chg_Pct", "PE-CE OI Change %", "PE−CE OI Chg %")),
            "PCR Change %": _value(row, ("pcr_chg_pct", "PCR Chg %", "PCR Change %", "PCR Δ %")),
        })
    if not rows:
        return pd.DataFrame(columns=[
            "Observation", "Open", "High", "Low", "Close", "Futures OI Change",
            "Futures OI Change %", "PE-CE OI Change", "PE-CE OI Change %", "PCR Change %"
        ])
    result = (
        pd.DataFrame(rows)
        .drop_duplicates("Observation")
        .sort_values("Observation")
        .reset_index(drop=True)
    )
    return _merge_pece_into_timeline(result, day, wanted)




# ============================================================================
# POINT-IN-TIME PECE EVIDENCE — ON-DEMAND CHART ENRICHMENT
# ============================================================================

PECE_SOURCE_ROOT = Path(os.getenv(
    "NTIS_PECE_SOURCE_ROOT",
    r"D:\\My-data\\Share_P&L\\Ichart Data\\Screenshot\\PECE_Volume",
))


@st.cache_data(ttl=300, show_spinner=False)
def _pece_day_timeline(day: str) -> pd.DataFrame:
    """Load PECE snapshots and retain the embedded observation timestamp.

    PECE workbooks may arrive every ~10 minutes while containing multiple
    5-minute observations.  Snapshot/arrival time is never used as the
    market observation time.  Duplicate symbol+observation rows are resolved
    by the newest workbook so the evidence layer stays point-in-time.
    """
    try:
        d = pd.Timestamp(day).date()
    except Exception:
        return pd.DataFrame()
    root = PECE_SOURCE_ROOT / f"{d.year:04d}" / d.strftime("%B").lower() / d.isoformat()
    if not root.exists():
        return pd.DataFrame()

    files = sorted(root.glob("*.xlsx"), key=lambda x: (x.stat().st_mtime_ns, str(x).lower()))
    frames = []
    wanted = {
        "Time", "Symbol", "Fut Price", "VWAP", "IV",
        "Fut OI Chg", "Fut OI Chg %", "Diff(PE-CE OI Chg)",
        "Diff(PE-CE OI Chg %)", "CE OI Chg", "CE OI Chg %",
        "PE OI Chg", "PE OI Chg %", "PCR-OI", "PCR-OI Chg",
        "Fut Volume", "CE Volume", "PE Volume", "OI ChgTrend",
    }
    for path in files:
        try:
            frame = pd.read_excel(path, sheet_name="Data")
        except Exception:
            try:
                frame = pd.read_excel(path)
            except Exception:
                continue
        if frame.empty or "Symbol" not in frame.columns or "Time" not in frame.columns:
            continue
        keep = [c for c in frame.columns if c in wanted]
        if "Symbol" not in keep or "Time" not in keep:
            continue
        frame = frame[keep].copy()
        frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
        frame["Observation"] = pd.to_datetime(
            d.isoformat() + " " + frame["Time"].astype(str).str.strip(),
            errors="coerce",
        )
        frame["_source_mtime"] = path.stat().st_mtime_ns
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["Observation", "Symbol"])
    out = out.sort_values(["_source_mtime", "Observation"])
    out = out.drop_duplicates(["Symbol", "Observation"], keep="last")
    return out.drop(columns=["_source_mtime"], errors="ignore").reset_index(drop=True)


def _merge_pece_into_timeline(frame: pd.DataFrame, day: str, symbol: str) -> pd.DataFrame:
    pece = _pece_day_timeline(day)
    if pece.empty or frame.empty:
        return frame
    pece = pece[pece["Symbol"].eq(str(symbol).strip().upper())].copy()
    if pece.empty:
        return frame
    pece = pece.sort_values("Observation")
    left = frame.sort_values("Observation").copy()
    # Daywise observation timestamps can carry seconds while PECE uses the
    # embedded 5-minute clock. Nearest mapping within 3 minutes is explicit
    # and does not invent or accumulate any derivative value.
    merged = pd.merge_asof(
        left, pece, on="Observation", direction="nearest",
        tolerance=pd.Timedelta(minutes=3), suffixes=("", "_PECE"),
    )
    aliases = {
        "Fut OI Chg": "Futures OI Change",
        "Fut OI Chg %": "Futures OI Change %",
        "Diff(PE-CE OI Chg)": "PE-CE OI Change",
        "Diff(PE-CE OI Chg %)": "PE-CE OI Change %",
        "CE OI Chg": "CE OI Change",
        "CE OI Chg %": "CE OI Change %",
        "PE OI Chg": "PE OI Change",
        "PE OI Chg %": "PE OI Change %",
        "PCR-OI": "PCR OI",
        "PCR-OI Chg": "PCR OI Change",
        "IV": "IV",
        "VWAP": "VWAP",
        "Fut Price": "Futures Price",
        "Fut Volume": "Futures Volume",
        "CE Volume": "CE Volume",
        "PE Volume": "PE Volume",
        "OI ChgTrend": "OI Change Trend",
    }
    for source, target in aliases.items():
        col = f"{source}_PECE" if f"{source}_PECE" in merged.columns else source
        if col in merged.columns:
            merged[target] = pd.to_numeric(merged[col], errors="coerce") if target != "OI Change Trend" else merged[col]
    return merged

def _cache_file_signature() -> tuple:
    try:
        stt = DAY_POINT_IN_TIME_CACHE_FILE.stat()
        return (int(stt.st_mtime_ns), int(stt.st_size))
    except Exception:
        return (0, 0)


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
        f"*IVR*IVP*{day}*.xlsx",
    )
    for pattern in patterns:
        try:
            found.extend(root.rglob(pattern))
        except Exception:
            continue
    return sorted({Path(x) for x in found}, key=lambda x: (observation_ts(x), str(x).lower()))


def _source_filename_timestamp_key(path: Path) -> str | None:
    """Extract a source filename capture timestamp in canonical form."""
    if path is None:
        return None
    name = Path(path).name

    m = re.search(
        r"(20\d{2}-\d{2}-\d{2})[_-](\d{6})(?:\D|$)",
        name,
    )
    if m:
        return f"{m.group(1)}_{m.group(2)}"

    m = re.search(
        r"(20\d{2})(\d{2})(\d{2})[_-](\d{6})(?:\D|$)",
        name,
    )
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}_{m.group(4)}"

    return None


def _normalize_ivrp_export(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize IVR/IVP exports whose first row may contain the real headers."""
    if raw is None or raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    out.columns = [str(c).strip() for c in out.columns]
    first = out.iloc[0].astype(str).str.strip().tolist()
    if first and first[0].casefold() == "symbol":
        out = out.iloc[1:].copy()
        out.columns = [str(c).strip() for c in first]
    return out.reset_index(drop=True)


def _read_ivrp_for_timestamp(
    day: str,
    target: pd.Timestamp,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Resolve Futures OI for one authoritative Daywise 5-minute timestamp.

    Performance policy:
      - successful resolution is cached for the exact Daywise timestamp;
      - LIVE pending points are rechecked at most once per minute;
      - explicit historical cache builds may set force_refresh=True so a
        previously pending LIVE/UI lookup can never suppress a fresh source
        check during a controlled cache build;
      - the existing T -> T+300 second eligibility rule remains authoritative;
      - a new Daywise timestamp naturally creates a new lookup key.
    """
    if not day or target is None or pd.isna(target):
        return pd.DataFrame()

    target = pd.Timestamp(target)
    # LIVE/UI keeps its Streamlit session cache. The background historical
    # builder has no ScriptRunContext, so it uses a process-local cache and
    # never touches st.session_state from the worker thread.
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        _has_streamlit_context = get_script_run_ctx() is not None
    except Exception:
        _has_streamlit_context = False
    if _has_streamlit_context:
        cache = st.session_state.setdefault("ivrp_timestamp_cache", {})
    else:
        cache = _BACKGROUND_IVRP_TIMESTAMP_CACHE
    key = f"{str(day)[:10]}|{target.strftime('%Y-%m-%dT%H:%M:%S')}|v3"
    now_epoch = time.time()
    cached = cache.get(key)

    if isinstance(cached, dict):
        status = str(cached.get("status", "pending"))
        checked_at = float(cached.get("checked_at", 0) or 0)
        if status == "complete":
            value = cached.get("data")
            return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()

        # Pending companion: don't scan the directory on every Streamlit rerun.
        # Historical cache builds explicitly bypass this wall-clock suppression.
        if (
            status == "pending"
            and not force_refresh
            and now_epoch - checked_at < FUTURES_PENDING_RETRY_SECONDS
        ):
            return pd.DataFrame()

    candidates = _day_ivrp_candidates(str(day)[:10])
    if not candidates:
        cache[key] = {
            "checked_at": now_epoch,
            "status": "pending",
            "data": pd.DataFrame(),
        }
        return pd.DataFrame()

    target_key = target.strftime("%Y-%m-%d_%H%M%S")
    exact = []
    forward = []
    now = pd.Timestamp.now()

    for path in candidates:
        ckey = _source_filename_timestamp_key(path)
        if ckey == target_key:
            exact.append(path)
            continue

        ts = observation_ts(path)
        if pd.isna(ts) or pd.Timestamp(ts) > now:
            continue
        delta = (pd.Timestamp(ts) - target).total_seconds()
        if 0.0 <= delta <= 300.0:
            forward.append((delta, path))

    if exact:
        path = sorted(exact, key=lambda p: str(p).lower())[0]
    elif forward:
        path = sorted(
            forward,
            key=lambda x: (x[0], str(x[1]).lower()),
        )[0][1]
    else:
        cache[key] = {
            "checked_at": now_epoch,
            "status": "pending",
            "data": pd.DataFrame(),
        }
        return pd.DataFrame()

    try:
        # Some IVR/IVP exports are Excel files where the physical first row
        # contains the real headers. Normalize that format before resolving
        # symbols/fields. This preserves the previously validated resolver
        # behavior and prevents an otherwise valid workbook from becoming
        # 0/N UNMAPPED.
        raw = _normalize_ivrp_export(pd.read_excel(path))

        def _canonical_symbol(value) -> str:
            """Normalize common NSE symbol decorations without changing display symbols."""
            text = str(value or "").strip().upper()
            if not text or text == "NAN":
                return ""
            # Common exports can carry exchange/segment decorations. Keep the
            # base NSE cash symbol as the join key while preserving the original
            # Daywise symbol for display.
            text = re.sub(r"^(?:NSE:|NFO:)", "", text)
            text = re.sub(r"(?:\.NS|-EQ|-BE|-FUT|-FUTURES)$", "", text)
            text = re.sub(r"\s+", "", text)
            return text

        def _build_ivrp_frame(frame: pd.DataFrame) -> pd.DataFrame:
            if frame is None or frame.empty:
                return pd.DataFrame()
            symbol_col = _named_column(frame, "Symbol", "symbol", "Ticker", "ticker")
            oi_col = _named_column(
                frame,
                "Total OI Chg", "Total OI Change", "total_oi_chg",
                "Fut OI Chg", "Futures OI Chg", "Future OI Chg",
                "fut_oi_chg", "futures_oi_chg",
            )
            oi_pct_col = _named_column(
                frame,
                "Total OI Chg (%)", "Total OI Chg %", "Total OI Change (%)",
                "Total OI Change %", "total_oi_chg_pct",
                "Fut OI Chg %", "Futures OI Chg %", "Future OI Chg %",
                "fut_oi_chg_pct", "futures_oi_chg_pct",
            )
            if symbol_col is None:
                return pd.DataFrame()
            result = pd.DataFrame({
                "symbol": frame[symbol_col].map(_canonical_symbol),
                "futures_oi_chg": _numeric_series(frame, oi_col),
                "futures_oi_chg_pct": _numeric_series(frame, oi_pct_col),
            })
            result = result[result["symbol"].ne("")].copy()
            return result.drop_duplicates("symbol")

        out = _build_ivrp_frame(raw)

        # Fallback only when the first worksheet does not expose the expected
        # IVR/IVP contract. This avoids reading all sheets during normal runs.
        if out.empty or not (out["futures_oi_chg"].notna().any() or out["futures_oi_chg_pct"].notna().any()):
            try:
                sheets = pd.read_excel(path, sheet_name=None)
                for sheet_df in sheets.values():
                    candidate = _build_ivrp_frame(_normalize_ivrp_export(sheet_df))
                    if not candidate.empty and (
                        candidate["futures_oi_chg"].notna().any()
                        or candidate["futures_oi_chg_pct"].notna().any()
                    ):
                        out = candidate
                        break
            except Exception:
                pass
        out = out[out["symbol"].ne("") & out["symbol"].ne("NAN")].copy()
        out = out.drop_duplicates("symbol")

        if out.empty:
            cache[key] = {
                "checked_at": now_epoch,
                "status": "pending",
                "data": pd.DataFrame(),
            }
            return pd.DataFrame()

        cache[key] = {
            "checked_at": now_epoch,
            "status": "complete",
            "data": out.copy(),
        }
        return out
    except Exception:
        cache[key] = {
            "checked_at": now_epoch,
            "status": "pending",
            "data": pd.DataFrame(),
        }
        return pd.DataFrame()

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


def _futures_mapping_stats(pred: pd.DataFrame | None) -> tuple[int, int]:
    """Return (mapped_rows, total_rows) for Futures evidence."""
    if pred is None or pred.empty or "symbol" not in pred.columns:
        return 0, 0
    future_cols = [
        c for c in ("futures_oi_chg", "futures_oi_chg_pct")
        if c in pred.columns
    ]
    if not future_cols:
        return 0, int(len(pred))
    numeric = pred[future_cols].apply(pd.to_numeric, errors="coerce")
    mapped = int(numeric.notna().any(axis=1).sum())
    return mapped, int(len(pred))


def _futures_mapping_complete(pred: pd.DataFrame | None) -> bool:
    mapped, total = _futures_mapping_stats(pred)
    return total > 0 and mapped == total


def _apply_futures_evidence_status(
    pred: pd.DataFrame,
    futures_evidence: pd.DataFrame | None,
    *,
    source_available: bool = False,
    source_pending: bool = False,
) -> pd.DataFrame:
    """Annotate Futures evidence independently of base snapshot validity.

    The Daywise/options snapshot remains valid even when IVR/IVP evidence is
    absent.  Status is row-level: MAPPED when a Futures value exists, D when
    an IVR/IVP source point was available but the symbol had no Futures value,
    and P when the companion source is not yet resolvable.
    """
    if pred is None or pred.empty:
        return pred
    out = pred.copy()
    if "symbol" not in out.columns:
        return out

    def key(series):
        v = series.astype(str).str.strip().str.upper()
        v = v.str.replace(r"^(?:NSE:|NFO:)", "", regex=True)
        v = v.str.replace(r"(?:\.NS|-EQ|-BE|-FUT|-FUTURES)$", "", regex=True)
        v = v.str.replace(r"\s+", "", regex=True)
        return v.where(v.ne("NAN"), "")

    mapped_keys = set()
    if isinstance(futures_evidence, pd.DataFrame) and not futures_evidence.empty and "symbol" in futures_evidence.columns:
        f = futures_evidence.copy()
        f["__key"] = key(f["symbol"])
        cols = [c for c in ("futures_oi_chg", "futures_oi_chg_pct") if c in f.columns]
        if cols:
            nums = f[cols].apply(pd.to_numeric, errors="coerce")
            mapped_keys = set(f.loc[nums.notna().any(axis=1), "__key"].astype(str))

    row_keys = key(out["symbol"])
    if source_available:
        status = row_keys.map(lambda x: "MAPPED" if x in mapped_keys else "D")
    elif source_pending:
        status = pd.Series("P", index=out.index)
    else:
        status = pd.Series("D", index=out.index)

    out["futures_evidence_status"] = status
    out["futures_data_available"] = status.eq("MAPPED")
    return out


def _merge_snapshot_evidence(
    df: pd.DataFrame,
    option_evidence: pd.DataFrame | None,
    futures_evidence: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge Daywise option evidence with authoritative IVR/IVP Futures evidence.

    Symbols are joined through a conservative NSE canonical key so common
    export decorations (NSE:, .NS, -EQ, -FUT) cannot create false UNMAPPED rows.
    The displayed Daywise symbol remains unchanged.
    """
    if df is None or df.empty or "symbol" not in df.columns:
        return df, pd.DataFrame()

    def _key(series: pd.Series) -> pd.Series:
        values = series.astype(str).str.strip().str.upper()
        values = values.str.replace(r"^(?:NSE:|NFO:)", "", regex=True)
        values = values.str.replace(r"(?:\.NS|-EQ|-BE|-FUT|-FUTURES)$", "", regex=True)
        values = values.str.replace(r"\s+", "", regex=True)
        return values.where(values.ne("NAN"), "")

    base = df.copy()
    base["__symbol_key"] = _key(base["symbol"])
    opt = option_evidence.copy() if isinstance(option_evidence, pd.DataFrame) else pd.DataFrame()
    fut = futures_evidence.copy() if isinstance(futures_evidence, pd.DataFrame) else pd.DataFrame()

    if not opt.empty and "symbol" in opt.columns:
        opt["__symbol_key"] = _key(opt["symbol"])
    if not fut.empty and "symbol" in fut.columns:
        fut["__symbol_key"] = _key(fut["symbol"])

    if opt.empty and fut.empty:
        evidence = pd.DataFrame({"__symbol_key": base["__symbol_key"]})
    elif fut.empty:
        evidence = opt.copy()
    elif opt.empty:
        evidence = fut.copy()
    else:
        evidence = opt.merge(fut, on="__symbol_key", how="outer", suffixes=("", "_ivrp"))
        for col in ("futures_oi_chg", "futures_oi_chg_pct"):
            ivrp_col = f"{col}_ivrp"
            if ivrp_col in evidence.columns:
                incoming = pd.to_numeric(evidence[ivrp_col], errors="coerce")
                existing = (
                    pd.to_numeric(evidence[col], errors="coerce")
                    if col in evidence.columns
                    else pd.Series(pd.NA, index=evidence.index)
                )
                evidence[col] = incoming.combine_first(existing)
                evidence.drop(columns=[ivrp_col], inplace=True)

    evidence = evidence.drop_duplicates("__symbol_key") if "__symbol_key" in evidence.columns else evidence
    enriched = base.copy()
    if "__symbol_key" in evidence.columns:
        lookup = evidence.set_index("__symbol_key")
        for col in (
            "futures_oi_chg", "futures_oi_chg_pct",
            "pe_minus_ce_oi_chg", "pe_minus_ce_oi_chg_pct", "pcr_chg_pct",
        ):
            if col in lookup.columns:
                enriched[col] = pd.to_numeric(
                    enriched["__symbol_key"].map(lookup[col]), errors="coerce"
                )
        enriched.drop(columns=["__symbol_key"], inplace=True)
    if "__symbol_key" in evidence.columns:
        evidence = evidence.drop(columns=["__symbol_key"])
    return enriched, evidence

def _day_option_evidence(daywise: pd.DataFrame) -> pd.DataFrame:
    """Extract the required option/PCR evidence by physical header name."""
    if daywise is None or daywise.empty:
        return pd.DataFrame()
    symbol_col = _named_column(daywise, "Symbol")
    if symbol_col is None:
        return pd.DataFrame()
    out = pd.DataFrame({"symbol": daywise[symbol_col].astype(str).str.strip().str.upper()})
    pece_col = _named_column(daywise, "Tot PE-CE OI Chg")
    pe_pct_col = _named_column(daywise, "Tot PE OI Chg %")
    ce_pct_col = _named_column(daywise, "Tot CE OI Chg %")
    pcr_pct_col = _named_column(daywise, "PCR Chg %")
    out["pe_minus_ce_oi_chg"] = _numeric_series(daywise, pece_col)
    pe_pct = _numeric_series(daywise, pe_pct_col)
    ce_pct = _numeric_series(daywise, ce_pct_col)
    out["pe_minus_ce_oi_chg_pct"] = pe_pct - ce_pct
    out["pcr_chg_pct"] = _numeric_series(daywise, pcr_pct_col)
    return out[out["symbol"].ne("") & out["symbol"].ne("NAN")].drop_duplicates("symbol")


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
        incoming = pd.to_numeric(out["symbol"].map(lookup[col]), errors="coerce") if col in lookup.columns else pd.Series(pd.NA, index=out.index)
        out[col] = existing.where(existing.notna(), incoming)
    return out


@st.cache_data(ttl=300, show_spinner=False)
@st.cache_data(ttl=120, show_spinner=False)
@st.cache_data(ttl=300, show_spinner=False)
def _replay_date_index() -> tuple[str, ...]:
    """Return Replay trading days from lightweight Daywise filenames only.

    This is UI metadata discovery. It never opens workbooks, calls the full
    historical snapshot resolver, or touches PIT payloads.
    """
    root = Path(getattr(sdl_config, "INTRADAY_SOURCE_ROOT", ""))
    if not root.exists() or not root.is_dir():
        return tuple()

    days = set()
    date_re = re.compile(r"(?<!\\d)(20\\d{2}-\\d{2}-\\d{2})(?!\\d)")
    try:
        paths = root.rglob("Daywise_Price_and_OI_Summary*.xlsx")
        for path in paths:
            m = date_re.search(path.name)
            if m:
                days.add(m.group(1))
    except Exception:
        return tuple()
    return tuple(sorted(days, reverse=True))


@st.cache_data(ttl=300, show_spinner=False)
def _calendar_month_day_files(selected_month: str) -> dict[str, list[Path]]:
    """Return Daywise paths for one month from filenames only.

    Exact observation timestamp resolution remains deferred to the selected
    day/snapshot path.
    """
    month = str(selected_month)[:7]
    root = Path(getattr(sdl_config, "INTRADAY_SOURCE_ROOT", ""))
    grouped: dict[str, list[Path]] = {}
    if not root.exists() or not root.is_dir():
        return grouped

    date_re = re.compile(r"(?<!\\d)(20\\d{2}-\\d{2}-\\d{2})(?!\\d)")
    try:
        paths = root.rglob("Daywise_Price_and_OI_Summary*.xlsx")
        for path in paths:
            m = date_re.search(path.name)
            if not m or not m.group(1).startswith(month):
                continue
            grouped.setdefault(m.group(1), []).append(path)
    except Exception:
        return grouped

    for day, items in grouped.items():
        grouped[day] = sorted(items, key=lambda p: str(p).lower())
    return grouped


@st.cache_data(ttl=5, show_spinner=False)
def _day_cache_summary(trading_date: str, files=None) -> dict:
    """Read persistent base-snapshot and independent Futures status.

    Five-second UI cache reduces calendar rerun cost without masking a build
    completion for long periods. Replay point selection itself remains uncached.
    """
    day = str(trading_date)[:10]
    files = list(files) if files is not None else snapshot_files(day)
    source_keys = []
    for path in files:
        ts = observation_ts(path)
        if pd.notna(ts):
            source_keys.append(pd.Timestamp(ts).isoformat())
    source_keys = list(dict.fromkeys(source_keys))

    cache = _load_day_point_cache()
    day_cache = cache.get(day, {}) if isinstance(cache, dict) else {}
    entries = day_cache.get("snapshots", {}) if isinstance(day_cache.get("snapshots", {}), dict) else {}

    cached = 0
    futures_complete = 0
    futures_unavailable = 0
    futures_pending = 0
    for key in source_keys:
        entry = entries.get(key)
        if not isinstance(entry, dict) or not isinstance(entry.get("pred"), pd.DataFrame):
            continue
        cached += 1
        pred = entry.get("pred")
        status = str(entry.get("futures_status", "")).upper()
        if status == "MAPPED":
            futures_complete += 1
        elif status == "D":
            futures_unavailable += 1
        elif status == "P":
            futures_pending += 1
        else:
            mapped, total = _futures_mapping_stats(pred)
            if total > 0 and mapped == total:
                futures_complete += 1
            elif total > 0 and mapped < total:
                # Legacy entries with partial Futures are retained as valid
                # base snapshots; they are pending migration to row-level D/P.
                futures_pending += 1

    missing = max(0, len(source_keys) - cached)
    return {
        "day": day,
        "source_count": len(source_keys),
        "cached_count": cached,
        "complete_count": futures_complete,
        "futures_complete_count": futures_complete,
        "futures_partial_count": sum(1 for key in source_keys if isinstance(entries.get(key), dict) and str(entries.get(key, {}).get("futures_status", "")).upper() == "PARTIAL"),
        "futures_unavailable_count": futures_unavailable,
        "futures_pending_count": futures_pending,
        "pending_count": futures_pending,
        "missing_count": missing,
        "ready": bool(source_keys) and cached == len(source_keys),
    }

def _day_cache_marker(summary: dict) -> str:
    source_count = int(summary.get("source_count", 0))
    cached_count = int(summary.get("cached_count", 0))
    pending_count = int(summary.get("futures_pending_count", summary.get("pending_count", 0)))
    if source_count <= 0:
        return "⚪"
    if cached_count <= 0:
        return "🔴"
    if cached_count < source_count:
        return "🟠"
    if pending_count > 0:
        return "🟡"
    return "🟢"


def build_day_point_in_time_cache(trading_date: str, progress_callback=None) -> dict:
    """Build/complete one historical day cache, chronologically, once.

    Existing complete points are immutable. Pending points are retried only
    through the authoritative IVR/IVP resolver. LIVE state is never changed.
    """
    day = str(trading_date)[:10]
    if not day:
        return {}
    files = snapshot_files(day)
    if not files:
        return {}

    cache = _load_day_point_cache()
    day_cache = cache.get(day, {}) if isinstance(cache.get(day, {}), dict) else {}
    entries = day_cache.get("snapshots", {}) if isinstance(day_cache.get("snapshots", {}), dict) else {}

    state = load_state(STATE_JSON)
    base = state.get("daily_opening_straddles", {}).get(day) if isinstance(state, dict) else None
    if not base:
        first_df, _ = load_primary_snapshot(files[0], observation_ts(files[0]))
        base = frozen_base_from_df(derive_straddle_values(first_df))

    total_files = len(files)
    processed_files = 0
    completed_files = 0
    pending_files = 0
    skipped_files = 0

    for path in files:
        ts = observation_ts(path)
        processed_files += 1
        if pd.isna(ts):
            skipped_files += 1
            if progress_callback:
                progress_callback(processed_files, total_files, completed_files, pending_files, skipped_files, path.name)
            continue
        key = pd.Timestamp(ts).isoformat()
        existing = entries.get(key) if isinstance(entries.get(key), dict) else None
        if existing and isinstance(existing.get("pred"), pd.DataFrame):
            existing_pred = existing.get("pred")
            # Base snapshot completeness is independent of Futures evidence.
            # Preserve existing complete base points, while allowing pending
            # Futures evidence to be refreshed by the resolver below.
            if str(existing.get("snapshot_status", "VALID")).upper() == "VALID":
                fut_status = str(existing.get("futures_status", "")).upper()
                if fut_status in {"MAPPED", "D"}:
                    completed_files += 1
                    if progress_callback:
                        progress_callback(processed_files, total_files, completed_files, pending_files, skipped_files, path.name)
                    continue

        try:
            raw, loaded_ts = load_primary_snapshot(path, ts)
            loaded_ts = pd.to_datetime(loaded_ts, errors="coerce")
            if pd.isna(loaded_ts) or raw is None or raw.empty:
                continue
            raw = derive_straddle_values(raw)
            option_ev = _day_option_evidence(raw)
            future_ev = _read_ivrp_for_timestamp(
                day, loaded_ts, force_refresh=True
            )

            pred = candidates(
                raw,
                base or {},
                snapshot_ts=loaded_ts,
                snapshot_path=None,
                first_alert_signature=_first_alert_source_signature(
                    pd.Timestamp(loaded_ts).date().isoformat()
                ),
            )
            pred, evidence = _merge_snapshot_evidence(
                pred, option_ev, future_ev
            ) if "_merge_snapshot_evidence" in globals() else (
                pred, option_ev.merge(future_ev, on="symbol", how="outer", suffixes=("", "_future"))
            )

            # Futures is an optional evidence layer.  A missing companion
            # must never invalidate the Daywise/options snapshot.
            source_available = isinstance(future_ev, pd.DataFrame) and not future_ev.empty
            if source_available:
                pred = _apply_futures_evidence_status(pred, future_ev, source_available=True)
                row_status = pred["futures_evidence_status"]
                fut_status = (
                    "MAPPED" if row_status.eq("MAPPED").all()
                    else "PARTIAL" if row_status.eq("MAPPED").any()
                    else "D"
                )
            else:
                # No eligible IVR/IVP workbook was resolvable at this point.
                # Keep the base snapshot VALID and leave Futures as pending so
                # a later controlled build can retry it; only a present IVR/IVP
                # workbook with a missing symbol is a genuine row-level D.
                pred = _apply_futures_evidence_status(pred, future_ev, source_pending=True)
                fut_status = "P"
            status = "complete" if _futures_mapping_complete(pred) else "partial"
            entries[key] = {
                "timestamp": pd.Timestamp(loaded_ts).isoformat(),
                "source_path": str(path),
                "pred": pred.copy(),
                "evidence": evidence.copy(),
                "snapshot_status": "VALID",
                "futures_status": fut_status,
                # Legacy field retained for compatibility with existing cache readers.
                "evidence_status": status,
            }
        except Exception:
            skipped_files += 1
            if progress_callback:
                progress_callback(processed_files, total_files, completed_files, pending_files, skipped_files, path.name)
            continue

        if status == "complete":
            completed_files += 1
        else:
            pending_files += 1
        if progress_callback:
            progress_callback(processed_files, total_files, completed_files, pending_files, skipped_files, path.name)

    ordered = dict(sorted(entries.items(), key=lambda kv: kv[0]))
    cache[day] = {
        "cache_schema": DAY_POINT_CACHE_SCHEMA,
        "trading_date": day,
        "latest_timestamp": next(reversed(ordered), None) if ordered else None,
        "snapshots": ordered,
        "source_count": len(files),
    }
    _save_day_point_cache(cache)
    return cache[day]

@st.cache_data(ttl=300, show_spinner=False)
def _available_replay_days() -> list[str]:
    """Return all historical trading days for which Daywise source data exists."""
    grouped: set[str] = set()
    try:
        paths = discover_historical_snapshots(None)
    except Exception:
        paths = []
    for raw_path in paths or []:
        try:
            ts = observation_ts(Path(raw_path))
            if pd.notna(ts):
                grouped.add(pd.Timestamp(ts).strftime("%Y-%m-%d"))
        except Exception:
            continue
    return sorted(grouped)


def build_all_available_day_point_in_time_cache(progress_callback=None) -> dict:
    """Build/complete every available historical day sequentially.

    This is the controlled bulk equivalent of pressing BUILD / COMPLETE on
    each calendar day. Existing complete point-in-time entries remain
    immutable; pending/incomplete points are processed through the same
    single-day builder. LIVE state is never modified.
    """
    days = _available_replay_days()
    results = {}
    total_days = len(days)
    for day_index, day in enumerate(days, start=1):
        day_result = build_day_point_in_time_cache(
            day,
            progress_callback=(
                (lambda done, total, complete, pending, skipped, filename,
                        di=day_index, td=total_days, d=day:
                    progress_callback(
                        di, td, d, done, total, complete, pending, skipped, filename
                    ))
                if progress_callback
                else None
            ),
        )
        results[day] = day_result
    return results


def attach_point_in_time_oi(df: pd.DataFrame, snapshot_path: Path, snapshot_ts: pd.Timestamp) -> pd.DataFrame:
    if df is None or df.empty or snapshot_path is None or pd.isna(snapshot_ts):
        return df
    evidence = point_in_time_oi_evidence(snapshot_path, snapshot_ts)
    if evidence.empty or "symbol" not in df.columns:
        return df
    out = df.copy()
    lookup = evidence.set_index("symbol")
    for col in ("futures_oi_chg", "futures_oi_chg_pct", "pe_minus_ce_oi_chg", "pe_minus_ce_oi_chg_pct"):
        if col not in out.columns:
            out[col] = out["symbol"].map(lookup[col]) if col in lookup.columns else pd.NA
        else:
            existing = pd.to_numeric(out[col], errors="coerce")
            enriched = pd.to_numeric(out["symbol"].map(lookup[col]), errors="coerce") if col in lookup.columns else pd.Series(pd.NA, index=out.index)
            out[col] = existing.where(existing.notna(), enriched)
    return out


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


def _first_alert_source_signature(trading_date: str | None) -> tuple:
    """Return a hashable source/state signature for First Alert cache invalidation.

    LIVE/Replay refreshes are keyed to actual source/state file changes rather
    than a blind wall-clock TTL. File stat data is intentionally lightweight;
    the expensive evidence parsing remains behind the cached worker below.
    """
    if not trading_date:
        return ()

    day = str(trading_date)[:10]
    entries = []
    for path in snapshot_files(day):
        try:
            stat = path.stat()
            mtime_ns = int(stat.st_mtime_ns)
            size = int(stat.st_size)
        except Exception:
            mtime_ns = 0
            size = 0
        ts = observation_ts(path)
        if pd.notna(ts):
            entries.append((str(path), pd.Timestamp(ts).isoformat(), mtime_ns, size))

    state_paths = [Path(STATE_JSON)]
    # Some SDL runtime deployments persist carried alert provenance in the
    # dashboard directory as processing_state.json. Treat it as an additional
    # durable source, never as a generated/current-observation fallback.
    sibling_processing_state = Path(__file__).resolve().parent / "processing_state.json"
    if sibling_processing_state not in state_paths:
        state_paths.append(sibling_processing_state)

    state_sig_parts = []
    for state_path in state_paths:
        try:
            stt = state_path.stat()
            state_sig_parts.append((str(state_path), int(stt.st_mtime_ns), int(stt.st_size)))
        except Exception:
            state_sig_parts.append((str(state_path), 0, 0))
    state_sig = tuple(state_sig_parts)

    evidence_path = Path(REQUIRED_EVIDENCE_DIR) / f"{day}.csv"
    evidence_sig = (0, 0)
    try:
        ett = evidence_path.stat()
        evidence_sig = (int(ett.st_mtime_ns), int(ett.st_size))
    except Exception:
        pass

    return (tuple(entries), state_sig, evidence_sig)


@st.cache_data(show_spinner=False)
def _first_alert_map_cached(
    trading_date: str | None,
    cutoff_iso: str | None,
    source_signature: tuple,
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

    source_times = [pd.Timestamp(item[1]) for item in source_signature[0]]
    if not source_times:
        return {}

    cutoff = pd.Timestamp(cutoff_iso) if cutoff_iso else None
    result: dict[str, pd.Timestamp] = {}

    # ------------------------------------------------------------------
    # 1) Durable SDL first-alert state — established carried provenance.
    # ------------------------------------------------------------------
    # Runtime variants exist for the durable state layout. In particular,
    # processing_state.json can store: trading_day -> symbol ->
    # first_alert_timestamp. Read those exact carried timestamps and validate
    # them against real Daywise observations before displaying them.
    state_candidates = []
    try:
        state_candidates.append(load_state(STATE_JSON))
    except Exception:
        state_candidates.append({})

    sibling_processing_state = Path(__file__).resolve().parent / "processing_state.json"
    if sibling_processing_state.exists() and sibling_processing_state != Path(STATE_JSON):
        try:
            raw_processing = json.loads(
                sibling_processing_state.read_text(encoding="utf-8")
            )
            if isinstance(raw_processing, dict):
                state_candidates.append(raw_processing)
        except Exception:
            pass

    def _first_alert_day_maps(state: dict) -> list[dict]:
        if not isinstance(state, dict):
            return []
        day = str(trading_date)[:10]
        maps = []

        # Established SDL first_alerts layouts.
        first_alerts = state.get("first_alerts")
        if isinstance(first_alerts, dict) and isinstance(first_alerts.get(day), dict):
            maps.append(first_alerts.get(day))

        per_day = state.get(day)
        if isinstance(per_day, dict):
            if isinstance(per_day.get("first_alerts"), dict):
                maps.append(per_day.get("first_alerts"))
            # processing_state.json layout: day -> symbol -> payload.
            maps.append(per_day)

        decision_state = state.get("decision_state")
        if isinstance(decision_state, dict):
            ds_day = decision_state.get(day)
            if isinstance(ds_day, dict):
                if isinstance(ds_day.get("first_alerts"), dict):
                    maps.append(ds_day.get("first_alerts"))
                maps.append(ds_day)

        processing_state = state.get("processing_state")
        if isinstance(processing_state, dict):
            ps_day = processing_state.get(day)
            if isinstance(ps_day, dict):
                maps.append(ps_day.get("first_alerts", ps_day))

        return [item for item in maps if isinstance(item, dict)]

    alert_aliases = (
        "first_alert_timestamp",
        "first_trigger_timestamp",
        "first_alert_time",
        "first_seen_timestamp",
        "first_detection_timestamp",
        "trigger_timestamp",
        "decision_timestamp",
        "alert_timestamp",
        "alert_time",
        "timestamp",
    )

    for state in state_candidates:
        for day_map in _first_alert_day_maps(state):
            for symbol, payload in day_map.items():
                symbol = str(symbol).strip().upper()
                if not symbol or symbol in {"FIRST_ALERTS", "SYMBOLS", "META"}:
                    continue

                raw_ts = None
                if isinstance(payload, dict):
                    for alias in alert_aliases:
                        if alias in payload:
                            raw_ts = payload.get(alias)
                            break
                else:
                    raw_ts = payload

                ts = pd.to_datetime(raw_ts, errors="coerce")
                if pd.isna(ts):
                    continue
                # IMPORTANT: first_alert_timestamp is the durable event
                # timestamp. It is NOT required to equal the timestamp of the
                # snapshot whose row currently carries the state. Historical
                # state proves this: e.g. HAVELLS 09:28:38 can be carried by
                # a later 13:37:27 snapshot. Requiring exact source-file time
                # equality suppresses valid First Alert values.
                #
                # Source integrity is preserved by requiring the timestamp to
                # belong to the same trading day and to be within the observed
                # source-session time range when source observations exist.
                if pd.Timestamp(ts).date().isoformat() != str(trading_date)[:10]:
                    continue
                if source_times:
                    earliest_source = min(source_times)
                    latest_source = max(source_times)
                    if ts < earliest_source or ts > latest_source:
                        continue
                if cutoff is not None and ts > cutoff:
                    continue
                # Earlier durable state is retained; later sources cannot
                # overwrite an already-established carried timestamp.
                result.setdefault(symbol, pd.Timestamp(ts))

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
            # The observation timestamp must be a real source observation.
            # The First Alert timestamp itself may be between snapshot file
            # timestamps; it is an event timestamp carried by durable state,
            # not necessarily the timestamp encoded in the later evidence row.
            e = e[
                e["observation_timestamp"].map(lambda x: _matches_source_snapshot(x, source_times))
            ]
            e = e[
                e["_alert_timestamp"].dt.date.astype(str).eq(str(trading_date)[:10])
            ]
            if source_times and not e.empty:
                earliest_source = min(source_times)
                latest_source = max(source_times)
                e = e[
                    e["_alert_timestamp"].between(earliest_source, latest_source, inclusive="both")
                ]
            if cutoff is not None:
                e = e[e["_alert_timestamp"] <= cutoff]
            if not e.empty:
                for symbol, ts in e.groupby("Symbol")["_alert_timestamp"].min().items():
                    # Durable state wins when both sources contain a value.
                    result.setdefault(symbol, pd.Timestamp(ts))

    return result


def first_alert_map(
    trading_date: str | None = None,
    cutoff_ts: pd.Timestamp | None = None,
) -> dict[str, pd.Timestamp]:
    """Public First Alert lookup keyed to actual source/state changes."""
    if not trading_date:
        return {}
    cutoff = pd.Timestamp(cutoff_ts) if cutoff_ts is not None and pd.notna(cutoff_ts) else None
    cutoff_iso = cutoff.isoformat() if cutoff is not None else None
    signature = _first_alert_source_signature(trading_date)
    return _first_alert_map_cached(str(trading_date)[:10], cutoff_iso, signature)


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

def _reconstruct_first_alert_map_from_replay(
    trading_date: str | None,
    cutoff_ts: pd.Timestamp | None,
    current_df: pd.DataFrame | None = None,
    current_snapshot_ts: pd.Timestamp | None = None,
) -> dict[str, pd.Timestamp]:
    """Reconstruct missing First Alert provenance from chronological SDL points.

    The opening/base snapshot is deliberately excluded: it establishes the
    frozen opening base and is not itself a First Alert.  From the first
    subsequent source point onward, the first timestamp at which a symbol is
    present in the existing decision-candidate dataframe is retained.  That
    timestamp is then carried forward to later points while the symbol remains
    in the current candidate/queue dataset.

    This is presentation/provenance reconstruction only.  It does not alter
    the SDL decision engine, candidate gates, scoring, or replay chronology.
    """
    if not trading_date:
        return {}

    day = str(trading_date)[:10]
    cutoff = pd.to_datetime(cutoff_ts, errors="coerce") if cutoff_ts is not None else pd.NaT
    if pd.isna(cutoff):
        cutoff = None

    result: dict[str, pd.Timestamp] = {}

    # First use the already persisted chronological replay cache.  This makes
    # First Alert stable across reruns and does not require recalculating source
    # workbooks.
    try:
        cache = _load_day_point_cache()
        day_cache = cache.get(day, {}) if isinstance(cache, dict) else {}
        entries = day_cache.get("snapshots", {}) if isinstance(day_cache.get("snapshots", {}), dict) else {}
    except Exception:
        entries = {}

    ordered = []
    for key, entry in entries.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("pred"), pd.DataFrame):
            continue
        ts = pd.to_datetime(entry.get("timestamp", key), errors="coerce")
        if pd.isna(ts) or ts.date().isoformat() != day:
            continue
        if cutoff is not None and ts > cutoff:
            continue
        ordered.append((pd.Timestamp(ts), entry.get("pred")))
    ordered.sort(key=lambda item: item[0])

    # The earliest point is the frozen opening/base observation and is never an
    # alert source.  Subsequent candidate observations are eligible.
    if ordered:
        base_ts = ordered[0][0]
        for ts, pred in ordered[1:]:
            if "symbol" not in pred.columns:
                continue
            for symbol in pred["symbol"].astype(str).str.strip().str.upper():
                if symbol and symbol not in {"NAN", "NONE"} and symbol not in result:
                    result[symbol] = ts

    # Include the currently evaluated point because it is not yet persisted in
    # the day cache while candidates() is executing.  This removes the previous
    # one-snapshot lag in First Alert reconstruction.
    if (
        isinstance(current_df, pd.DataFrame)
        and not current_df.empty
        and "symbol" in current_df.columns
        and current_snapshot_ts is not None
    ):
        current_ts = pd.to_datetime(current_snapshot_ts, errors="coerce")
        if pd.notna(current_ts) and current_ts.date().isoformat() == day:
            # Never treat the opening/base point as an alert.
            is_base = bool(ordered and current_ts <= ordered[0][0])
            if not is_base and (cutoff is None or current_ts <= cutoff):
                for symbol in current_df["symbol"].astype(str).str.strip().str.upper():
                    if symbol and symbol not in {"NAN", "NONE"} and symbol not in result:
                        result[symbol] = pd.Timestamp(current_ts)

    return result



def _frame_symbols(frame: pd.DataFrame) -> list[str]:
    """Return canonical symbols from a cached/live decision frame.

    Replay cache entries from different SDL revisions may expose either the
    dashboard ``symbol`` column or the original pipeline ``Symbol`` column.
    First Alert reconstruction must understand both layouts.
    """
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    column = next(
        (name for name in ("symbol", "Symbol", "STOCK", "Stock") if name in frame.columns),
        None,
    )
    if column is None:
        return []
    values = frame[column].astype(str).str.strip().str.upper()
    return [
        value for value in values.tolist()
        if value and value not in {"NAN", "NONE", "NA", "<NA>"}
    ]


def _first_alert_map_from_chronological_cache(
    trading_date: str | None,
    cutoff_ts: pd.Timestamp | None = None,
) -> dict[str, pd.Timestamp]:
    """Build the carried First Alert map from the persisted point-in-time cache.

    Contract:
      * the first Daywise snapshot is the frozen BASE and can never create an alert;
      * the first subsequent cached snapshot containing a symbol in the existing
        SDL decision dataset becomes that symbol's First Alert;
      * once established, that timestamp is carried to later snapshots;
      * durable First Alert state remains authoritative when it exists;
      * this function never evaluates or changes SDL gates/scoring.
    """
    if not trading_date:
        return {}

    day = str(trading_date)[:10]
    cutoff = pd.to_datetime(cutoff_ts, errors="coerce") if cutoff_ts is not None else pd.NaT
    if pd.isna(cutoff):
        cutoff = None

    # Start with durable provenance.  This preserves any already-established
    # event timestamp and lets reconstruction fill only genuine gaps.
    result = dict(first_alert_map(day, cutoff))

    try:
        cache = _load_day_point_cache()
        day_cache = cache.get(day, {}) if isinstance(cache, dict) else {}
        entries = day_cache.get("snapshots", {}) if isinstance(day_cache, dict) else {}
    except Exception:
        entries = {}

    if not isinstance(entries, dict) or not entries:
        return result

    ordered: list[tuple[pd.Timestamp, pd.DataFrame]] = []
    for key, entry in entries.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("pred"), pd.DataFrame):
            continue
        ts = pd.to_datetime(entry.get("timestamp", key), errors="coerce")
        if pd.isna(ts) or ts.date().isoformat() != day:
            continue
        ts = pd.Timestamp(ts)
        if cutoff is not None and ts > cutoff:
            continue
        ordered.append((ts, entry["pred"]))

    ordered.sort(key=lambda item: item[0])
    if len(ordered) <= 1:
        return result

    # The earliest source point is BASE only.  Never create First Alert from it.
    for ts, pred in ordered[1:]:
        for symbol in _frame_symbols(pred):
            result.setdefault(symbol, ts)

    return result


def _attach_first_alert_provenance(
    df: pd.DataFrame,
    trading_date: str | None,
    cutoff_ts: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Attach the same carried First Alert to every current decision row.

    This is deliberately a presentation/provenance layer.  It is applied after
    reading persisted LIVE/Replay cache entries as well as to newly-built rows,
    because those persisted entries may have been created before First Alert
    display reconstruction existed.
    """
    if df is None or df.empty or not trading_date:
        return df

    out = df.copy()
    symbol_col = next(
        (name for name in ("symbol", "Symbol", "STOCK", "Stock") if name in out.columns),
        None,
    )
    if symbol_col is None:
        return out

    first_map = _first_alert_map_from_chronological_cache(trading_date, cutoff_ts)
    if not first_map:
        return out

    symbols = out[symbol_col].astype(str).str.strip().str.upper()
    carried = symbols.map(first_map)

    # Preserve an already-valid explicit timestamp; only fill the historical
    # gaps that caused the dashboard's blank First Alert cells.
    existing = pd.to_datetime(
        out.get("first_trigger_timestamp", pd.Series(pd.NaT, index=out.index)),
        errors="coerce",
    )
    existing = existing.where(existing.notna(), pd.to_datetime(
        out.get("first_alert_timestamp", pd.Series(pd.NaT, index=out.index)),
        errors="coerce",
    ))
    merged = existing.where(existing.notna(), carried)

    if cutoff_ts is not None and pd.notna(cutoff_ts):
        cutoff = pd.Timestamp(cutoff_ts)
        merged = merged.mask(pd.to_datetime(merged, errors="coerce") > cutoff, pd.NaT)

    out["first_trigger_timestamp"] = pd.to_datetime(merged, errors="coerce")
    out["first_alert_timestamp"] = out["first_trigger_timestamp"]
    return out


def add_first_times(
    df: pd.DataFrame,
    trading_date: str | None = None,
    cutoff_ts: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    first_map = first_alert_map(trading_date, cutoff_ts)

    # Durable state is authoritative when present.  If durable state is absent
    # for a symbol, reconstruct its first qualifying post-base observation from
    # the chronological replay cache/current point.  This is the missing bridge
    # that caused First Alert to remain blank while First Breakout was populated.
    reconstructed = _reconstruct_first_alert_map_from_replay(
        trading_date,
        cutoff_ts,
        current_df=out,
        current_snapshot_ts=(
            pd.to_datetime(out["observation_timestamp"], errors="coerce").dropna().iloc[0]
            if "observation_timestamp" in out.columns
            and not pd.to_datetime(out["observation_timestamp"], errors="coerce").dropna().empty
            else None
        ),
    )
    for symbol, ts in reconstructed.items():
        first_map.setdefault(symbol, ts)

    out["first_trigger_timestamp"] = out["symbol"].map(first_map)
    # Keep the durable field name available to every presentation path.
    # first_trigger_timestamp remains the canonical dashboard display alias.
    out["first_alert_timestamp"] = out["first_trigger_timestamp"]
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
    first_alert_signature: tuple | None = None,
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

    if snapshot_path is not None and snapshot_ts is not None and pd.notna(snapshot_ts):
        out = attach_point_in_time_oi(out, snapshot_path, snapshot_ts)

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

def _parse_data_filter(value: str):
    """Parse a compact filter expression without changing the legacy Min behavior.

    Bare numbers remain minimum thresholds (>=).  Optional comparison operators
    allow upper-bound/short-covering queries such as ``<-100000`` without adding
    extra controls or changing the existing UI footprint.
    """
    try:
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        match = re.fullmatch(r"(<=|>=|<|>|=)?\s*(-?(?:\d+(?:\.\d*)?|\.\d+))", text)
        if not match:
            return None
        operator = match.group(1) or ">="
        return operator, float(match.group(2))
    except (TypeError, ValueError):
        return None


def apply_data_filters(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    """Frozen OI/PCR filters: four minimum-only thresholds."""
    if df is None or df.empty:
        return df

    with st.expander("DATA FILTERS · OI / PCR", expanded=False):
        cols = st.columns(4)
        specs = [
            (cols[0], "FUTURES OI CHANGE", "futures_oi_chg", [
                "futures_oi_chg", "Futures OI Change", "Future OI Change",
                "Futures OI Δ", "Future OI Δ", "futures_oi_change", "future_oi_change",
            ]),
            (cols[1], "FUTURES OI CHANGE %", "futures_oi_chg_pct", [
                "futures_oi_chg_pct", "Futures OI Change %", "Future OI Change %",
                "Futures OI Chg %", "Future OI Chg %", "futures_oi_change_pct",
                "future_oi_change_pct",
            ]),
            (cols[2], "OPTION OI CHANGE (PE−CE)", "pe_minus_ce_oi_chg", [
                "pe_minus_ce_oi_chg", "PE_CE_OI_Chg", "PE-CE OI Change",
                "PE−CE OI Change", "PE-CE OI Δ", "PE−CE OI Δ",
                "pe_minus_ce_oi", "pe_ce_oi_change", "pe_minus_ce_oi_change",
            ]),
            (cols[3], "PCR CHANGE %", "pcr_chg_pct", [
                "pcr_chg_pct", "PCR Chg %", "PCR Change %", "PCR Δ %",
                "PCR_Chg_Pct", "pcr_change_pct",
            ]),
        ]
        filters = {}
        for col, label, canonical, aliases in specs:
            with col:
                st.markdown(
                    f'<div class="filter-title">{label}</div>',
                    unsafe_allow_html=True,
                )
                source = next((a for a in aliases if a in df.columns), None)
                if source is None:
                    st.caption("No data")
                    filters[canonical] = None
                    continue

                vals = pd.to_numeric(df[source], errors="coerce").dropna()
                if vals.empty:
                    st.caption("No data")
                    filters[canonical] = None
                    continue

                expression = st.text_input(
                    "Filter",
                    key=f"{key_prefix}_{canonical}_min",
                    placeholder="Min / <value / >value",
                    label_visibility="collapsed",
                )
                filters[canonical] = _parse_data_filter(expression)

    aliases_by_canonical = {
        "futures_oi_chg": [
            "futures_oi_chg", "Futures OI Change", "Future OI Change",
            "Futures OI Δ", "Future OI Δ", "futures_oi_change", "future_oi_change",
        ],
        "futures_oi_chg_pct": [
            "futures_oi_chg_pct", "Futures OI Change %", "Future OI Change %",
            "Futures OI Chg %", "Future OI Chg %", "futures_oi_change_pct",
            "future_oi_change_pct",
        ],
        "pe_minus_ce_oi_chg": [
            "pe_minus_ce_oi_chg", "PE_CE_OI_Chg", "PE-CE OI Change",
            "PE−CE OI Change", "PE-CE OI Δ", "PE−CE OI Δ",
            "pe_minus_ce_oi", "pe_ce_oi_change", "pe_minus_ce_oi_change",
        ],
        "pcr_chg_pct": [
            "pcr_chg_pct", "PCR Chg %", "PCR Change %", "PCR Δ %",
            "PCR_Chg_Pct", "pcr_change_pct",
        ],
    }

    out = df.copy()
    for canonical, minimum in filters.items():
        if minimum is None:
            continue
        source = next(
            (a for a in aliases_by_canonical[canonical] if a in out.columns),
            None,
        )
        if source is None:
            continue
        operator, threshold = minimum
        values = pd.to_numeric(out[source], errors="coerce")
        if operator == "<":
            mask = values.lt(threshold)
        elif operator == "<=":
            mask = values.le(threshold)
        elif operator == ">":
            mask = values.gt(threshold)
        elif operator == "=":
            mask = values.eq(threshold)
        else:
            # Legacy behavior: a bare number is still a minimum threshold.
            mask = values.ge(threshold)
        out = out[mask]
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

def queue_html(df: pd.DataFrame, replay_mode: bool = False) -> str:
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
        futures_oi_pct = metric(row, [
            "futures_oi_chg_pct", "Futures OI Change %", "Future OI Change %",
            "Futures OI Chg %", "Future OI Chg %", "futures_oi_change_pct",
            "future_oi_change_pct",
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

        futures_missing = futures_oi is None and futures_oi_pct is None
        futures_status = str(row.get("futures_oi_status", "")).strip().upper()
        futures_delayed = bool(row.get("futures_oi_delayed", False)) or futures_status == "DELAYED"
        delayed_badge = (
            ' <span class="badge badge-yellow" title="Last successfully processed Futures evidence; delayed">D</span>'
            if futures_delayed
            else ""
        )
        if replay_mode and futures_missing:
            futures_oi_display = '<span class="badge badge-yellow" title="Futures data not available in the point-in-time IVR/IVP source">D</span>'
            futures_oi_pct_display = futures_oi_display
        else:
            futures_oi_display = fmt_oi(futures_oi) + delayed_badge if futures_oi is not None and not pd.isna(futures_oi) else (delayed_badge or "—")
            futures_oi_pct_display = fmt_pct_value(futures_oi_pct) + delayed_badge if futures_oi_pct is not None and not pd.isna(futures_oi_pct) else (delayed_badge or "—")

        rows.append(
            "<tr>"
            f"<td>{i}</td>"
            f'<td><div class="stock-cell">{logo(row.get("symbol"))}'
            f'<span>{safe_text(str(row.get("symbol","")).upper())}</span></div></td>'
            f'<td><span class="badge {badge_class(row)}">'
            f'{safe_text(direction.title())} · '
            f'{safe_text(strength_label.title())}</span></td>'
            f'<td class="{price_class}">{pct(price)}</td>'
            f'<td class="{change_class(futures_oi)}">{futures_oi_display}</td>'
            f'<td class="{change_class(futures_oi_pct)}">{futures_oi_pct_display}</td>'
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
        '<th style="width:7%">FUTURES OI CHG %</th>'
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


@st.cache_data(ttl=900, show_spinner=False)

def impact_hint(text: str) -> str:
    value = str(text or "").casefold()
    negative = ("loss","decline","downgrade","penalty","fine","default","fraud","litigation","investigation","resignation","delay","cancel","weak","warning","cut","probe","regulatory action","concern")
    positive = ("order","contract","award","approval","acquisition","investment","expansion","capacity","results","earnings","profit","guidance","upgrade","deal","stake","support","growth","launch")
    neg = sum(term in value for term in negative)
    pos = sum(term in value for term in positive)
    return "POSITIVE" if pos > neg else "NEGATIVE" if neg > pos else "NEUTRAL"

def _news_item_text(item: dict) -> str:
    return str(item.get("text") or item.get("title") or item.get("headline") or "").strip()

def _news_item_time(item: dict) -> str:
    return str(item.get("time") or item.get("timestamp") or item.get("published") or "News").strip()

def _news_item_source(item: dict) -> str:
    return str(item.get("source") or "Google News").strip()

def _news_item_impact(item: dict) -> str:
    return str(item.get("impact") or impact_hint(_news_item_text(item)))

def _news_item_symbol(item: dict) -> str:
    return str(item.get("symbol") or item.get("stock") or item.get("ticker") or "").strip().upper()

def _news_is_junk(text: str) -> bool:
    value = str(text or "").casefold()
    junk = ("price target","target price","forecast","prediction","technical analysis","technical outlook","watchlist","should you buy","buy or sell","share price today","stock price today","multibagger","penny stock","top stocks to buy","stocks to watch","market forecast","best stocks to buy","stocks to buy","stocks to sell","investment idea")
    return not value or any(term in value for term in junk)

def _news_terms(text: str, terms) -> int:
    value = str(text or "").casefold()
    return sum(1 for term in terms if str(term).casefold() in value)

def _news_direction(text: str) -> int:
    pos = _news_terms(text, POSITIVE_NEWS_TERMS)
    neg = _news_terms(text, NEGATIVE_NEWS_TERMS)
    return 1 if pos > neg else -1 if neg > pos else 0

def _news_scope(text: str, company: bool = False) -> str:
    if company:
        return "COMPANY"
    if _news_terms(text, GLOBAL_NEWS_TERMS):
        return "MARKET / MACRO"
    if _news_terms(text, SECTOR_NEWS_TERMS):
        return "SECTOR / THEME"
    return "MARKET / DOMESTIC"

def analyze_news_catalyst(symbol: str, row, stock_news: list[dict], market_news: list[dict]) -> dict:
    symbol = str(symbol or "").strip().upper()
    direction = str(row.get("direction_label", "")).upper()
    price_change = pd.to_numeric(row.get("Price Chg %"), errors="coerce")
    if pd.isna(price_change):
        price_change = pd.to_numeric(row.get("Price_Chg_Pct"), errors="coerce")
    if pd.isna(price_change):
        price_change = pd.to_numeric(row.get("price_chg_pct"), errors="coerce")
    candidates = []
    for item in stock_news or []:
        text = _news_item_text(item)
        if text and not _news_is_junk(text):
            candidates.append((text, True, _news_item_time(item)))
    for item in market_news or []:
        text = _news_item_text(item)
        item_symbol = _news_item_symbol(item)
        if text and not _news_is_junk(text) and (item_symbol == symbol or _news_terms(text, GLOBAL_NEWS_TERMS + SECTOR_NEWS_TERMS)):
            candidates.append((text, False, _news_item_time(item)))
    scored = []
    for text, company, stamp in candidates:
        bias = _news_direction(text)
        major_hits = _news_terms(text, MAJOR_NEWS_TERMS)
        if bias == 0 and major_hits == 0:
            continue
        score = min(5, major_hits + (1 if bias else 0))
        scored.append({"text":text,"bias":bias,"score":score,"major":score >= 3,"scope":_news_scope(text,company),"time":stamp})
    scored.sort(key=lambda x:(x["major"],x["score"]), reverse=True)
    major = [x for x in scored if x["major"]]
    top = scored[:3]
    news_bias = sum(x["bias"] * max(1,x["score"]) for x in top)
    news_bias = 1 if news_bias > 0 else -1 if news_bias < 0 else 0
    market_direction = 1 if direction.startswith("BULL") else -1 if direction.startswith("BEAR") else 0
    if pd.notna(price_change) and price_change != 0:
        market_direction = 1 if float(price_change) > 0 else -1
    alignment = "ALIGNED" if news_bias and market_direction and news_bias == market_direction else "CONTRARY" if news_bias and market_direction else "NEUTRAL"
    impact = "POSITIVE" if news_bias > 0 else "NEGATIVE" if news_bias < 0 else "NEUTRAL"
    return {"major":bool(major),"impact":impact,"alignment":alignment,"items":top,"major_items":major[:2],"headline":major[0]["text"] if major else (top[0]["text"] if top else "")}

def catalyst_badge(analysis: dict) -> str:
    if not analysis.get("major"): return ""
    impact = analysis.get("impact")
    title = "Major positive news catalyst" if impact == "POSITIVE" else "Major negative news catalyst" if impact == "NEGATIVE" else "Major mixed/neutral news catalyst"
    return f'<span class="catalyst-star" title="{title}">★</span>'

def catalyst_panel_html(analysis: dict) -> str:
    if not analysis.get("major"):
        return '<div class="news-catalyst"><div class="catalyst-head"><div class="catalyst-title">NEWS CATALYST</div><div class="catalyst-bias-neutral">NO MATERIAL CATALYST DETECTED</div></div><div class="catalyst-body">No major available news item is strong enough to explain today&#39;s move.</div><div class="catalyst-note">Presentation layer only · no SDL re-scoring</div></div>'
    impact = analysis.get("impact","NEUTRAL")
    alignment = analysis.get("alignment","NEUTRAL")
    cls = "major-up" if impact == "POSITIVE" else "major-down" if impact == "NEGATIVE" else "mixed"
    bias_cls = "catalyst-bias-up" if impact == "POSITIVE" else "catalyst-bias-down" if impact == "NEGATIVE" else "catalyst-bias-neutral"
    major_items = analysis.get("major_items") or [{}]
    scope = major_items[0].get("scope","NEWS")
    return f'<div class="news-catalyst {cls}"><div class="catalyst-head"><div class="catalyst-title">★ MAJOR NEWS CATALYST · {safe_text(scope)}</div><div class="{bias_cls}">{safe_text(impact)} · {safe_text(alignment)}</div></div><div class="catalyst-body">{safe_text(analysis.get("headline",""))}</div><div class="catalyst-note">Presentation layer only · frozen SDL decision score unchanged</div></div>'

@st.cache_data(ttl=900, show_spinner=False)
def _quality_news_rss(query: str) -> list[dict]:
    q = str(query or "").strip()
    if not q: return []
    try:
        url = "https://news.google.com/rss/search?" + urlencode({"q":q,"hl":"en-IN","gl":"IN","ceid":"IN:en"})
        req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urlopen(req, timeout=3) as response:
            root = ET.fromstring(response.read())
        allowed = ("mint","livemint","moneycontrol","cnbc tv18","cnbctv18","reuters","economic times","economictimes","business standard","financial express","businessline","the hindu businessline")
        out=[]; seen=set()
        for item in root.findall("./channel/item")[:20]:
            title=(item.findtext("title") or "").strip()
            pub=(item.findtext("pubDate") or "").strip()
            source=(item.findtext("source") or "").strip()
            if not title or _news_is_junk(title): continue
            if source and not any(name in source.casefold() for name in allowed): continue
            key=title.casefold()
            if key in seen: continue
            seen.add(key)
            out.append({"text":title,"title":title,"time":pub,"timestamp":pub,"published":pub,"source":source or "Google News","scope":"EXTERNAL"})
        return out
    except Exception:
        return []



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

        futures_status = str(row.get("futures_oi_status", "")).strip().upper()
        futures_delayed = bool(row.get("futures_oi_delayed", False)) or futures_status == "DELAYED"
        futures_label_suffix = " · D" if futures_delayed else ""
        cards = [
            (f"FUTURES OI CHANGE{futures_label_suffix}", fut, fut_pct),
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
            if label.startswith("FUTURES OI CHANGE") and futures_delayed:
                note = "Delayed · last successfully processed Futures evidence"

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

        show_timeline = st.checkbox(
            "Show on-demand price timeline",
            value=False,
            key=f"{page_key}_timeline",
        )
        if show_timeline:
            timeline_day = current_ts.date().isoformat() if pd.notna(current_ts) else ""
            timeline = _symbol_price_timeline(
                timeline_day,
                selected,
                current_ts.isoformat() if pd.notna(current_ts) else None,
                _cache_file_signature(),
            )
            if not timeline.empty:
                _render_intraday_evidence_chart(timeline, alert_timestamp=None)
            else:
                st.caption("No cached point-in-time price history is available for this symbol.")

        # External news is intentionally cold-path: it is fetched only after
        # explicit user action so normal LIVE refresh latency is unchanged.
        load_external = st.checkbox(
            "Load external stock / sector / macro news",
            value=False,
            key=f"{page_key}_external_news",
        )
        external_news = {"stock": [], "sector": [], "macro": []}
        if load_external:
            external_news = live_external_news(selected, row)

        quality_stock = _quality_news_rss(f'"{selected}" India stock company')
        quality_sector = _quality_news_rss(f'"{selected}" sector India regulatory results order')
        stock_news = [x for x in quality_stock if not _news_is_junk(x.get("text", ""))]
        market_news = [x for x in _quality_news_rss('site:livemint.com OR site:moneycontrol.com OR site:cnbctv18.com India markets sector regulatory news') if not _news_is_junk(x.get("text", ""))]
        combined_stock_news = list(external_news.get("stock", [])) + stock_news
        combined_market_news = list(external_news.get("sector", [])) + list(external_news.get("macro", [])) + market_news
        news_analysis = analyze_news_catalyst(selected, row, combined_stock_news, combined_market_news)
        st.markdown(catalyst_panel_html(news_analysis), unsafe_allow_html=True)

        left, right = st.columns(2)

        with left:
            with st.expander(
                f"STOCK-SPECIFIC NEWS · {selected}",
                expanded=False,
            ):
                if combined_stock_news:
                    major_texts = {x.get("text") for x in news_analysis.get("major_items", [])}
                    for item in combined_stock_news[:8]:
                        is_major = item.get("text") in major_texts
                        cls = "news-item major-news" if is_major else "news-item"
                        star = "★ " if is_major else ""
                        st.markdown(
                            f'<div class="{cls}">'
                            f'{star}{safe_text(_news_item_text(item))}'
                            f'<span class="news-time">'
                            f'{safe_text(_news_item_time(item))} · '
                            f'{safe_text(impact_hint(_news_item_text(item)))}'
                            f'</span></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        '<div class="news-empty">'
                        'No stock-specific news returned. External news is loaded on demand.'
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
                            f'{star}<b>{safe_text(item.get("symbol") or "NSE")}</b> · '
                            f'{safe_text(item.get("text", ""))}'
                            f'<span class="news-time">'
                            f'{safe_text(item.get("time", "NSE"))} · '
                            f'{safe_text(item.get("impact") or _news_item_impact(item))}'
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
    snapshot_ts: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Load the current persisted point-in-time Replay entry.

    Deliberately not Streamlit-cache this reader: the cache builder updates
    the persistent day-cache in place, so a 300-second UI cache can otherwise
    show stale Futures evidence (for example 0/34 after the builder has
    already refreshed the same point). The expensive source/Futures work is
    still protected by the timestamp-driven resolver cache.
    """
    ts = pd.to_datetime(snapshot_ts, errors="coerce")
    if pd.isna(ts):
        ts = observation_ts(path)
    day = pd.Timestamp(ts).date().isoformat() if pd.notna(ts) else ""
    key = pd.Timestamp(ts).isoformat() if pd.notna(ts) else ""

    cache = _load_day_point_cache()
    day_cache = cache.get(day, {}) if isinstance(cache, dict) else {}
    entries = (
        day_cache.get("snapshots", {})
        if isinstance(day_cache.get("snapshots", {}), dict)
        else {}
    )
    entry = entries.get(key)

    if isinstance(entry, dict) and isinstance(entry.get("pred"), pd.DataFrame):
        pred = entry["pred"].copy()
        entry_status = str(entry.get("evidence_status", "pending")).lower()

        # Do not permanently freeze a replay point with missing Futures
        # evidence. Re-check the point-in-time IVR/IVP companion whenever the
        # cached point is pending or has no Futures values.
        if entry_status != "complete" or not _futures_mapping_complete(pred):
            future_ev = _read_ivrp_for_timestamp(day, pd.Timestamp(ts))
            if _futures_evidence_available(future_ev):
                try:
                    raw, loaded_ts = load_primary_snapshot(path, ts)
                    loaded_ts = pd.to_datetime(loaded_ts, errors="coerce")
                    if pd.notna(loaded_ts) and raw is not None and not raw.empty:
                        raw = derive_straddle_values(raw)
                        option_ev = _day_option_evidence(raw)
                        pred, evidence = _merge_snapshot_evidence(
                            pred, option_ev, future_ev
                        )
                        pred = _apply_futures_evidence_status(pred, future_ev, source_available=True)
                        mapped_rows, total_rows = _futures_mapping_stats(pred)
                        refreshed_status = (
                            "complete"
                            if total_rows > 0 and mapped_rows == total_rows
                            else "partial"
                        )
                        entries[key] = {
                            **entry,
                            "timestamp": pd.Timestamp(loaded_ts).isoformat(),
                            "pred": pred.copy(),
                            "evidence": evidence.copy(),
                            "snapshot_status": "VALID",
                            "futures_status": "MAPPED" if _futures_evidence_available(future_ev) else "D",
                            "evidence_status": refreshed_status,
                        }
                        day_cache["snapshots"] = dict(
                            sorted(entries.items(), key=lambda kv: kv[0])
                        )
                        cache[day] = day_cache
                        _save_day_point_cache(cache)
                except Exception:
                    pass

        replay_return_ts = pd.Timestamp(entry.get("timestamp", ts))
        pred = _attach_first_alert_provenance(
            pred,
            day,
            replay_return_ts,
        )
        return pred, replay_return_ts

    # Explicit cache build is the normal path. This fallback is intentionally
    # one-point only so selecting an uncached point can never silently rebuild
    # an entire historical day.
    df, loaded_ts = load_primary_snapshot(path, ts)
    loaded_ts = pd.to_datetime(loaded_ts, errors="coerce")
    if pd.isna(loaded_ts) or df is None or df.empty:
        return pd.DataFrame(), pd.NaT

    state = load_state(STATE_JSON)
    base = (
        state.get("daily_opening_straddles", {}).get(day)
        if isinstance(state, dict)
        else None
    )
    if not base:
        files = snapshot_files(day)
        if files:
            first_df, _ = load_primary_snapshot(files[0], observation_ts(files[0]))
            base = frozen_base_from_df(derive_straddle_values(first_df))

    raw = derive_straddle_values(df)
    pred = candidates(
                raw,
                base or {},
                snapshot_ts=loaded_ts,
                snapshot_path=None,
                first_alert_signature=_first_alert_source_signature(
                    pd.Timestamp(loaded_ts).date().isoformat()
                ),
            )
    option_ev = _day_option_evidence(raw)
    future_ev = _read_ivrp_for_timestamp(day, loaded_ts)
    pred, _ = _merge_snapshot_evidence(pred, option_ev, future_ev)
    pred = _attach_first_alert_provenance(pred, day, loaded_ts)
    return pred, loaded_ts

def _load_day_cache_build_state() -> dict:
    try:
        if not DAY_CACHE_BUILD_STATE_FILE.exists():
            return {}
        value = json.loads(DAY_CACHE_BUILD_STATE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save_day_cache_build_state(**values) -> dict:
    with _DAY_CACHE_BUILD_LOCK:
        current = _load_day_cache_build_state()
        current.update(values)
        current["updated_at"] = datetime.now().isoformat(timespec="seconds")
        tmp = DAY_CACHE_BUILD_STATE_FILE.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(DAY_CACHE_BUILD_STATE_FILE)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        return current


def _cache_build_is_running() -> bool:
    state = _load_day_cache_build_state()
    if str(state.get("status", "")).upper() != "RUNNING":
        return False
    try:
        heartbeat = pd.Timestamp(state.get("heartbeat_at"))
        if pd.isna(heartbeat):
            return False
        return (pd.Timestamp.now() - heartbeat).total_seconds() < 300.0
    except Exception:
        return False


def _cache_build_progress_state(day_index, total_days, build_day, done, total,
                                complete, pending, skipped, filename):
    _save_day_cache_build_state(
        status="RUNNING",
        mode="BULK" if total_days and total_days > 1 else "DAY",
        pid=os.getpid(),
        day_index=int(day_index),
        total_days=int(total_days),
        current_day=str(build_day),
        current_snapshot=int(done),
        total_snapshots=int(total),
        futures_complete=int(complete),
        futures_pending=int(pending),
        skipped=int(skipped),
        current_file=str(filename or ""),
        heartbeat_at=datetime.now().isoformat(timespec="seconds"),
    )


def _background_build_days(days: list[str], mode: str = "BULK") -> None:
    """Build historical cache outside the Streamlit script request."""
    total_days = len(days)
    now = datetime.now().isoformat(timespec="seconds")
    _save_day_cache_build_state(
        status="RUNNING", mode=str(mode).upper(), pid=os.getpid(),
        day_index=0, total_days=total_days, current_day="",
        current_snapshot=0, total_snapshots=0, futures_complete=0,
        futures_pending=0, skipped=0, current_file="", started_at=now,
        heartbeat_at=now,
    )
    try:
        for day_index, day in enumerate(days, start=1):
            def _progress(done, total, complete, pending, skipped, filename,
                          di=day_index, td=total_days, d=day):
                _cache_build_progress_state(
                    di, td, d, done, total, complete, pending, skipped, filename
                )

            _save_day_cache_build_state(
                current_day=str(day), day_index=day_index, total_days=total_days,
                current_snapshot=0, total_snapshots=len(snapshot_files(day)),
                current_file="", heartbeat_at=datetime.now().isoformat(timespec="seconds"),
            )
            build_day_point_in_time_cache(day, progress_callback=_progress)

        finished = datetime.now().isoformat(timespec="seconds")
        _save_day_cache_build_state(
            status="FINISHED", day_index=total_days, total_days=total_days,
            current_day=str(days[-1]) if days else "", current_file="",
            heartbeat_at=finished, finished_at=finished,
        )
    except Exception as exc:
        finished = datetime.now().isoformat(timespec="seconds")
        _save_day_cache_build_state(
            status="ERROR", error=f"{type(exc).__name__}: {exc}",
            heartbeat_at=finished, finished_at=finished,
        )


def _start_background_cache_build(days: list[str], mode: str = "BULK") -> bool:
    days = [str(d)[:10] for d in (days or []) if str(d).strip()]
    if not days or _cache_build_is_running():
        return False

    # Publish RUNNING before starting the worker so the next Streamlit rerun
    # can immediately render the persistent build monitor.
    started = datetime.now().isoformat(timespec="seconds")
    _save_day_cache_build_state(
        status="RUNNING",
        mode=str(mode).upper(),
        pid=os.getpid(),
        day_index=0,
        total_days=len(days),
        current_day="",
        current_snapshot=0,
        total_snapshots=0,
        futures_complete=0,
        futures_pending=0,
        skipped=0,
        current_file="",
        started_at=started,
        heartbeat_at=started,
    )
    worker = threading.Thread(
        target=_background_build_days,
        args=(days, str(mode).upper()),
        name="SDL-DayCacheBuilder",
        daemon=True,
    )
    worker.start()
    return True


def _render_cache_build_state() -> None:
    """Render the single authoritative cache-build status in compact form."""
    state = _load_day_cache_build_state()
    status = str(state.get("status", "")).upper()
    if status not in {"RUNNING", "FINISHED", "ERROR"}:
        return
    mode = str(state.get("mode", "BULK")).upper()
    di = int(state.get("day_index", 0) or 0); td = int(state.get("total_days", 0) or 0)
    done = int(state.get("current_snapshot", 0) or 0); total = int(state.get("total_snapshots", 0) or 0)
    complete = int(state.get("futures_complete", 0) or 0); pending = int(state.get("futures_pending", 0) or 0)
    skipped = int(state.get("skipped", 0) or 0); day = str(state.get("current_day", ""))
    filename = str(state.get("current_file", "")); heartbeat_at = state.get("heartbeat_at")
    try: heartbeat_age=max(0,int((pd.Timestamp.now()-pd.Timestamp(heartbeat_at)).total_seconds()))
    except Exception: heartbeat_age=-1
    if status == "RUNNING":
        pct=int(round(((max(0,di-1)+(done/total if total else 0))/td)*100)) if td else 0; pct=max(0,min(100,pct))
        state_label="🟢 RUNNING" if 0<=heartbeat_age<300 else "🟠 HEARTBEAT STALE"
        st.markdown('<div class="cache-build-monitor"><div class="cache-build-monitor-head">'
                    f'<div>⚙ CACHE BUILD <span class="cache-build-live">{state_label}</span></div>'
                    f'<div class="cache-build-mode">{mode} · DAY {di}/{td}</div></div>'
                    f'<div class="cache-build-title">{safe_text(day or "starting…")} · {done}/{total} snapshots · {pct}% · Futures {complete} mapped / {pending} pending · {skipped} skipped</div></div>', unsafe_allow_html=True)
        st.progress(pct/100.0,text=f"Build {pct}%")
        st.markdown(f'<div class="cache-build-compact-note">Current: {safe_text(filename or "preparing…")} · Heartbeat: {heartbeat_age}s · Refresh-safe background worker.</div>',unsafe_allow_html=True)
    elif status == "FINISHED":
        # FINISHED describes the worker job, not necessarily 100% source/cache
        # coverage. Invalidate the short UI summary cache before reading the
        # final day so the monitor and Replay panel cannot display different
        # cached coverage immediately after a build completes.
        try:
            _day_cache_summary.clear()
        except Exception:
            pass
        final_summary = _day_cache_summary(day) if day else {}
        final_source = int(final_summary.get("source_count", 0) or 0)
        final_cached = int(final_summary.get("cached_count", 0) or 0)
        final_missing = int(final_summary.get("missing_count", 0) or 0)
        if final_source > 0 and final_cached < final_source:
            st.markdown(
                f'<div class="cache-build-monitor" style="border-color:#8b6114">'
                f'<div class="cache-build-monitor-head"><div>⚙ CACHE BUILD <span class="cache-build-live" style="color:#ffc650">🟠 FINISHED · PARTIAL CACHE</span></div>'
                f'<div class="cache-build-mode">{td} DAY(S)</div></div>'
                f'<div class="cache-build-title">Build job finished · {safe_text(day or "—")} · {final_cached}/{final_source} snapshots cached · {final_missing} not built</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="cache-build-monitor"><div class="cache-build-monitor-head"><div>⚙ CACHE BUILD <span class="cache-build-live">🟢 FINISHED · CACHE COMPLETE</span></div><div class="cache-build-mode">{td} DAY(S)</div></div><div class="cache-build-title">Build job finished · {safe_text(day or "—")} · all available source snapshots cached</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(f'<div class="cache-build-monitor" style="border-color:#8c3540"><div class="cache-build-monitor-head"><div>⚙ CACHE BUILD <span style="color:#ff7b84">🔴 STOPPED</span></div><div class="cache-build-mode">DAY {di}/{td}</div></div><div class="cache-build-title">{safe_text(state.get("error","unknown error"))} · Snapshot {done}/{total}</div></div>',unsafe_allow_html=True)


if hasattr(st, "fragment"):
    @st.fragment
    def _render_replay_filter_queue(pred: pd.DataFrame, ts) -> None:
        """Isolate Replay data-filter interactions from the calendar and rest of the dashboard."""
        if pred is None or pred.empty:
            st.info("No eligible SDL decisions exist in this replay snapshot.")
            return
        st.markdown(
            '<div class="filter-panel"><div class="filter-caption">'
            'REPLAY FILTERS · independent from live feed</div>',
            unsafe_allow_html=True,
        )
        filtered = render_filters(pred, "replay")
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption(f"{len(filtered)} matching replay decision(s).")
        st.markdown(
            '<div class="workspace-panel"><div class="panel-head">'
            '<div class="panel-title">REPLAY QUEUE</div>'
            f'<div class="panel-meta">Snapshot time is immutable: {safe_text(fmt_time(ts, full=True))}'
            '</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(queue_html(filtered, replay_mode=True), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
else:
    def _render_replay_filter_queue(pred: pd.DataFrame, ts) -> None:
        if pred is None or pred.empty:
            st.info("No eligible SDL decisions exist in this replay snapshot.")
            return
        st.markdown(
            '<div class="filter-panel"><div class="filter-caption">'
            'REPLAY FILTERS · independent from live feed</div>',
            unsafe_allow_html=True,
        )
        filtered = render_filters(pred, "replay")
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption(f"{len(filtered)} matching replay decision(s).")
        st.markdown(
            '<div class="workspace-panel"><div class="panel-head">'
            '<div class="panel-title">REPLAY QUEUE</div>'
            f'<div class="panel-meta">Snapshot time is immutable: {safe_text(fmt_time(ts, full=True))}'
            '</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(queue_html(filtered, replay_mode=True), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def replay_view() -> None:
    with st.expander(
        "INTRADAY REPLAY · HISTORICAL SNAPSHOT · LIVE STATE REMAINS UNCHANGED",
        expanded=False,
    ):
        st.markdown(
            '<div class="panel-meta">'
            'Point-in-time replay only · LIVE state is never modified by Replay.'
            '</div>',
            unsafe_allow_html=True,
        )

        date_values = list(_replay_date_index())
        if not date_values:
            st.info("No Daywise snapshots are available for replay.")
            return
        if not date_values:
            st.info("No snapshots have a valid observation timestamp for replay.")
            return

        months = sorted({d[:7] for d in date_values}, reverse=True)
        selected_month = st.session_state.get("replay_calendar_month", months[0])
        if selected_month not in months:
            selected_month = months[0]
        month_date_values = [d for d in date_values if d[:7] == selected_month]
        # Keep the selected day synchronized with the visible month.  This is
        # UI state only; it never changes the point-in-time cache or LIVE state.
        day = st.session_state.get("replay_day")
        if day not in month_date_values:
            day = month_date_values[0] if month_date_values else date_values[0]
            st.session_state["replay_day"] = day
            st.session_state["replay_snapshot_index"] = 0

        if "replay_calendar_open" not in st.session_state:
            st.session_state["replay_calendar_open"] = True

        left_col, right_col = st.columns([0.24, 0.76], gap="small")

        with left_col:
            if not bool(st.session_state.get("replay_calendar_open", True)):
                if st.button(
                    "📅 Change Day",
                    key="replay_change_day",
                    use_container_width=True,
                ):
                    st.session_state["replay_calendar_open"] = True
                    st.rerun()

            with st.container(key="replay_calendar_panel"):
                with st.expander(
                    "REPLAY CALENDAR",
                    expanded=bool(st.session_state.get("replay_calendar_open", True)),
                ):
                    selected_month = st.selectbox(
                        "Replay month",
                        months,
                        format_func=lambda x: pd.Timestamp(f"{x}-01").strftime("%B %Y"),
                        key="replay_calendar_month",
                    )
                    month_date_values = [d for d in date_values if d[:7] == selected_month]
                    st.markdown(
                        '<div class="replay-calendar-legend">'
                        '<b>DAY STATUS</b> · '
                        '🟢 complete · 🟡 cache complete / Futures pending · '
                        '🟠 partial build · 🔴 not built · ⚪ no source'
                        '</div>',
                        unsafe_allow_html=True,
                    )

                    cal = calendar.monthcalendar(
                        int(selected_month[:4]),
                        int(selected_month[5:7]),
                    )
                    month_day_files = _calendar_month_day_files(selected_month)

                    with st.container(key="replay_calendar_wrap"):
                        headers = st.columns(7, gap="small")
                        for col, label in zip(
                            headers, ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
                        ):
                            with col:
                                st.markdown(
                                    f'<div class="replay-calendar-head">{label}</div>',
                                    unsafe_allow_html=True,
                                )

                        for week in cal:
                            cols = st.columns(7, gap="small")
                            for col, number in zip(cols, week):
                                with col:
                                    if not number:
                                        st.markdown(
                                            '<div class="replay-calendar-empty"></div>',
                                            unsafe_allow_html=True,
                                        )
                                        continue

                                    day_value = f"{selected_month}-{number:02d}"
                                    if day_value not in month_date_values:
                                        st.markdown(
                                            f'<div class="replay-calendar-day replay-calendar-no-source">{number}</div>',
                                            unsafe_allow_html=True,
                                        )
                                        continue

                                    day_files = month_day_files.get(day_value, [])
                                    summary = _day_cache_summary(day_value, day_files)
                                    marker = _day_cache_marker(summary)
                                    if st.button(
                                        f"{marker} {number}",
                                        key=f"replay_cal_{day_value}",
                                        use_container_width=True,
                                    ):
                                        st.session_state["replay_day"] = day_value
                                        st.session_state["replay_snapshot_index"] = 0
                                        st.session_state["replay_calendar_open"] = False
                                        st.rerun()

                                    # Calendar is intentionally status-only.
                                    # Detailed source/cache/Futures counts belong in the
                                    # selected-day panel on the right, preventing cell wrapping
                                    # and the previous asymmetric calendar layout.

        # ------------------------------------------------------------------
        # Selected-day workspace: deliberately kept beside the calendar so
        # the calendar does not consume the full dashboard width.
        # ------------------------------------------------------------------
        day_files = snapshot_files(day)
        if not day_files:
            with right_col:
                st.info("No snapshots are available for the selected trading day.")
            return

        summary = _day_cache_summary(day, day_files)
        marker = _day_cache_marker(summary)
        source_n = int(summary.get("source_count", 0))
        cached_n = int(summary.get("cached_count", 0))
        complete_n = int(summary.get("futures_complete_count", summary.get("complete_count", 0)))
        unavailable_n = int(summary.get("futures_unavailable_count", 0))
        pending_n = int(summary.get("futures_pending_count", summary.get("pending_count", 0)))
        missing_n = int(summary.get("missing_count", 0))

        if marker == "🟢":
            status_class = "ready"
            status_text = (
                f"READY · {cached_n}/{source_n} snapshots cached · "
                f"Futures {complete_n} mapped · {unavailable_n} D · {pending_n} pending"
            )
        elif marker == "🟡":
            status_class = "pending"
            status_text = (
                f"SNAPSHOTS CACHED · {cached_n}/{source_n} · "
                f"Futures {complete_n} mapped · {unavailable_n} D · {pending_n} pending"
            )
        elif marker == "🟠":
            status_class = "partial"
            status_text = (
                f"PARTIAL BUILD · {cached_n}/{source_n} snapshots cached · "
                f"Futures {complete_n} mapped · {unavailable_n} D · {pending_n} pending · {missing_n} not built"
            )
        else:
            status_class = "notbuilt"
            status_text = (
                f"NOT BUILT · {source_n} source snapshots · "
                f"{cached_n} cached · {missing_n} not built"
            )

        with right_col:
            with st.container(key="replay_day_info_panel"):
                st.markdown(
                    f'<div class="replay-day-heading">'
                    f'<span>REPLAY DAY</span>'
                    f'<b>{pd.Timestamp(day).strftime("%A · %d %b %Y")}</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="replay-cache-status {status_class} replay-cache-status-prominent">'
                    f'<b>{status_text}</b></div>',
                    unsafe_allow_html=True,
                )

                # Resume control: retry only missing/unresolved work.
                # Completed MAPPED/D snapshots remain untouched; newly arrived
                # Daywise files are rediscovered when the worker starts.
                cache_running = _cache_build_is_running()
                bulk_days = _available_replay_days()
                bday, bbulk = st.columns([1, 1], gap="small")
                with bday:
                    if missing_n > 0 and pending_n > 0:
                        build_label = f"BUILD MISSING ({missing_n}) + PENDING ({pending_n})"
                    elif missing_n > 0:
                        build_label = f"BUILD MISSING ({missing_n})"
                    elif pending_n > 0:
                        build_label = f"BUILD PENDING ({pending_n})"
                    else:
                        build_label = "DAY CACHE COMPLETE"
                    if missing_n > 0 or pending_n > 0:
                        if st.button(build_label, key=f"build_replay_cache_{day}", type="primary", use_container_width=True, disabled=cache_running):
                            _start_background_cache_build([day], mode="DAY"); st.rerun()
                    else:
                        st.button(build_label, key=f"build_replay_cache_done_{day}", use_container_width=True, disabled=True)
                with bbulk:
                    if st.button(f"BUILD ALL ({len(bulk_days)})", key="build_all_replay_cache", type="secondary", use_container_width=True, disabled=(not bulk_days) or cache_running):
                        _start_background_cache_build(bulk_days, mode="BULK"); st.rerun()
                st.markdown('<div class="replay-cache-build-note" style="margin:2px 0 4px">Point-in-time Daywise + IVR/IVP · Futures optional · LIVE state unchanged.</div>', unsafe_allow_html=True)

                if cached_n == source_n and source_n > 0:
                    st.markdown(
                        '<div class="replay-cache-ready-note">'
                        'Selected-day base snapshot cache is complete. Futures is an optional evidence layer; D rows remain valid.'
                        '</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    '<div class="replay-selected-snapshot">'
                    '<div class="replay-selected-snapshot-label">POINT-IN-TIME SNAPSHOT</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                selected_idx = st.selectbox(
                    "Snapshot time",
                    range(len(day_files)),
                    format_func=lambda i: fmt_time(observation_ts(day_files[i])),
                    key="replay_snapshot_index",
                    label_visibility="collapsed",
                )
                if selected_idx is None or pd.isna(selected_idx):
                    st.info("Select a snapshot time to open Replay.")
                    return

                path = day_files[int(selected_idx)]
                pred, ts = replay_snapshot_frame(path, observation_ts(path))

                # The selector is intentionally time-only. The source filename
                # remains internal and is never presented in the Replay UI.
                replay_ts_text = fmt_time(ts, full=True)
                st.markdown(
                    f'<div class="replay-selected-time">SELECTED SNAPSHOT · <b>{safe_text(replay_ts_text)}</b></div>',
                    unsafe_allow_html=True,
                )

                _fut_cols = [
                    c for c in ("futures_oi_chg", "futures_oi_chg_pct")
                    if c in pred.columns
                ]
                _fut_mapped = 0
                if _fut_cols and "symbol" in pred.columns:
                    _fut_mapped = int(
                        pred[_fut_cols]
                        .apply(pd.to_numeric, errors="coerce")
                        .notna()
                        .any(axis=1)
                        .sum()
                    )
                if _fut_cols and "symbol" in pred.columns:
                    _fut_missing = max(0, len(pred) - _fut_mapped)
                    if _fut_missing:
                        st.caption(
                            f"Futures evidence: MAPPED for {_fut_mapped}/{len(pred)} replay rows; "
                            f"{_fut_missing} row(s) remain UNMAPPED for this point-in-time IVR/IVP source."
                        )
                    else:
                        st.caption(
                            f"Futures evidence: MAPPED for {_fut_mapped}/{len(pred)} replay rows "
                            f"from the point-in-time IVR/IVP resolver."
                        )
                else:
                    st.caption(
                        "Futures evidence: PENDING — no point-in-time IVR/IVP values mapped "
                        "for this replay snapshot."
                    )

                if _fut_cols and "symbol" in pred.columns:
                    _fut_numeric = pred[_fut_cols].apply(pd.to_numeric, errors="coerce")
                    _unmapped_symbols = (
                        pred.loc[~_fut_numeric.notna().any(axis=1), "symbol"]
                        .astype(str)
                        .str.strip()
                        .tolist()
                    )
                    if _unmapped_symbols:
                        st.caption(
                            "Data not available in the point-in-time IVR/IVP source: "
                            + ", ".join(_unmapped_symbols)
                            + " · shown as yellow D in Replay Queue."
                        )

        _render_replay_filter_queue(pred, ts)


# ============================================================================
# SESSION / MARKET-DATE RESOLUTION
# ============================================================================
#
# The pipeline's process_latest_snapshot_for_today() is intentionally not used
# as the authoritative session resolver here.  Its "today" view can lag behind
# the historical Daywise repository when the latest completed source session is
# a prior trading day.  The Decision Centre therefore resolves the session
# from the same read-only Daywise source repository used by Replay.
#
# Rules:
#   1. A current trading day with Daywise source -> use today's latest source.
#   2. A current trading day without source -> use the latest prior source day.
#   3. A weekend / configured NSE F&O holiday -> use the latest prior source day.
#   4. Never allow persisted LIVE state to select an older session than the
#      authoritative source repository.
# ============================================================================

# NSE F&O regular-session holidays for calendar year 2026.
# Source: NSE circular NSE/FAOP/71777 dated 12-Dec-2025.
NSE_FO_HOLIDAYS_2026 = frozenset(
    {
        "2026-01-26",
        "2026-03-03",
        "2026-03-26",
        "2026-03-31",
        "2026-04-03",
        "2026-04-14",
        "2026-05-01",
        "2026-05-28",
        "2026-06-26",
        "2026-09-14",
        "2026-10-02",
        "2026-10-20",
        "2026-11-10",
        "2026-11-24",
        "2026-12-25",
    }
)


def _nse_is_trading_day(day) -> bool:
    """Return whether the NSE F&O regular session is scheduled for *day*."""
    ts = pd.Timestamp(day)
    if pd.isna(ts):
        return False
    day_text = ts.strftime("%Y-%m-%d")
    if ts.weekday() >= 5:
        return False
    if day_text in NSE_FO_HOLIDAYS_2026:
        return False
    return True


def _nse_market_state(now=None) -> tuple[str, bool]:
    """Return (display_state, scheduled_trading_day) for the current clock."""
    ts = pd.Timestamp.now(tz=IST) if now is None else pd.Timestamp(now)
    if ts.tzinfo is None:
        ts = ts.tz_localize(IST)
    else:
        ts = ts.tz_convert(IST)

    day = ts.date()
    if not _nse_is_trading_day(day):
        return "NON-TRADING DAY", False

    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()

    if ts.time() < market_open:
        return "PRE-OPEN", True
    if ts.time() <= market_close:
        return "OPEN", True
    return "CLOSED", True


def _latest_session_sources(reference_day=None, lookback_days: int = 45):
    """Resolve the latest authoritative Daywise session from the source tree.

    Returns:
        (session_day, source_files, current_day_has_source)

    ``current_day_has_source`` distinguishes a live trading day waiting for its
    first source from a non-trading day / completed prior session.
    """
    if reference_day is None:
        today = pd.Timestamp.now(tz=IST).date()
    else:
        today = pd.Timestamp(reference_day).date()

    today_text = today.isoformat()
    today_files = snapshot_files(today_text)
    if _nse_is_trading_day(today) and today_files:
        return today_text, today_files, True

    # On a non-trading day, or before the first source on a trading day, walk
    # backwards through the read-only source repository.  45 calendar days
    # covers normal weekends/holidays without depending on a stale persisted
    # dashboard session.
    for offset in range(1, max(1, int(lookback_days)) + 1):
        candidate_day = (today - pd.Timedelta(days=offset)).isoformat()
        if not _nse_is_trading_day(candidate_day):
            continue
        files = snapshot_files(candidate_day)
        if files:
            return candidate_day, files, False

    # Fallback for repositories containing an exceptional source day not
    # represented by the static holiday table.  We still prefer the newest
    # actual Daywise source rather than persisted LIVE state.
    discovered = []
    for offset in range(1, max(1, int(lookback_days)) + 1):
        candidate_day = (today - pd.Timedelta(days=offset)).isoformat()
        files = snapshot_files(candidate_day)
        if files:
            discovered.append((candidate_day, files))
    if discovered:
        return discovered[0][0], discovered[0][1], False

    return None, [], False


def _build_live_prediction_from_source(path: Path):
    """Build one LIVE point from the authoritative Daywise source file."""
    if path is None:
        return None, pd.DataFrame(), pd.NaT, "No source snapshot."

    ts = observation_ts(path)
    if pd.isna(ts):
        return None, pd.DataFrame(), pd.NaT, "Source snapshot has no valid observation timestamp."

    try:
        raw_df, _ = load_primary_snapshot(path, ts)
    except Exception as exc:
        return path, pd.DataFrame(), ts, f"Unable to read source snapshot: {type(exc).__name__}: {exc}"

    if raw_df is None or raw_df.empty:
        return path, pd.DataFrame(), ts, "Source snapshot contains no rows."

    state = load_state(STATE_JSON)
    day = pd.Timestamp(ts).date().isoformat()

    base = (
        state.get("daily_opening_straddles", {}).get(day)
        if isinstance(state, dict)
        else None
    )
    if not base:
        base = frozen_base_from_df(derive_straddle_values(raw_df))

    raw = derive_straddle_values(raw_df)
    pred = candidates(
        raw,
        base or {},
        snapshot_ts=ts,
        snapshot_path=None,
        first_alert_signature=_first_alert_source_signature(
            pd.Timestamp(ts).date().isoformat()
        ),
    )

    option_ev = _day_option_evidence(raw)
    futures = _read_ivrp_for_timestamp(day, ts)
    pred, evidence = _merge_snapshot_evidence(pred, option_ev, futures)
    pred = _apply_futures_evidence_status(
        pred, futures, source_available=_futures_evidence_available(futures), source_pending=not _futures_evidence_available(futures)
    )
    mapped_rows, total_rows = _futures_mapping_stats(pred)
    status = (
        "complete"
        if total_rows > 0 and mapped_rows == total_rows
        else "partial"
    )
    futures_status = "MAPPED" if _futures_evidence_available(futures) else "P"

    # Persist this exact source point in the chronological day cache.
    cache = _load_day_point_cache()
    day_cache = (
        cache.get(day, {})
        if isinstance(cache.get(day, {}), dict)
        else {}
    )
    entries = (
        day_cache.get("snapshots", {})
        if isinstance(day_cache.get("snapshots", {}), dict)
        else {}
    )
    entries[pd.Timestamp(ts).isoformat()] = {
        "timestamp": pd.Timestamp(ts).isoformat(),
        "source_path": str(path),
        "pred": pred.copy(),
        "evidence": evidence.copy(),
        "snapshot_status": "VALID",
        "futures_status": futures_status,
        "evidence_status": status,
    }
    ordered = dict(sorted(entries.items(), key=lambda kv: kv[0]))
    cache[day] = {
        "cache_schema": DAY_POINT_CACHE_SCHEMA,
        "trading_date": day,
        "latest_timestamp": next(reversed(ordered), None),
        "snapshots": ordered,
        "source_count": len(snapshot_files(day)),
    }
    _save_day_point_cache(cache)
    pred = _attach_first_alert_provenance(pred, day, ts)
    _save_persisted_live_snapshot(path, ts, pred, f"Source session: {day}")
    pred = _apply_live_futures_delay_policy(
        pred,
        ts,
        futures_fresh=bool(status == "complete"),
    )
    return path, pred, ts, f"Source session: {day}"



# ============================================================================
# LIVE DATA
# ============================================================================

def _load_live_futures_state() -> dict:
    try:
        if not LIVE_FUTURES_STATE_FILE.exists():
            return {}
        with LIVE_FUTURES_STATE_FILE.open("rb") as handle:
            value = pickle.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save_live_futures_state(state: dict) -> None:
    tmp = LIVE_FUTURES_STATE_FILE.with_suffix(".tmp")
    try:
        with tmp.open("wb") as handle:
            pickle.dump(state, handle, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(LIVE_FUTURES_STATE_FILE)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _live_futures_present(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    return any(
        c in df.columns and pd.to_numeric(df[c], errors="coerce").notna().any()
        for c in ("futures_oi_chg", "futures_oi_chg_pct")
    )


def _hydrate_live_futures_state_from_source(day: str, primary_ts: pd.Timestamp) -> dict:
    """Recover the latest valid LIVE Futures evidence without changing Replay.

    This is used only when LIVE has no durable Futures carry-forward state. It
    searches the Futures source independently of the Daywise primary snapshot,
    chooses the latest populated Futures workbook not later than the retained
    LIVE primary timestamp, and persists that evidence as the delayed LIVE
    Futures state. It never creates an SDL snapshot and never modifies Replay.
    """
    if not day or primary_ts is None or pd.isna(primary_ts):
        return {}
    try:
        candidates = _day_ivrp_candidates(str(day)[:10])
    except Exception:
        candidates = []
    for path in sorted(
        candidates,
        key=lambda item: (observation_ts(item), str(item).lower()),
        reverse=True,
    ):
        source_ts = observation_ts(path)
        if pd.isna(source_ts) or pd.Timestamp(source_ts) > pd.Timestamp(primary_ts):
            continue
        try:
            evidence = _read_ivrp_for_timestamp(
                str(day)[:10], pd.Timestamp(source_ts), force_refresh=True
            )
        except Exception:
            continue
        if not _live_futures_present(evidence):
            continue
        values = evidence[[c for c in ("symbol", "futures_oi_chg", "futures_oi_chg_pct") if c in evidence.columns]].to_dict("records")
        state = {
            "status": "STALE_SOURCE",
            "processed_snapshot_ts": pd.Timestamp(source_ts).isoformat(),
            "futures_source_ts": pd.Timestamp(source_ts).isoformat(),
            "values": values,
        }
        _save_live_futures_state(state)
        return state
    return {}


def _apply_live_futures_delay_policy(
    pred: pd.DataFrame,
    snapshot_ts: pd.Timestamp,
    futures_fresh: bool = False,
) -> pd.DataFrame:
    """Keep last Futures values after 5 minutes without fresh evidence and mark D."""
    if pred is None or pred.empty:
        return pred
    out = pred.copy()
    state = _load_live_futures_state()

    if futures_fresh and _live_futures_present(out):
        cols = [c for c in ("futures_oi_chg", "futures_oi_chg_pct") if c in out.columns]
        source_ts = pd.to_datetime(out.attrs.get("futures_source_ts"), errors="coerce")
        if pd.isna(source_ts):
            source_ts = pd.Timestamp(snapshot_ts)
        state = {
            "status": "FRESH",
            "processed_snapshot_ts": pd.Timestamp(source_ts).isoformat(),
            "futures_source_ts": pd.Timestamp(source_ts).isoformat(),
            "values": out[["symbol"] + cols].to_dict("records") if "symbol" in out.columns else [],
        }
        _save_live_futures_state(state)
        out["futures_oi_status"] = "FRESH"
        out["futures_oi_delayed"] = False
        return out

    if not state.get("values"):
        state = _hydrate_live_futures_state_from_source(
            pd.Timestamp(snapshot_ts).date().isoformat() if pd.notna(snapshot_ts) else "",
            pd.Timestamp(snapshot_ts) if pd.notna(snapshot_ts) else pd.NaT,
        )

    last_ts = pd.to_datetime(
        state.get("futures_source_ts") or state.get("processed_snapshot_ts"),
        errors="coerce",
    ) if state else pd.NaT
    age = (pd.Timestamp(snapshot_ts) - last_ts).total_seconds() if pd.notna(last_ts) and pd.notna(snapshot_ts) else None
    delayed = age is not None and age >= LIVE_FUTURES_DELAY_SECONDS

    if delayed and state.get("values") and "symbol" in out.columns:
        saved = pd.DataFrame(state["values"])
        if not saved.empty and "symbol" in saved.columns:
            saved = saved.drop_duplicates("symbol").set_index("symbol")
            idx = out["symbol"].astype(str)
            for col in ("futures_oi_chg", "futures_oi_chg_pct"):
                if col in saved.columns:
                    restored = pd.to_numeric(idx.map(saved[col]), errors="coerce")
                    current = pd.to_numeric(out[col], errors="coerce") if col in out.columns else pd.Series(pd.NA, index=out.index)
                    out[col] = restored.combine_first(current)

    out["futures_oi_status"] = "DELAYED" if delayed else "PENDING"
    out["futures_oi_delayed"] = delayed
    return out


def latest_live() -> tuple[
    Path | None,
    pd.DataFrame,
    pd.Timestamp,
    str,
]:
    """Return the latest authoritative LIVE/session snapshot.

    LIVE is source-driven.  A stale persisted snapshot can accelerate a repeat
    render, but it can never choose the session.  The latest valid Daywise
    session is resolved first from the read-only source repository.
    """
    try:
        session_day, available, current_day_has_source = _latest_session_sources()

        persisted = _load_persisted_live_snapshot()

        if not available:
            if persisted and isinstance(persisted.get("pred"), pd.DataFrame):
                ts = pd.to_datetime(
                    persisted.get("observation_timestamp"),
                    errors="coerce",
                )
                path = (
                    Path(persisted["source_path"])
                    if persisted.get("source_path")
                    else None
                )
                pred = _attach_first_alert_provenance(
                    persisted["pred"],
                    ts.date().isoformat() if pd.notna(ts) else None,
                    ts if pd.notna(ts) else None,
                )
                return (
                    path,
                    pred,
                    ts,
                    "No Daywise source is currently available.",
                )
            return None, pd.DataFrame(), pd.NaT, "No Daywise source snapshot is available."

        latest = available[-1]
        latest_ts = observation_ts(latest)

        if pd.isna(latest_ts):
            return None, pd.DataFrame(), pd.NaT, "Latest Daywise source has no valid timestamp."

        persisted_ts = (
            pd.to_datetime(
                persisted.get("observation_timestamp"),
                errors="coerce",
            )
            if persisted
            else pd.NaT
        )

        # Persisted LIVE data may be reused only when it belongs to the exact
        # authoritative latest source point.  It can never pin the dashboard
        # to an older session such as 10-Sep when 18-Sep source files exist.
        if (
            persisted
            and pd.notna(persisted_ts)
            and pd.Timestamp(persisted_ts) == pd.Timestamp(latest_ts)
            and isinstance(persisted.get("pred"), pd.DataFrame)
        ):
            pred = persisted["pred"].copy()
            pred = _attach_first_alert_provenance(
                pred,
                pd.Timestamp(latest_ts).date().isoformat(),
                pd.Timestamp(latest_ts),
            )
            futures = _read_ivrp_for_timestamp(
                pd.Timestamp(latest_ts).date().isoformat(),
                pd.Timestamp(latest_ts),
            )

            if not futures.empty:
                try:
                    future_cols = [
                        c for c in ("futures_oi_chg", "futures_oi_chg_pct")
                        if c in pred.columns
                    ]
                    existing_future_rows = 0
                    if future_cols:
                        existing_future_rows = int(
                            pred[future_cols]
                            .apply(pd.to_numeric, errors="coerce")
                            .notna()
                            .any(axis=1)
                            .sum()
                        )
                    total_rows = int(len(pred))
                    if existing_future_rows < total_rows:
                        raw, _ = load_primary_snapshot(latest, latest_ts)
                        option_ev = _day_option_evidence(
                            derive_straddle_values(raw)
                        )
                        pred, _ = _merge_snapshot_evidence(
                            pred,
                            option_ev,
                            futures,
                        )
                except Exception:
                    pass

                _save_persisted_live_snapshot(
                    latest,
                    latest_ts,
                    pred,
                    persisted.get("message", ""),
                )
                pred = _apply_live_futures_delay_policy(
                    pred,
                    latest_ts,
                    futures_fresh=True,
                )
            else:
                pred = _apply_live_futures_delay_policy(
                    pred,
                    latest_ts,
                    futures_fresh=False,
                )

            message = (
                f"Current source session: {session_day}"
                if current_day_has_source
                else f"Latest completed source session: {session_day}"
            )
            return latest, pred, latest_ts, message

        # Process the newly authoritative latest source point directly.
        # Do not call process_latest_snapshot_for_today(), because that
        # function may resolve "today" against a stale persisted session.
        path, pred, ts, message = _build_live_prediction_from_source(latest)

        if path is not None and not pred.empty and pd.notna(ts):
            return path, pred, ts, message

        # Source-readiness guard: a newly discovered Daywise workbook can be
        # visible in the repository while it is still being written.  An
        # empty read at that point is an ingestion/readiness condition, not
        # evidence that SDL has zero qualified decisions.  If a valid
        # persisted LIVE snapshot exists for the same trading session and is
        # older than this incomplete source point, keep that last completed
        # snapshot visible until the next valid source observation arrives.
        # Never fall back across sessions and never manufacture decisions.
        if (
            path is not None
            and pd.notna(ts)
            and isinstance(persisted, dict)
            and isinstance(persisted.get("pred"), pd.DataFrame)
            and not persisted["pred"].empty
            and pd.notna(persisted_ts)
            and pd.Timestamp(persisted_ts).date() == pd.Timestamp(ts).date()
            and pd.Timestamp(persisted_ts) < pd.Timestamp(ts)
        ):
            fallback_pred = persisted["pred"].copy()
            fallback_pred = _attach_first_alert_provenance(
                fallback_pred,
                pd.Timestamp(persisted_ts).date().isoformat(),
                pd.Timestamp(persisted_ts),
            )
            fallback_path = (
                Path(persisted["source_path"])
                if persisted.get("source_path")
                else path
            )
            fallback_pred = _apply_live_futures_delay_policy(
                fallback_pred,
                pd.Timestamp(persisted_ts),
                futures_fresh=False,
            )
            fallback_message = (
                f"LIVE source update is still being prepared — showing last completed "
                f"snapshot ({pd.Timestamp(persisted_ts).strftime('%H:%M:%S')})."
            )
            return fallback_path, fallback_pred, pd.Timestamp(persisted_ts), fallback_message

        # A valid, readable source can legitimately produce no qualified
        # decisions.  Preserve that exact source timestamp rather than
        # falling back to an unrelated session.
        if path is not None and pd.notna(ts):
            return path, pred, ts, message

        return None, pd.DataFrame(), pd.NaT, message or "Unable to process latest source."

    except Exception as exc:
        return None, pd.DataFrame(), pd.NaT, f"{type(exc).__name__}: {exc}"


def _render_live_content() -> None:
    path, pred, data_ts, message = latest_live()

    if path is None:
        st.warning(message)
        return

    now = pd.Timestamp.now(tz=IST)
    market_state, scheduled_trading_day = _nse_market_state(now)

    # Compact live context strip.
    # The data session is determined by the source repository, not by the
    # persisted dashboard state.  On weekends/holidays the latest completed
    # source session is intentionally preserved.
    current_day = now.date()
    preserved_session = (
        pd.notna(data_ts)
        and data_ts.date() != current_day
    )

    snapshot_label = (
        "LAST AVAILABLE SESSION"
        if preserved_session
        else "LATEST SOURCE SNAPSHOT"
    )

    if not scheduled_trading_day:
        snapshot_note = "Latest completed trading session · market not scheduled today"
    elif preserved_session:
        snapshot_note = "Waiting for today's first Daywise source snapshot"
    else:
        snapshot_note = "Actual Daywise source observation time"

    if preserved_session:
        if market_state == "NON-TRADING DAY":
            context_message = (
                f"<b>PREVIOUS SESSION PRESERVED</b> · Market is not scheduled to trade today. "
                f"Showing the latest completed source session: "
                f"<b>{safe_text(fmt_time(data_ts, True))}</b>."
            )
        else:
            context_message = (
                "<b>PREVIOUS SESSION PRESERVED</b> · No Daywise snapshot is available "
                "for today's trading session yet. The dashboard will switch automatically "
                "when the first new source snapshot arrives."
            )
        st.markdown(
            '<div class="queue-header-note" style="margin:0 0 8px 0">'
            + context_message
            + '</div>',
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
              <div class="utility-value amber">{safe_text(market_state)}</div>
              <div class="utility-note">NSE F&amp;O session context</div>
            </div>
            <div class="utility-cell">
              <div class="utility-label">DECISION MODE</div>
              <div class="utility-value">
                {
                    "PRESERVED SESSION"
                    if preserved_session
                    else "FACTS ONLY"
                }
              </div>
              <div class="utility-note">No dashboard re-scoring</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if preserved_session and pd.notna(data_ts):
        st.caption(
            f"Data session: {safe_text(fmt_time(data_ts, True))} · "
            f"Market state: {safe_text(market_state)} · "
            f"Session selection is source-driven."
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

    st.markdown(
        f'<div class="live-feed-summary">'
        f'Latest source: {safe_text(fmt_time(data_ts, True))} · '
        f'{len(pred)} qualified decisions · Live Queue filters and data are live-session only.'
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

    # Performance rule: Priority Radar is an SDL prioritisation view only.
    # Do not fetch/analyse/render external news here. News belongs exclusively
    # to the dedicated News section and must never block LIVE/Radar rendering.

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

    # LIVE QUEUE is independently collapsible. Collapsing it does not alter
    # Priority Radar or Replay state.
    with st.expander(
        "LIVE QUEUE · FILTERED DECISION TABLE · click to expand / collapse",
        expanded=False,
    ):
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

        # Stock detail remains inside the Live Queue workspace and is itself
        # independently collapsed by its existing control.
        render_stock_detail(
            filtered if not filtered.empty else pred,
            "live_detail",
        )

    # B4 is deliberately rendered AFTER the core LIVE surface.
    # Alert evaluation can touch the point-in-time cache and AlertStore; it must
    # never delay Priority Radar/LIVE visibility during a Streamlit rerun.
    emitted_alerts = _b4_emit_alerts(pred, data_ts) if path is not None else []
    _render_b4_alert_drawer(emitted_alerts, pred)


# ============================================================================
# SECTOR ANALYSIS — EXISTING NEWS FEED ADAPTER (PRESENTATION ONLY)
# ============================================================================

def _quality_external_news_feed(query: str) -> list[dict]:
    q = str(query or '').strip()
    if not q:
        return []
    try:
        url = 'https://news.google.com/rss/search?' + urlencode({'q': q, 'hl': 'en-IN', 'gl': 'IN', 'ceid': 'IN:en'})
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=3) as response:
            root = ET.fromstring(response.read())
        allowed = {'mint','livemint','moneycontrol','cnbc tv18','cnbctv18','reuters','economic times','economictimes','business standard','financial express','businessline','the hindu businessline'}
        items = []
        for item in root.findall('./channel/item')[:12]:
            title = (item.findtext('title') or '').strip()
            stamp = (item.findtext('pubDate') or '').strip()
            source = (item.findtext('source') or 'Google News').strip()
            if title and any(name in source.casefold() for name in allowed):
                items.append({'title': title, 'timestamp': stamp, 'source': source})
        return items
    except Exception:
        return []

@st.cache_data(ttl=900, show_spinner=False)
def _quality_news_collection() -> list[dict]:
    queries = (
        'India stocks (site:livemint.com OR site:moneycontrol.com OR site:cnbctv18.com)',
        'India markets (site:reuters.com OR site:economictimes.indiatimes.com OR site:business-standard.com)',
        'India stocks regulator policy (site:financialexpress.com OR site:thehindubusinessline.com)',
    )
    rows, seen = [], set()
    for query in queries:
        for item in _quality_external_news_feed(query):
            title = str(item.get('title', '')).strip()
            key = title.casefold()
            if not title or key in seen:
                continue
            seen.add(key)
            rows.append(item)
    return rows[:30]

def sector_analysis_news_provider() -> list[dict]:
    junk = ('price target','target price','forecast','prediction','technical analysis','technical outlook','watchlist','should you buy','buy or sell','share price today','stock price today','multibagger','top stocks to buy','stocks to watch','market forecast')
    return [
        {'title': str(item.get('title','')).strip(), 'timestamp': item.get('timestamp'), 'source': item.get('source','Google News')}
        for item in _quality_news_collection()
        if str(item.get('title','')).strip() and not any(term in str(item.get('title','')).casefold() for term in junk)
    ][:20]

POSITIVE_NEWS_TERMS = (
    "order", "contract", "award", "approval", "acquisition", "investment",
    "expansion", "capacity", "results", "earnings", "profit", "guidance",
    "upgrade", "deal", "stake", "tariff cut", "policy support",
)
NEGATIVE_NEWS_TERMS = (
    "loss", "decline", "downgrade", "penalty", "fine", "default", "fraud",
    "litigation", "investigation", "resignation", "delay", "cancel", "cut",
    "weak", "warning", "regulatory", "commission cap", "expense of management",
)
MAJOR_NEWS_TERMS = (
    "regulator", "regulatory", "irdai", "rbi", "sebi", "government", "ministry",
    "order", "contract", "acquisition", "merger", "stake", "fund raising",
    "fundraising", "capital", "results", "earnings", "profit", "loss",
    "investigation", "penalty", "tariff", "policy", "guidance", "capacity",
    "war", "oil", "crude", "rate", "bond yield", "sanction", "export",
)
GLOBAL_NEWS_TERMS = (
    "iran", "middle east", "oil", "crude", "brent", "fed", "federal reserve",
    "us rates", "tariff", "china", "global", "geopolitical", "war", "monsoon",
    "bond yield", "treasury yield",
)
SECTOR_NEWS_TERMS = (
    "power", "utilities", "energy", "renewable", "solar", "wind", "grid",
    "transmission", "banking", "pharma", "auto", "steel", "metal", "it sector",
    "insurance", "insurer", "irdai", "reinsurance", "general insurance",
    "life insurance", "health insurance", "insurance distribution",
)
NEWS_JUNK_TERMS = (
    "price target", "target price", "forecast", "prediction", "technical analysis",
    "technical outlook", "watchlist", "should you buy", "buy or sell",
    "share price today", "stock price today", "multibagger", "penny stock",
    "top stocks to buy", "stocks to watch", "ai-generated", "market forecast",
)
QUALITY_NEWS_SOURCES = {
    "mint", "livemint", "moneycontrol", "cnbc tv18", "cnbctv18", "reuters",
    "economictimes", "economic times", "business standard", "the hindu businessline",
    "businessline", "financial express",
}

def _news_terms(text: str, terms: tuple[str, ...]) -> int:
    value = str(text or "").lower()
    return sum(1 for term in terms if term in value)

def _news_direction(text: str) -> int:
    pos = _news_terms(text, POSITIVE_NEWS_TERMS)
    neg = _news_terms(text, NEGATIVE_NEWS_TERMS)
    return 1 if pos > neg else -1 if neg > pos else 0

def _news_scope(text: str, company: bool = False) -> str:
    value = str(text or "").lower()
    if company:
        return "COMPANY"
    if _news_terms(value, GLOBAL_NEWS_TERMS):
        return "MARKET / MACRO"
    if _news_terms(value, SECTOR_NEWS_TERMS):
        return "SECTOR / THEME"
    return "MARKET / DOMESTIC"

def _news_is_junk(text: str) -> bool:
    return _news_terms(text, NEWS_JUNK_TERMS) > 0

def _news_quality_score(item: dict) -> float:
    text = str(item.get("text", ""))
    source = str(item.get("source", "")).lower()
    score = min(5, _news_terms(text, MAJOR_NEWS_TERMS)) * 2.0
    score += min(3, _news_terms(text, POSITIVE_NEWS_TERMS + NEGATIVE_NEWS_TERMS))
    if any(q in source for q in QUALITY_NEWS_SOURCES):
        score += 3.0
    if _news_is_junk(text):
        score -= 8.0
    return score


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


# ============================================================================
# B4 LIVE ALERT EVALUATION — PRESENTATION/ALERT LAYER ONLY
# ============================================================================

_B4_FIELD_MAP = {
    "Futures OI Change": ("_futures_oi", "futures_oi_chg"),
    "Futures OI Change %": ("futures_oi_chg_pct",),
    "PE − CE OI Change": ("pe_minus_ce_oi_chg", "Tot PE-CE OI Chg"),
    "PCR": ("pcr", "PCR", "PCR Ratio", "pcr_ratio"),
    "Momentum %": ("momentum_pct", "momentum", "price_move_pct", "signed_price_move_pct"),
    "Straddle Progress": ("progress",),
    "Price Change %": ("price_move_pct", "signed_price_move_pct"),
}

def _b4_value(row, label):
    for key in _B4_FIELD_MAP.get(label, ()): 
        if key in row.index:
            v=row.get(key)
            if pd.notna(v):
                try: return float(v)
                except Exception: return v
    return None

def _b4_context(row, ts, day):
    return {"symbol":str(row.get("symbol",row.get("Symbol",""))).strip().upper(),"trading_date":day,"observation_timestamp":pd.Timestamp(ts).isoformat(),"values":{k:_b4_value(row,k) for k in _B4_FIELD_MAP}}

def _b4_compare(a, b, op):
    if a is None or b is None:
        return False
    try:
        a = float(a)
        b = float(b)
    except Exception:
        return False
    return {
        ">": a > b,
        ">=": a >= b,
        "<": a < b,
        "<=": a <= b,
        "=": a == b,
        "!=": a != b,
    }.get(str(op).upper(), False)


def _b4_condition(current, threshold, operator):
    """Evaluate whether the current observation satisfies a B4 rule."""
    if current is None:
        return False
    op = str(operator or ">=").upper()
    if op in {">", ">=", "<", "<=", "=", "!=", "CHANGED_TO"}:
        return _b4_compare(current, threshold, op if op != "CHANGED_TO" else "=")
    try:
        cv = float(current)
        if op in {"CROSSED_ABOVE", "CROSSED_BELOW"}:
            tv = float(threshold)
            return cv > tv if op == "CROSSED_ABOVE" else cv < tv
        if op in {"ENTERED_RANGE", "EXITED_RANGE"}:
            if not isinstance(threshold, (list, tuple)) or len(threshold) != 2:
                return False
            lo, hi = sorted(float(x) for x in threshold)
            return lo <= cv <= hi
    except Exception:
        pass
    if op == "BECAME_TRUE":
        return bool(current)
    if op == "BECAME_FALSE":
        return not bool(current)
    return False


def _b4_edge(previous, current, threshold, operator):
    """Evaluate approved crossing/state operators using two observations."""
    if current is None:
        return False
    op = str(operator or ">=").upper()
    if op in {">", ">=", "<", "<=", "=", "!="}:
        return _b4_compare(current, threshold, op) and (
            previous is None or not _b4_compare(previous, threshold, op)
        )
    if previous is None:
        return False
    try:
        pv, cv, tv = float(previous), float(current), float(threshold)
    except Exception:
        return False
    if op == "CROSSED_ABOVE":
        return pv <= tv and cv > tv
    if op == "CROSSED_BELOW":
        return pv >= tv and cv < tv
    if op == "ENTERED_RANGE":
        if not isinstance(threshold, (list, tuple)) or len(threshold) != 2:
            return False
        lo, hi = sorted(float(x) for x in threshold)
        return not (lo <= pv <= hi) and lo <= cv <= hi
    if op == "EXITED_RANGE":
        if not isinstance(threshold, (list, tuple)) or len(threshold) != 2:
            return False
        lo, hi = sorted(float(x) for x in threshold)
        return lo <= pv <= hi and not (lo <= cv <= hi)
    if op == "CHANGED_TO":
        return previous != current and current == threshold
    if op == "BECAME_TRUE":
        return not bool(previous) and bool(current)
    if op == "BECAME_FALSE":
        return bool(previous) and not bool(current)
    return False


def _b4_cache_signature() -> tuple:
    """Cheap invalidation key for the B4 previous-context cache."""
    try:
        stat = DAY_POINT_IN_TIME_CACHE_FILE.stat()
        return (int(stat.st_mtime_ns), int(stat.st_size))
    except Exception:
        return (0, 0)


@st.cache_data(ttl=10, show_spinner=False)
def _b4_previous_context_map(
    day: str,
    observation_iso: str,
    symbols: tuple[str, ...],
    cache_signature: tuple,
) -> dict:
    """Resolve all prior LIVE alert contexts in one cache pass.

    The previous implementation reopened/unpickled the entire day cache once
    per candidate symbol.  That made the new alert layer a hot-path O(symbols
    x snapshots) operation and could stall the complete dashboard.  This
    resolver performs one read and one chronological pass, then returns only
    the small symbol->context map needed by the alert evaluator.
    """
    del cache_signature  # used by Streamlit cache invalidation
    wanted = {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
    if not wanted:
        return {}

    observation_ts = pd.to_datetime(observation_iso, errors="coerce")
    if pd.isna(observation_ts):
        return {}

    cache = _load_day_point_cache()
    day_cache = cache.get(str(day), {}) if isinstance(cache, dict) else {}
    entries = day_cache.get("snapshots", {}) if isinstance(day_cache, dict) else {}
    best: dict[str, tuple[pd.Timestamp, dict]] = {}

    for key, entry in entries.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("pred"), pd.DataFrame):
            continue
        ts = pd.to_datetime(entry.get("timestamp", key), errors="coerce")
        if pd.isna(ts) or ts >= observation_ts:
            continue

        frame = entry["pred"]
        col = (
            "symbol" if "symbol" in frame.columns
            else "Symbol" if "Symbol" in frame.columns
            else None
        )
        if not col:
            continue

        symbols_series = frame[col].astype(str).str.strip().str.upper()
        for idx in frame.index[symbols_series.isin(wanted)]:
            row = frame.loc[idx]
            symbol = str(row.get(col, "")).strip().upper()
            if not symbol:
                continue
            previous = best.get(symbol)
            if previous is not None and ts <= previous[0]:
                continue
            best[symbol] = (ts, _b4_context(row, ts, day))

    return {symbol: context for symbol, (_ts, context) in best.items()}


def _b4_emit_alerts(pred: pd.DataFrame, observation_ts: pd.Timestamp) -> list[dict]:
    """Evaluate the approved B4 rules and persist only genuine new events.

    This is deliberately an additive presentation/alert layer.  SDL candidate
    selection, scoring and gates remain untouched.  Previous point-in-time
    values are resolved once, while AlertStore owns persistent re-arm/dedup
    state so a browser refresh or Streamlit rerun cannot manufacture repeats.
    """
    if AlertStore is None or pred is None or pred.empty or pd.isna(observation_ts):
        return []
    rules = _UI.get("alert_rules", [])
    if not isinstance(rules, list) or not rules:
        return []

    observation_ts = pd.Timestamp(observation_ts)
    day = observation_ts.date().isoformat()
    symbols = tuple(sorted({
        str(value).strip().upper()
        for value in (
            pred["symbol"].tolist() if "symbol" in pred.columns
            else pred["Symbol"].tolist() if "Symbol" in pred.columns else []
        ) if str(value).strip()
    }))
    previous_map = _b4_previous_context_map(day, observation_ts.isoformat(), symbols, _b4_cache_signature())
    store = AlertStore(ALERT_STORE_FILE)
    emitted: list[dict] = []

    for idx, raw_rule in enumerate(rules):
        if not isinstance(raw_rule, dict) or not raw_rule.get("enabled", True):
            continue
        rule = _normalize_b4_rule(raw_rule, idx)
        rule_id = str(rule["id"])
        # Persist the exact runtime rule consumed by this evaluation. This makes
        # configuration edits durable and gives AlertStore a stable rule id.
        try:
            store.save_rule(rule, pd.Timestamp.utcnow().isoformat())
        except Exception:
            pass

        field = str(rule.get("field", "")).strip()
        operator = str(rule.get("operator", ">=")).strip()
        threshold = rule.get("value")
        severity = "HIGH" if str(rule.get("name")) in {"Futures OI Spike", "PCR Extreme", "Strong Breakout"} else "INFO"

        for _, row in pred.iterrows():
            ctx = _b4_context(row, observation_ts, day)
            sym = ctx["symbol"]
            if not sym:
                continue
            old = previous_map.get(sym)
            current_value = ctx["values"].get(field)
            previous_value = (old or {}).get("values", {}).get(field) if old else None
            matched = _b4_edge(previous_value, current_value, threshold, operator)
            current_condition = _b4_condition(current_value, threshold, operator)
            observation_iso = ctx["observation_timestamp"]

            # Keep the persistent re-arm state synchronized on every observation,
            # including a FALSE condition. This is what lets a later threshold
            # crossing fire again after the stock has actually left the condition.
            try:
                persistent_emit = store.should_emit(
                    rule,
                    symbol=sym,
                    trading_date=day,
                    matched=bool(current_condition),
                    observation_timestamp=observation_iso,
                )
            except Exception:
                persistent_emit = matched

            # First observed point is a baseline, never a synthetic alert.
            # Subsequent alerts require both the point-in-time edge and the
            # persistent re-arm decision.
            if old is None or not matched or not persistent_emit:
                continue

            alert_id = hashlib.sha1(f"{rule_id}|{sym}|{observation_iso}".encode()).hexdigest()[:24]
            threshold_text = f"{float(threshold):g}" if isinstance(threshold, (int, float)) else str(threshold)
            event = {
                "alert_id": alert_id,
                "rule_id": rule_id,
                "rule_name": str(rule.get("name", "Alert rule")),
                "trading_date": day,
                "symbol": sym,
                "observation_timestamp": observation_iso,
                "direction": row.get("direction_label"),
                "strength": row.get("strength"),
                "message": f"{field} {operator} {threshold_text}",
                "severity": severity,
                "sound": bool(rule.get("sound", False)),
                "payload": ctx,
                "created_at": pd.Timestamp.utcnow().isoformat(),
            }
            if store.record_event(event):
                emitted.append(event)

    st.session_state["b4_new_alerts"] = emitted
    return emitted


# ============================================================================
# B4 ALERT DRAWER ADAPTER
# ============================================================================

def _load_b4_alert_events(limit: int = 8) -> list[dict]:
    """Read bounded persisted alert events for the B4 drawer."""
    if AlertStore is None:
        return []
    try:
        store = AlertStore(ALERT_STORE_FILE)
        return store.recent_events(limit=max(1, min(int(limit), 100)))
    except Exception as exc:
        _UI["b4_store_error"] = f"{type(exc).__name__}: {exc}"
        return []


def _render_b4_alert_drawer(emitted: list[dict] | None = None, pred: pd.DataFrame | None = None) -> None:
    """Render the B4 drawer and expose integration failures instead of hiding them."""
    if render_alert_drawer is None:
        if _B4_IMPORT_ERROR:
            st.warning(f"B4 alert drawer unavailable: {_B4_IMPORT_ERROR}", icon="⚠️")
        return
    try:
        events = _load_b4_alert_events(8)
        history_events = _load_b4_alert_events(50)
        sound_enabled = bool(_UI.get("alert_sound_enabled", False))
        sound_volume = float(_UI.get("alert_sound_volume", 0.35))
        sound_tone = str(_UI.get("alert_sound_tone", "soft"))
        rules = _UI.get("alert_rules", [])
        if not isinstance(rules, list):
            rules = []
        newest_id = str(events[0].get("alert_id", "")) if events else ""
        baseline = st.session_state.get("sdl_alert_latest_id")
        new_alert = bool(emitted) or bool(baseline is not None and newest_id and newest_id != str(baseline))
        if newest_id:
            st.session_state.sdl_alert_latest_id = newest_id
        new_sound = bool(new_alert and any(bool(event.get("sound", False)) for event in (emitted or [])))

        def _alert_chart_provider(event: dict):
            day = str(event.get("trading_date") or "")
            symbol = str(event.get("symbol") or "").strip().upper()
            cutoff = str(event.get("observation_timestamp") or "") or None
            if not day or not symbol:
                return pd.DataFrame(columns=["Observation", "Close"])
            return _symbol_price_timeline(day, symbol, cutoff, _cache_file_signature())

        diagnostic = _UI.get("b4_store_error") or _UI.get("b4_runtime_error") or _B4_IMPORT_ERROR

        def _daily_radar_provider():
            cols=[]
            for _, rr in pred.iterrows():
                cols.append((
                    str(rr.get("symbol") or "").strip().upper(),
                    rr.get("Price Chg %"),
                    rr.get("sector") or rr.get("Sector") or rr.get("industry") or "",
                    rr.get("company_name") or rr.get("Company Name") or rr.get("name") or "",
                ))
            return daily_catalyst_radar(tuple(x[0] for x in cols), tuple(cols))

        result = render_alert_drawer(
            events,
            history_events=history_events,
            sound_enabled=sound_enabled,
            sound_volume=sound_volume,
            sound_tone=sound_tone,
            new_alert=new_alert,
            new_alert_sound=new_sound,
            rules=rules,
            chart_provider=_alert_chart_provider,
            news_provider=_daily_radar_provider,
            diagnostic=str(diagnostic) if diagnostic else None,
        )
        if isinstance(result, dict):
            returned_rules = result.get("rules", rules) or _default_b4_rules()
            normalized_rules = [_normalize_b4_rule(rule, i) for i, rule in enumerate(returned_rules)]
            _UI.update({
                "alert_sound_enabled": bool(result.get("enabled", sound_enabled)),
                "alert_sound_volume": float(result.get("volume", sound_volume)),
                "alert_sound_tone": str(result.get("tone", sound_tone)),
                "alert_rules": normalized_rules,
                "alert_config_schema": 4,
            })
            if AlertStore is not None:
                store = AlertStore(ALERT_STORE_FILE)
                updated_at = pd.Timestamp.now(tz=IST).isoformat()
                for rule in normalized_rules:
                    store.save_rule(rule, updated_at)
            save_ui_settings(
                alert_sound_enabled=_UI["alert_sound_enabled"],
                alert_sound_volume=_UI["alert_sound_volume"],
                alert_sound_tone=_UI["alert_sound_tone"],
                alert_rules=_UI["alert_rules"],
                alert_config_schema=4,
            )
    except Exception as exc:
        _UI["b4_runtime_error"] = f"{type(exc).__name__}: {exc}"
        st.warning(f"B4 alert drawer runtime error: {type(exc).__name__}: {exc}", icon="⚠️")


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
        '<div class="header-control" style="display:flex;align-items:center;justify-content:center">'
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
    # Streamlit fragments rerun only the LIVE content. Replay, navigation,
    # settings and other static page sections are not browser-reloaded.
    _refresh_seconds = max(30, int(_UI.get("refresh_seconds", 60)))
    _live_renderer = _render_live_content
    if bool(_UI.get("auto_refresh", False)) and hasattr(st, "fragment"):
        _live_renderer = st.fragment(run_every=_refresh_seconds)(_render_live_content)
    _live_renderer()

    # Historical cache build monitor is intentionally outside the LIVE
    # fragment and outside the Replay expander. A dedicated lightweight
    # fragment keeps the progress display live even when Auto Refresh is off.
    if hasattr(st, "fragment"):
        _cache_monitor_renderer = st.fragment(run_every=3)(_render_cache_build_state)
        _cache_monitor_renderer()
    else:
        _render_cache_build_state()

    # Replay remains outside the LIVE fragment by design. Its selected day,
    # snapshot and cache state therefore remain untouched by Live refreshes.
    replay_view()
