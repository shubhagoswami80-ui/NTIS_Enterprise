from __future__ import annotations

from pathlib import Path
import html
import json
import re

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
# NTIS SDL — APPROVED DECISION CENTRE
#
# CONTROLLED UI PATCH — 28-Aug-2026
#
# PRESENTATION LAYER ONLY.
# SDL/app.py is deliberately NOT used or modified.
# Existing SDL pipeline / qualification / prediction / evidence logic remains
# authoritative. This file only presents its outputs.
#
# Existing launcher remains:
#   SDL\start_sdl_preview.ps1
#
# Do not add another launcher for this dashboard.
# ============================================================================

st.set_page_config(
    page_title="NTIS SDL — Intraday Decision Centre",
    page_icon="SDL",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================================
# APPROVED DARK VISUAL SYSTEM
# ============================================================================

st.markdown(
    r"""
<style>
:root{
  --bg:#050d18;
  --bg2:#071321;
  --panel:#091729;
  --panel2:#0e1d31;
  --panel3:#13243a;
  --line:#203653;
  --line2:#29476e;
  --text:#eef4fb;
  --muted:#91a3ba;
  --red:#ff3038;
  --red2:#ff5960;
  --green:#18df82;
  --purple:#7a62ff;
  --amber:#ffb21c;
  --cyan:#16cfe2;
  --blue:#6d99ff;
}

/* Streamlit chrome must not push/cover the approved dashboard. */
.stApp{
  background:
    radial-gradient(circle at 50% -16%,#102b54 0%,transparent 38%),
    linear-gradient(180deg,#050d18 0%,#071321 100%);
  color:var(--text);
}
.block-container{
  max-width:1660px!important;
  padding:46px 18px 22px!important;
}
header[data-testid="stHeader"]{
  background:#040a12!important;
  height:38px!important;
  box-shadow:none!important;
}
[data-testid="stSidebar"]{display:none!important}
div[data-testid="stToolbar"],
div[data-testid="stDecoration"]{display:none!important}
footer{display:none!important}
div[data-testid="stAppViewContainer"]{background:transparent!important}
div[data-testid="stVerticalBlock"]{gap:.34rem!important}
div[data-testid="stSelectbox"]>div>div,
div[data-testid="stDateInput"] input,
div[data-testid="stTimeInput"] input{
  background:#101f35!important;
  color:#eef4fb!important;
  border:1px solid #29405e!important;
}
div[data-testid="stSelectbox"] svg,
div[data-testid="stDateInput"] svg,
div[data-testid="stTimeInput"] svg{
  fill:#b9c8dc!important;
  color:#b9c8dc!important;
}
p,label,span,div,button,input,textarea{
  font-family:Inter,Segoe UI,Arial,sans-serif!important;
  box-sizing:border-box;
}

/* Native Streamlit controls must remain inside the approved dark system.
   Do not depend on HTML wrapper divs around Streamlit widgets. */
div[data-testid="stButton"] button{
  min-height:35px!important;
  border-radius:7px!important;
  font-size:10px!important;
  font-weight:900!important;
  padding:4px 10px!important;
  background:#0d1b2e!important;
  border:1px solid #29405e!important;
  color:#e7eef8!important;
  box-shadow:none!important;
}
div[data-testid="stButton"] button:hover{
  background:#142743!important;
  border-color:#5b78a5!important;
  color:#fff!important;
}
div[data-testid="stButton"] button[kind="primary"]{
  background:#f02f35!important;
  border-color:#ff5960!important;
  color:#fff!important;
}
div[data-testid="stButton"] button[kind="primary"]:hover{
  background:#ff4047!important;
  border-color:#ff6970!important;
}
div[data-testid="stCheckbox"] label p{
  color:#eef4fb!important;
  font-size:9px!important;
  font-weight:850!important;
}
div[data-testid="stSelectbox"]>div>div,
div[data-testid="stDateInput"] input,
div[data-testid="stTimeInput"] input,
div[data-testid="stTextInput"] input{
  background:#101f35!important;
  color:#eef4fb!important;
  border:1px solid #29405e!important;
  border-radius:7px!important;
}
div[data-testid="stSelectbox"] label,
div[data-testid="stDateInput"] label,
div[data-testid="stTimeInput"] label,
div[data-testid="stTextInput"] label{
  color:#aebdd1!important;
  font-size:9px!important;
  font-weight:850!important;
}
div[data-testid="stSelectbox"] svg,
div[data-testid="stDateInput"] svg,
div[data-testid="stTimeInput"] svg{
  fill:#b9c8dc!important;
  color:#b9c8dc!important;
}

/* ---------- HEADER ---------- */
.sdl-header{
  width:100%;
  min-height:62px;
  padding:8px 12px;
  margin:0 0 9px;
  background:linear-gradient(105deg,#061126 0%,#0b1c3a 55%,#102a58 100%);
  border:1px solid #20375d;
  border-radius:8px;
  box-shadow:0 8px 26px rgba(0,0,0,.28);
}
.sdl-brand{
  color:#f6f9ff;
  font-size:20px!important;
  line-height:1.05;
  font-weight:950!important;
  letter-spacing:.02em;
}
.sdl-sub{
  color:#b7c5da;
  font-size:9px!important;
  font-weight:750!important;
  letter-spacing:.08em;
  margin-top:4px;
}
.header-nav div[data-testid="stButton"] button,
.header-action div[data-testid="stButton"] button{
  min-height:35px!important;
  border-radius:7px!important;
  font-size:10px!important;
  font-weight:900!important;
  padding:3px 9px!important;
  background:#0d1b2e!important;
  border:1px solid #29405e!important;
  color:#e7eef8!important;
}
.header-nav div[data-testid="stButton"] button:hover,
.header-action div[data-testid="stButton"] button:hover{
  border-color:#5b78a5!important;
  color:#fff!important;
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
  padding:7px 10px;
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
  min-height:35px!important;
  background:#101f35!important;
  border:1px solid #29405e!important;
  color:#fff!important;
  font-size:10px!important;
}
.header-control div[data-testid="stSelectbox"] svg{
  fill:#b9c8dc!important;
  color:#b9c8dc!important;
}

/* ---------- TOP UTILITY STRIP ---------- */
.utility-strip{
  width:100%;
  min-height:50px;
  padding:7px 10px;
  margin:0 0 9px;
  background:linear-gradient(105deg,#081a35 0%,#0d2448 55%,#102b58 100%);
  border:1px solid #203b66;
  border-radius:8px;
  box-shadow:0 7px 22px rgba(0,0,0,.22);
}
.utility-cell{
  min-height:34px;
  padding:3px 9px;
  border-right:1px solid #203653;
}
.utility-cell:last-child{border-right:0}
.utility-label{
  color:#7f95b3;
  font-size:7px!important;
  font-weight:950!important;
  letter-spacing:.11em;
}
.utility-value{
  color:#eef4fb;
  font-size:10px!important;
  font-weight:900!important;
  margin-top:3px;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.utility-value.green{color:#18df82}
.utility-value.amber{color:#ffb21c}
.utility-value.cyan{color:#16cfe2}
.utility-note{
  color:#8fa2bb;
  font-size:7px!important;
  margin-top:2px;
}

/* ---------- STATUS ---------- */
.status-strip{
  display:grid;
  grid-template-columns:1fr 1fr;
  background:#091729;
  border:1px solid #203653;
  border-radius:9px;
  overflow:hidden;
  margin-bottom:9px;
}
.status-cell{
  min-height:62px;
  padding:9px 13px;
}
.status-cell:first-child{border-right:1px solid #203653}
.status-label{
  color:#a8b8ce;
  font-size:9px!important;
  font-weight:950!important;
  letter-spacing:.12em;
}
.status-value{
  color:#f1f5fc;
  font-size:14px!important;
  font-weight:950!important;
  margin-top:5px;
}
.status-value.green{color:#18df82}
.status-foot{
  color:#8194ad;
  font-size:8px!important;
  margin-top:4px;
}
.live-state{
  color:#8fa3bb;
  font-size:8px!important;
  margin:0 2px 7px;
}

/* ---------- KPI ---------- */
.kpi-card{
  min-height:78px;
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
.kpi-card.cyan{border-color:#15546a}
.kpi-icon{
  float:left;
  width:30px;height:30px;
  border-radius:8px;
  margin-right:8px;
  display:flex;
  align-items:center;
  justify-content:center;
  background:#142a4c;
  color:#74a2ff;
  font-size:15px!important;
  font-weight:950!important;
}
.kpi-card.green .kpi-icon{background:#083324;color:#18df82}
.kpi-card.red .kpi-icon{background:#3b171d;color:#ff6570}
.kpi-card.purple .kpi-icon{background:#211957;color:#9b7cff}
.kpi-card.amber .kpi-icon{background:#39270b;color:#ffb31c}
.kpi-card.cyan .kpi-icon{background:#073341;color:#10d1e6}
.kpi-label{
  color:#aabbd0;
  font-size:9px!important;
  font-weight:950!important;
  letter-spacing:.10em;
}
.kpi-value{
  color:#f5f8ff;
  font-size:25px!important;
  line-height:1;
  font-weight:950!important;
  margin-top:6px;
}
.kpi-foot{
  color:#8a9ab1;
  font-size:8px!important;
  margin-top:6px;
}

/* ---------- FILTERS ---------- */
.filter-panel{
  background:#091729;
  border:1px solid #203653;
  border-radius:9px;
  padding:9px 11px 10px;
  margin-bottom:9px;
}
.filter-caption{
  color:#8fa2bb;
  font-size:9px!important;
  margin-bottom:7px;
}
.filter-title{
  color:#b7c6da;
  font-size:9px!important;
  font-weight:950!important;
  letter-spacing:.10em;
  margin-bottom:5px;
}
.filter-group{
  padding:0 10px;
  border-right:1px solid #1c304a;
}
.filter-group:first-child{padding-left:1px}
.filter-group:last-child{border-right:0;padding-right:1px}
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
  min-height:27px!important;
  margin:0!important;
}
div[data-testid="stRadio"] [role="radiogroup"] label p,
div[data-testid="stRadio"] [role="radiogroup"] label span{
  color:#e7eef8!important;
  font-size:9px!important;
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

/* ---------- RADAR ---------- */
.section-bar{
  background:linear-gradient(105deg,#081b38,#102c5b);
  border:1px solid #294b7b;
  border-radius:8px;
  padding:7px 10px;
  color:#fff;
  font-size:10px!important;
  font-weight:950!important;
  letter-spacing:.10em;
  margin-bottom:7px;
}
.radar-panel{
  background:#091729;
  border:1px solid #203653;
  border-radius:9px;
  padding:8px 10px;
  margin-bottom:9px;
}
.radar-title{
  color:#b1c0d3;
  font-size:9px!important;
  font-weight:950!important;
  letter-spacing:.10em;
  margin-bottom:5px;
}
.radar-card{
  min-height:78px;
  padding:7px;
  background:#0f1e33;
  border:1px solid #203a5b;
  border-radius:7px;
}
.radar-symbol{
  color:#f0f5fc;
  font-size:10px!important;
  font-weight:950!important;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.radar-meta{
  color:#93a5bd;
  font-size:8px!important;
  margin-top:3px;
}
.radar-progress{
  color:#ffb31c;
  font-size:14px!important;
  font-weight:950!important;
  margin-top:4px;
}
.radar-first{
  color:#7489a4;
  font-size:7px!important;
  margin-top:2px;
}

/* ---------- WORKSPACE ---------- */
.workspace-panel{
  background:#091729;
  border:1px solid #203653;
  border-radius:9px;
  overflow:hidden;
}
.panel-head{
  padding:9px 11px;
  background:#0e1d31;
  border-bottom:1px solid #203653;
}
.panel-title{
  color:#edf3fc;
  font-size:11px!important;
  font-weight:950!important;
}
.panel-meta{
  color:#8fa2bb;
  font-size:9px!important;
  margin-top:3px;
}
.queue-wrap{overflow-x:auto}
table.queue{
  width:100%;
  border-collapse:collapse;
  table-layout:fixed;
  font-size:10px!important;
}
table.queue th{
  background:#13243a;
  color:#a9b8ce;
  font-size:8px!important;
  font-weight:900!important;
  letter-spacing:.06em;
  text-align:left;
  padding:8px 5px;
  border-bottom:1px solid #2a4260;
  white-space:nowrap;
}
table.queue td{
  background:#0b192b;
  color:#e3ebf7;
  font-size:10px!important;
  padding:8px 5px;
  border-bottom:1px solid #1b2c43;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  vertical-align:middle;
}
.stock-cell{
  display:flex;
  align-items:center;
  gap:6px;
  font-weight:950!important;
}
.logo{
  width:24px;height:24px;
  flex:0 0 24px;
  border-radius:6px;
  background:#fff;
  color:#17325c;
  border:1px solid #415675;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:7px!important;
  font-weight:950!important;
}
.badge{
  display:inline-block;
  padding:4px 6px;
  border-radius:5px;
  font-size:8px!important;
  font-weight:950!important;
}
.badge-green{background:#0b3023;border:1px solid #19694a;color:#38e296}
.badge-red{background:#35171d;border:1px solid #773039;color:#ff6b75}
.badge-blue{background:#14284b;border:1px solid #3a5f9f;color:#93b2ff}
.badge-amber{background:#34260f;border:1px solid #6e521e;color:#ffc24d}
.up{color:#18df82!important;font-weight:950!important}
.down{color:#ff626c!important;font-weight:950!important}
.strength{color:#8fb0ff!important;font-weight:950!important}
.breakout{color:#18df82!important;font-weight:950!important}
.rail{
  display:inline-block;
  width:42px;height:5px;
  margin-left:5px;
  vertical-align:middle;
  border-radius:99px;
  background:#26384f;
  overflow:hidden;
}
.rail-fill{
  display:block;height:100%;
  border-radius:99px;
  background:#ffad17;
}
.rail-fill.break{background:#19d27f}
.view-more-row{
  padding:7px;
  border-top:1px solid #203653;
  text-align:center;
}
.view-more-row div[data-testid="stButton"] button{
  min-height:28px!important;
  background:#102038!important;
  border:1px solid #2a4565!important;
  color:#e0e8f4!important;
  font-size:9px!important;
  font-weight:900!important;
}

/* ---------- DETAIL ---------- */
.detail-body{padding:10px}
.detail-select div[data-testid="stSelectbox"]>div>div{
  min-height:31px!important;
  background:#0f1e33!important;
  border:1px solid #29415f!important;
  color:#fff!important;
  font-size:10px!important;
}
.detail-hero{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:7px;
  padding:7px 0 8px;
  border-bottom:1px solid #203653;
}
.detail-symbol{
  color:#f5f8fd;
  font-size:15px!important;
  font-weight:950!important;
}
.detail-sub{
  color:#8498b2;
  font-size:8px!important;
  margin-top:3px;
}
.detail-grid{
  display:grid;
  grid-template-columns:repeat(2,1fr);
  gap:6px;
  margin-top:8px;
}
.detail-card{
  background:#0f1e33;
  border:1px solid #203a59;
  border-radius:7px;
  padding:7px;
  min-height:60px;
}
.detail-label{
  color:#8da0b9;
  font-size:8px!important;
  font-weight:950!important;
  letter-spacing:.08em;
}
.detail-value{
  color:#f4f7fc;
  font-size:15px!important;
  font-weight:950!important;
  margin-top:4px;
  line-height:1.08;
}
.detail-foot{
  color:#758aa5;
  font-size:7px!important;
  margin-top:3px;
}
.process-box{
  background:#0f1e33;
  border:1px solid #203a59;
  border-radius:7px;
  padding:8px;
  margin-top:7px;
}
.process-value{
  color:#f5f8fd;
  font-size:21px!important;
  font-weight:950!important;
  margin-top:2px;
}
.process-rail{
  height:7px;
  background:#27384e;
  border-radius:99px;
  overflow:hidden;
  margin:7px 0;
}
.process-fill{
  height:100%;
  background:#ff4d5a;
  border-radius:99px;
}
.process-scale{
  display:flex;
  justify-content:space-between;
  color:#6f829d;
  font-size:7px!important;
}
.factor-box{
  background:#0b192b;
  border:1px solid #203653;
  border-radius:7px;
  margin-top:7px;
  padding:5px 8px;
}
.factor-row{
  display:flex;
  justify-content:space-between;
  padding:5px 0;
  border-bottom:1px solid #1b2c43;
  color:#dce5f2;
  font-size:8px!important;
}
.factor-row:last-child{border-bottom:0}
.support{color:#18d27a!important;font-weight:950!important}
.contradict{color:#ff626c!important;font-weight:950!important}
.neutral{color:#8ea0b8!important;font-weight:850!important}


/* ---------- CUMULATIVE TRADER CONTEXT ---------- */
.context-box{background:#0b192b;border:1px solid #203653;border-radius:7px;padding:8px;margin-top:7px}
.context-head{display:flex;justify-content:space-between;color:#edf3fc;font-size:9px!important;font-weight:950!important;letter-spacing:.08em}
.context-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:7px}
.context-card{background:#0f1e33;border:1px solid #203a59;border-radius:7px;padding:7px}
.context-label{color:#8da0b9;font-size:7px!important;font-weight:950!important;letter-spacing:.08em}
.context-value{color:#f4f7fc;font-size:12px!important;font-weight:950!important;margin-top:3px}
.history-box{background:#0b192b;border:1px solid #29415f;border-radius:7px;padding:8px;margin-top:7px}
.history-head{display:flex;justify-content:space-between;color:#e4ebf5;font-size:8px!important;font-weight:950!important}
.history-rail{height:7px;background:#26384f;border-radius:99px;overflow:hidden;margin-top:6px}
.history-fill{height:100%;background:#7a62ff;border-radius:99px}
@media(max-width:1200px){.context-grid{grid-template-columns:1fr 1fr}}

/* ---------- PLANNED PANELS ---------- */
.planned-panel{
  background:#091729;
  border:1px solid #203653;
  border-radius:9px;
  overflow:hidden;
  margin-bottom:7px;
  min-height:112px;
}
.planned-title{
  color:#edf3fc;
  font-size:9px!important;
  font-weight:950!important;
  letter-spacing:.08em;
  padding:9px 10px 0;
}
.planned-copy{
  color:#8da0b8;
  font-size:8px!important;
  line-height:1.35;
  padding:6px 10px 10px;
}
.planned-status{
  display:inline-block;
  margin:0 10px 8px;
  padding:4px 6px;
  border-radius:5px;
  background:#101f33;
  border:1px dashed #3a506d;
  color:#8fa1b8;
  font-size:7px!important;
}

/* ---------- REPLAY ---------- */
.replay-panel{
  background:#091729;
  border:1px solid #203653;
  border-radius:9px;
  padding:9px 11px;
  margin-top:9px;
}
.replay-title{
  color:#edf3fc;
  font-size:11px!important;
  font-weight:950!important;
}
.replay-note{
  color:#8ea0b8;
  font-size:9px!important;
  margin-top:3px;
}
.replay-panel div[data-testid="stDateInput"] input,
.replay-panel div[data-testid="stTimeInput"] input{
  background:#0f1e33!important;
  color:#edf3fc!important;
  border:1px solid #29415f!important;
}
.replay-panel div[data-testid="stDateInput"] label,
.replay-panel div[data-testid="stTimeInput"] label,
.replay-panel div[data-testid="stSelectbox"] label{
  color:#aebdd1!important;
  font-size:9px!important;
  font-weight:850!important;
}
.replay-panel div[data-testid="stButton"] button{
  min-height:33px!important;
  background:#f02f35!important;
  border:1px solid #ff5960!important;
  color:#fff!important;
  font-size:10px!important;
  font-weight:950!important;
}
.replay-panel div[data-testid="stSelectbox"]>div>div{
  min-height:33px!important;
  background:#0f1e33!important;
  color:#edf3fc!important;
  border:1px solid #29415f!important;
}
.replay-panel div[data-testid="stSelectbox"] svg,
.replay-panel div[data-testid="stDateInput"] svg,
.replay-panel div[data-testid="stTimeInput"] svg{
  fill:#aebdd1!important;
  color:#aebdd1!important;
}

/* ---------- RESET / GENERIC ---------- */
.reset-wrap div[data-testid="stButton"] button{
  min-height:28px!important;
  background:#102038!important;
  border:1px solid #27415f!important;
  color:#d8e2ef!important;
  font-size:9px!important;
  font-weight:850!important;
}
div[data-testid="stAlert"]{
  background:#132017!important;
  color:#eef4fb!important;
  border:1px solid #294b2d!important;
}

/* ---------- FOOTER ---------- */
.sdl-footer{
  display:flex;
  justify-content:space-between;
  gap:10px;
  border-top:1px solid #1d3049;
  margin-top:9px;
  padding-top:7px;
  color:#71839c;
  font-size:8px!important;
}

/* Desktop is the approved target. Only compact gracefully below it. */
@media(max-width:1200px){
  .block-container{padding-top:46px!important}
  .workspace-cols{display:block}
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================================
# SAFE DISPLAY HELPERS
# ============================================================================

def safe_text(value) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass
    return html.escape(str(value))


def observation_ts(path: str | Path) -> pd.Timestamp:
    """Resolve the exact snapshot timestamp without using file mtime first.

    Current Daywise files use a compact ``YYYY-MM-DD_HHMMSS`` suffix
    (for example ``..._2026-08-28_144503.xlsx``).  The upstream parser
    historically accepted only the hour/minute form, which could make the
    dashboard fall back to filesystem mtime.  The dashboard now recognizes
    the exact compact form first, then delegates to the existing parser.
    """
    path = Path(path)
    stem = path.stem

    compact = re.search(
        r"(?P<date>\d{4}-\d{2}-\d{2})[_-](?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})$",
        stem,
    )
    if compact:
        try:
            return pd.Timestamp(
                f"{compact.group('date')} {compact.group('hour')}:"
                f"{compact.group('minute')}:{compact.group('second')}"
            )
        except Exception:
            pass

    try:
        value = parse_observation_timestamp(path)
        value = pd.to_datetime(value, errors="coerce")
        if pd.notna(value):
            return value
    except Exception:
        pass

    # Last-resort display fallback only. SDL logic never intentionally uses
    # filesystem mtime as the market observation timestamp.
    try:
        return pd.Timestamp.fromtimestamp(path.stat().st_mtime)
    except Exception:
        return pd.NaT


def active_source_root() -> Path:
    """Return the dashboard-selected SDL source root for this app session."""
    value = st.session_state.get("source_root")
    if value:
        return Path(str(value)).expanduser().resolve()
    return Path(
        getattr(
            sdl_pipeline,
            "INTRADAY_SOURCE_ROOT",
            getattr(sdl_config, "INTRADAY_SOURCE_ROOT", ""),
        )
    ).expanduser().resolve()


def apply_source_root(value: str) -> tuple[bool, str]:
    """Apply a dashboard-selected source root without changing SDL logic."""
    candidate = Path(str(value).strip()).expanduser()
    if not str(candidate):
        return False, "Source folder cannot be empty."
    try:
        candidate = candidate.resolve()
    except Exception:
        candidate = candidate.absolute()
    if not candidate.exists() or not candidate.is_dir():
        return False, f"Source folder does not exist or is not a folder: {candidate}"

    # Keep the dashboard's existing source-discovery contract intact.
    # Only runtime configuration is changed; no source files are copied or written.
    sdl_pipeline.INTRADAY_SOURCE_ROOT = candidate
    sdl_config.INTRADAY_SOURCE_ROOT = candidate
    st.session_state["source_root"] = str(candidate)
    return True, str(candidate)


def snapshot_files(day: str | None = None) -> list[Path]:
    # discover_historical_snapshots() resolves its root through the existing
    # pipeline/config module state. Keep those values synchronized with the
    # dashboard-selected session source before discovery.
    root = active_source_root()
    sdl_pipeline.INTRADAY_SOURCE_ROOT = root
    sdl_config.INTRADAY_SOURCE_ROOT = root
    try:
        paths = [Path(p) for p in discover_historical_snapshots(day)]
    except Exception:
        return []
    pairs = []
    for path in paths:
        stamp = observation_ts(path)
        if pd.notna(stamp):
            pairs.append((path, stamp))
    pairs.sort(key=lambda x: (x[1], str(x[0]).lower()))
    return [p for p, _ in pairs]


def frozen_base(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    if df is None or df.empty or "Symbol" not in df.columns:
        return {}
    result: dict[str, dict[str, float]] = {}
    for _, row in df.drop_duplicates("Symbol").iterrows():
        symbol = str(row.get("Symbol", "")).strip().upper()
        open_price = pd.to_numeric(row.get("daily_open_reference"), errors="coerce")
        premium = pd.to_numeric(row.get("opening_straddle_premium"), errors="coerce")
        if symbol and pd.notna(open_price) and pd.notna(premium) and float(premium) > 0:
            result[symbol] = {
                "open_price": float(open_price),
                "opening_straddle_premium": float(premium),
            }
    return result


def candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = build_current_predictions(df, frozen_base(df))
    if out is None:
        return pd.DataFrame()
    out = out.copy()
    if out.empty:
        return out

    # Display timestamp only; decision logic is still supplied by the existing
    # prediction engine.
    if "Symbol" in df.columns and "symbol" in out.columns:
        source = df.copy()
        source["Symbol"] = source["Symbol"].astype(str).str.upper().str.strip()
        if "observation_timestamp" in source.columns:
            source["observation_timestamp"] = pd.to_datetime(
                source["observation_timestamp"], errors="coerce"
            )
            stamp_map = (
                source.groupby("Symbol")["observation_timestamp"]
                .max()
                .to_dict()
            )
            out["observation_timestamp"] = out["symbol"].map(stamp_map)

    return out


def event_first_times() -> dict[str, pd.Timestamp]:
    try:
        events = load_events(EVENT_CSV)
    except Exception:
        return {}
    if events is None or events.empty:
        return {}
    if "symbol" not in events.columns or "observation_timestamp" not in events.columns:
        return {}
    e = events.copy()
    e["symbol"] = e["symbol"].astype(str).str.upper().str.strip()
    e["observation_timestamp"] = pd.to_datetime(
        e["observation_timestamp"], errors="coerce"
    )
    e = e.dropna(subset=["observation_timestamp"])
    if e.empty:
        return {}
    return e.groupby("symbol")["observation_timestamp"].min().to_dict()


def add_first_times(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    first_map = event_first_times()
    out["first_trigger_timestamp"] = out["symbol"].map(first_map)
    return out


def first_seen(row: pd.Series) -> pd.Timestamp:
    for key in (
        "first_trigger_timestamp",
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


def fmt_time(value, full: bool = False) -> str:
    value = pd.to_datetime(value, errors="coerce")
    if pd.isna(value):
        return "—"
    return value.strftime("%d %b %Y, %H:%M:%S" if full else "%H:%M:%S")


def pct(value) -> str:
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        return "—"
    return f"{float(value):+.2f}%"


def logo(symbol) -> str:
    text = str(symbol or "").strip().upper()
    if not text or text == "NAN":
        return '<span class="logo">—</span>'
    return f'<span class="logo" title="{safe_text(text)}">{safe_text(text[:4])}</span>'


def breakout_series(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=bool)
    if "factual_breakout" not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)
    return df["factual_breakout"].fillna(False).astype(bool)


def apply_filters(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    cols = st.columns(4)
    progress_opts = ["All", "25%+", "50%+", "70%+", "75%+", "Breakout"]
    direction_opts = ["All", "Bullish", "Bearish"]
    strength_opts = ["All", "Developing", "Strong", "Supported", "Wait / Conflict"]
    stage_opts = [
        "All",
        "100%+ BREAKOUT",
        "25–<50% EARLY",
        "50–<75%",
        "75–<100% APPROACHING",
    ]

    selections = {}
    with cols[0]:
        st.markdown('<div class="filter-group"><div class="filter-title">PROGRESS ⓘ</div>', unsafe_allow_html=True)
        selections["progress"] = st.radio(
            "Progress",
            progress_opts,
            horizontal=True,
            key=f"{key_prefix}_progress",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with cols[1]:
        st.markdown('<div class="filter-group"><div class="filter-title">DIRECTION ⓘ</div>', unsafe_allow_html=True)
        selections["direction"] = st.radio(
            "Direction",
            direction_opts,
            horizontal=True,
            key=f"{key_prefix}_direction",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with cols[2]:
        st.markdown('<div class="filter-group"><div class="filter-title">STRENGTH ⓘ</div>', unsafe_allow_html=True)
        selections["strength"] = st.radio(
            "Strength",
            strength_opts,
            horizontal=True,
            key=f"{key_prefix}_strength",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with cols[3]:
        st.markdown('<div class="filter-group"><div class="filter-title">STAGE ⓘ</div>', unsafe_allow_html=True)
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
            out.get("direction_label", pd.Series("", index=out.index))
            .astype(str).str.upper()
            .eq(selections["direction"].upper())
        ]

    if selections["strength"] != "All":
        wanted = selections["strength"].upper().split("/")[0].strip()
        out = out[
            out.get("strength_label", pd.Series("", index=out.index))
            .astype(str).str.upper()
            .str.contains(wanted, regex=False, na=False)
        ]

    progress = pd.to_numeric(
        out.get("progress", pd.Series(index=out.index, dtype=float)),
        errors="coerce",
    ).fillna(-1)

    choice = selections["progress"]
    if choice == "25%+":
        out = out[progress >= 25]
    elif choice == "50%+":
        out = out[progress >= 50]
    elif choice == "70%+":
        out = out[progress >= 70]
    elif choice == "75%+":
        out = out[progress >= 75]
    elif choice == "Breakout":
        out = out[breakout_series(out)]

    if selections["stage"] != "All":
        stage = selections["stage"]
        p = pd.to_numeric(
            out.get("progress", pd.Series(index=out.index, dtype=float)),
            errors="coerce",
        )
        if stage == "100%+ BREAKOUT":
            out = out[breakout_series(out)]
        elif stage == "25–<50% EARLY":
            out = out[(p >= 25) & (p < 50)]
        elif stage == "50–<75%":
            out = out[(p >= 50) & (p < 75)]
        elif stage == "75–<100% APPROACHING":
            out = out[(p >= 75) & (p < 100)]

    return out


def badge_class(row: pd.Series) -> str:
    direction = str(row.get("direction_label", "")).upper()
    if direction == "BULLISH":
        return "badge-green"
    if direction == "BEARISH":
        return "badge-red"
    return "badge-amber"


def queue_html(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return '<div style="padding:18px;text-align:center;color:#8293aa;font-size:10px">No stocks match the current filters.</div>'

    rows = []
    for i, (_, row) in enumerate(df.iterrows(), 1):
        price = pd.to_numeric(row.get("signed_price_move_pct"), errors="coerce")
        progress = pd.to_numeric(row.get("progress"), errors="coerce")
        progress = 0.0 if pd.isna(progress) else float(progress)
        strength = pd.to_numeric(row.get("strength"), errors="coerce")
        direction = str(row.get("direction_label", "—"))
        strength_label = str(row.get("strength_label", "—"))
        stage = str(row.get("stage", "—"))
        confirmation = str(row.get("confirmation", "STRONG"))
        breakout = bool(row.get("factual_breakout", False))
        first = first_seen(row)
        updated = pd.to_datetime(row.get("observation_timestamp"), errors="coerce")

        price_class = "up" if pd.notna(price) and price > 0 else "down" if pd.notna(price) and price < 0 else ""
        fill_class = "break" if breakout else ""

        rows.append(
            f'<tr title="First trigger: {fmt_time(first, True)} | Updated: {fmt_time(updated, True)}">'
            f'<td>{i}</td>'
            f'<td><div class="stock-cell">{logo(row.get("symbol"))}<span>{safe_text(str(row.get("symbol", "")).upper())}</span></div></td>'
            f'<td><span class="badge {badge_class(row)}">{safe_text(direction.title())} · {safe_text(strength_label.title())}</span></td>'
            f'<td class="{price_class}">{pct(price)}</td>'
            f'<td><b>{progress:.1f}%</b><span class="rail"><span class="rail-fill {fill_class}" style="width:{min(max(progress,0),100):.0f}%"></span></span></td>'
            f'<td><span class="badge badge-blue">{safe_text(stage)}</span></td>'
            f'<td><span class="badge badge-blue">{safe_text(confirmation)}</span></td>'
            f'<td class="strength">{"—" if pd.isna(strength) else f"{float(strength):.0f}"}</td>'
            f'<td class="breakout">{"YES" if breakout else "—"}</td>'
            f'<td>{fmt_time(first)}</td>'
            f'<td>{fmt_time(updated)}</td>'
            '</tr>'
        )

    return (
        '<div class="queue-wrap"><table class="queue"><thead><tr>'
        '<th style="width:3%">#</th>'
        '<th style="width:13%">STOCK ⓘ</th>'
        '<th style="width:17%">DIRECTION / STRENGTH</th>'
        '<th style="width:8%">MOMENTUM</th>'
        '<th style="width:14%">STRADDLE PROGRESS</th>'
        '<th style="width:13%">STAGE</th>'
        '<th style="width:10%">CONFIRMATION</th>'
        '<th style="width:7%">STRENGTH</th>'
        '<th style="width:6%">BREAKOUT</th>'
        '<th style="width:5%">FIRST</th>'
        '<th style="width:7%">UPDATED</th>'
        '</tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _numeric_from_row(row: pd.Series, names: list[str]):
    for name in names:
        if name in row.index:
            value = pd.to_numeric(row.get(name), errors="coerce")
            if pd.notna(value):
                return float(value)
    return None


def _historical_evidence_summary(events: pd.DataFrame, symbol: str):
    if events is None or events.empty or "symbol" not in events.columns:
        return None
    e = events.copy()
    e["symbol"] = e["symbol"].astype(str).str.upper().str.strip()
    e = e[e["symbol"].eq(str(symbol).upper().strip())]
    if e.empty:
        return None
    price = pd.to_numeric(e.get("price_chg_pct"), errors="coerce").dropna().abs()
    sample = int(len(e))
    significant = int((price >= 1.0).sum()) if not price.empty else 0
    avg_move = float(price.mean()) if not price.empty else None
    availability = min(sample / 10.0, 1.0)
    significance = min(significant / max(sample, 1), 1.0)
    strength = int(round(100 * (0.55 * availability + 0.45 * significance)))
    label = "STRONG" if strength >= 70 else "MODERATE" if strength >= 45 else "LIMITED"
    return {"strength": strength, "label": label, "sample": sample, "significant": significant, "avg_move": avg_move}


def render_cumulative_context(row: pd.Series, current_ts: pd.Timestamp):
    symbol = str(row.get("symbol", "")).upper()
    values = {
        "PRICE CHG": _numeric_from_row(row, ["Price Chg %", "price_chg_pct", "signed_price_move_pct"]),
        "OI CHG": _numeric_from_row(row, ["OI Chg %", "oi_chg_pct"]),
        "IV CHG": _numeric_from_row(row, ["IV Chg %", "iv_chg_pct"]),
        "PCR CHG": _numeric_from_row(row, ["PCR Chg %", "pcr_chg_pct"]),
        "CE OI CHG": _numeric_from_row(row, ["Tot CE OI Chg %", "tot_ce_oi_chg_pct"]),
        "PE OI CHG": _numeric_from_row(row, ["Tot PE OI Chg %", "tot_pe_oi_chg_pct"]),
    }

    def fmt(v):
        return "—" if v is None else f"{v:+.2f}%"

    try:
        events = load_events(EVENT_CSV)
    except Exception:
        events = pd.DataFrame()

    hist = _historical_evidence_summary(events, symbol)
    if hist is None:
        hist_html = (
            '<div class="history-box"><div class="history-head">'
            '<span>HISTORICAL EVIDENCE STRENGTH</span><span>INSUFFICIENT</span>'
            '</div><div class="panel-meta">No sufficient stored historical event sample for this stock.</div></div>'
        )
    else:
        avg = "—" if hist["avg_move"] is None else f'{hist["avg_move"]:.2f}%'
        hist_html = (
            f'<div class="history-box"><div class="history-head">'
            f'<span>HISTORICAL EVIDENCE STRENGTH</span><span>{hist["label"]} · {hist["strength"]}/100</span>'
            f'</div><div class="history-rail"><div class="history-fill" style="width:{hist["strength"]}%"></div></div>'
            f'<div class="panel-meta">Stored events: {hist["sample"]} · Significant moves ≥1%: {hist["significant"]} · Avg absolute move: {avg} · INFORMATION ONLY — NOT A FILTER GATE.</div></div>'
        )

    cards = "".join(
        f'<div class="context-card"><div class="context-label">{safe_text(k)}</div><div class="context-value">{safe_text(fmt(v))}</div></div>'
        for k, v in values.items()
    )
    cards += (
        f'<div class="context-card"><div class="context-label">AS OF</div><div class="context-value">{safe_text(fmt_time(current_ts))}</div></div>'
        f'<div class="context-card"><div class="context-label">DIRECTION</div><div class="context-value">{safe_text(str(row.get("direction_label", "—")).title())}</div></div>'
        f'<div class="context-card"><div class="context-label">STRENGTH</div><div class="context-value">{safe_text(str(row.get("strength_label", "—")).title())}</div></div>'
    )

    return (
        '<details class="context-box" open>'
        '<summary class="context-head"><span>MARKET CONTEXT</span><span>▼</span></summary>'
        f'<div class="context-grid">{cards}</div>'
        '</details>'
        + hist_html
        + '<details class="context-box"><summary class="context-head"><span>NEWS / RESULT / IMPACT</span><span>▶</span></summary>'
        '<div class="panel-meta">External news/result feeds are not connected in this bundle. No synthetic context is injected into SDL decisions.</div></details>'
    )


def detail_panel(df: pd.DataFrame, key: str) -> None:
    if df is None or df.empty:
        st.markdown(
            '<div class="detail-body"><div class="panel-meta">No selected decision.</div></div>',
            unsafe_allow_html=True,
        )
        return

    symbols = [str(x).upper() for x in df["symbol"].dropna().astype(str).tolist()]
    if not symbols:
        st.markdown(
            '<div class="detail-body"><div class="panel-meta">No selected decision.</div></div>',
            unsafe_allow_html=True,
        )
        return

    default = st.session_state.get(f"{key}_symbol")
    if default not in symbols:
        default = symbols[0]
        st.session_state[f"{key}_symbol"] = default

    symbol = st.selectbox(
        "Selected decision",
        symbols,
        index=symbols.index(default),
        key=f"{key}_symbol",
        label_visibility="collapsed",
    )
    row = df[df["symbol"].astype(str).str.upper().eq(symbol)].iloc[0]

    direction = str(row.get("direction_label", "—")).upper()
    strength_label = str(row.get("strength_label", "—")).upper()
    progress = pd.to_numeric(row.get("progress"), errors="coerce")
    progress = 0.0 if pd.isna(progress) else float(progress)
    strength = pd.to_numeric(row.get("strength"), errors="coerce")
    stage = str(row.get("stage", "—"))
    momentum = pd.to_numeric(row.get("signed_price_move_pct"), errors="coerce")
    first = first_seen(row)
    updated = pd.to_datetime(row.get("observation_timestamp"), errors="coerce")

    st.markdown(
        f'<div class="detail-hero">'
        f'<div><div class="detail-symbol">{logo(symbol)} {safe_text(symbol)}</div>'
        f'<div class="detail-sub">First seen: {fmt_time(first, True)} · Updated: {fmt_time(updated, True)}</div></div>'
        f'<span class="badge {badge_class(row)}">{safe_text(direction.title())} · {safe_text(strength_label.title())}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    next_stage = "Breakout" if progress >= 75 else "75%" if progress >= 50 else "50%"

    st.markdown(
        f'<div class="detail-grid">'
        f'<div class="detail-card"><div class="detail-label">STRENGTH</div><div class="detail-value">{"—" if pd.isna(strength) else f"{float(strength):.0f}"}</div><div class="detail-foot">{safe_text(strength_label.title())}</div></div>'
        f'<div class="detail-card"><div class="detail-label">STRADDLE PROGRESS</div><div class="detail-value">{progress:.1f}%</div><div class="detail-foot">Next: {safe_text(next_stage)}</div></div>'
        f'<div class="detail-card"><div class="detail-label">STAGE</div><div class="detail-value">{safe_text(stage)}</div><div class="detail-foot">Existing SDL stage</div></div>'
        f'<div class="detail-card"><div class="detail-label">MOMENTUM</div><div class="detail-value">{pct(momentum)}</div><div class="detail-foot">As of {fmt_time(updated)}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    factors = row.get("factors", [])
    factor_rows = []
    if isinstance(factors, list):
        for factor in factors:
            label = getattr(factor, "label", None)
            state = str(getattr(factor, "state", "NEUTRAL"))
            cls = "support" if state == "SUPPORT" else "contradict" if state == "CONTRADICT" else "neutral"
            factor_rows.append(
                f'<div class="factor-row"><span>{safe_text(label or "Factor")}</span><b class="{cls}">{safe_text(state)}</b></div>'
            )

    st.markdown(
        f'<div class="process-box"><div class="detail-label">STRADDLE PROCESS</div>'
        f'<div class="process-value">{progress:.1f}%</div>'
        f'<div class="process-rail"><div class="process-fill" style="width:{min(max(progress,0),100):.0f}%"></div></div>'
        f'<div class="process-scale"><span>25%</span><span>50%</span><span>75%</span><span>100% BREAKOUT</span></div></div>'
        f'<div class="factor-box">'
        + ("".join(factor_rows) if factor_rows else '<div class="factor-row"><span>Evidence factors</span><b class="neutral">—</b></div>')
        + "</div>",
        unsafe_allow_html=True,
    )

    try:
        labels = factor_labels(row.to_dict())
    except Exception:
        labels = []
    if labels:
        st.caption(" · ".join(str(x) for x in labels))

    # Raw input evidence is displayed for operator verification only.
    # It does not create a new score or alter the existing SDL decision.
    evidence_specs = [
        ("PRICE CHG %", ["Price Chg %", "price_chg_pct"]),
        ("OI CHG %", ["OI Chg %", "oi_chg_pct"]),
        ("IV CHG %", ["IV Chg %", "iv_chg_pct"]),
        ("PCR CHG %", ["PCR Chg %", "pcr_chg_pct"]),
        ("CE OI CHG %", ["Tot CE OI Chg %", "tot_ce_oi_chg_pct"]),
        ("PE OI CHG %", ["Tot PE OI Chg %", "tot_pe_oi_chg_pct"]),
    ]
    evidence_cards = []
    for label, names in evidence_specs:
        value = None
        for name in names:
            if name in row.index:
                value = row.get(name)
                if value is not None and not (isinstance(value, float) and pd.isna(value)):
                    break
        if value is None or (isinstance(value, float) and pd.isna(value)):
            display_value = "—"
        else:
            try:
                display_value = f"{float(value):+.2f}%"
            except Exception:
                display_value = str(value)
        evidence_cards.append(
            f'<div class="detail-card"><div class="detail-label">{safe_text(label)}</div>'
            f'<div class="detail-value" style="font-size:16px!important">{safe_text(display_value)}</div>'
            f'<div class="detail-foot">Source snapshot field</div></div>'
        )
    st.markdown(
        '<div class="detail-label" style="margin-top:8px">INPUT EVIDENCE · VERIFICATION</div>'
        '<div class="detail-grid">' + "".join(evidence_cards) + '</div>'
        '<div class="panel-meta" style="margin-top:5px">Displayed from the existing decision record; no additional scoring is performed.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        render_cumulative_context(
            row,
            updated if pd.notna(updated) else pd.Timestamp.now(),
        ),
        unsafe_allow_html=True,
    )


def planned_panel(title: str, copy: str) -> None:
    st.markdown(
        f'<div class="planned-panel">'
        f'<div class="planned-title">{safe_text(title)}</div>'
        f'<div class="planned-status">Coming soon</div>'
        f'<div class="planned-copy">{safe_text(copy)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ============================================================================
# SNAPSHOT PROCESSING — EXISTING ENGINE ONLY
# ============================================================================

def run_snapshot(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()

    try:
        result = process_snapshot(path, observation_ts(path))
        frames = (
            [x for x in result if isinstance(x, pd.DataFrame)]
            if isinstance(result, tuple)
            else [result]
        )
        # Existing deployment convention: the decision-bearing source frame
        # is the second dataframe when process_snapshot returns multiple frames.
        source = frames[1] if len(frames) > 1 else frames[0] if frames else pd.DataFrame()
        return add_first_times(candidates(source))
    except Exception as exc:
        st.session_state["sdl_live_error"] = f"{type(exc).__name__}: {exc}"
        return pd.DataFrame()


def latest_snapshot() -> tuple[Path | None, pd.Timestamp]:
    files = snapshot_files()
    if not files:
        return None, pd.NaT
    path = files[-1]
    return path, observation_ts(path)


# ============================================================================
# PERSISTED DASHBOARD PRESENTATION SETTINGS
# ============================================================================
# Settings are dashboard-only and never alter SDL decision/scoring logic.
# The file is created locally beside this dashboard when an operator applies
# a setting. It contains only presentation/runtime preferences.
DASHBOARD_SETTINGS_FILE = Path(__file__).resolve().parent / ".sdl_dashboard_settings.json"


def _load_dashboard_settings() -> dict:
    try:
        if not DASHBOARD_SETTINGS_FILE.exists():
            return {}
        raw = json.loads(DASHBOARD_SETTINGS_FILE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_dashboard_settings(**values) -> None:
    payload = {}
    try:
        existing = _load_dashboard_settings()
        if isinstance(existing, dict):
            payload.update(existing)
        for key, value in values.items():
            if key == "source_root":
                payload[key] = str(value)
            elif key == "refresh_seconds":
                payload[key] = int(value)
            elif key == "auto_refresh":
                payload[key] = bool(value)
        DASHBOARD_SETTINGS_FILE.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception:
        # Settings persistence is best-effort and must never block the dashboard.
        pass


def _restore_persisted_settings() -> dict:
    saved = _load_dashboard_settings()
    restored = {}
    source = saved.get("source_root")
    if source:
        candidate = Path(str(source)).expanduser()
        try:
            candidate = candidate.resolve()
        except Exception:
            candidate = candidate.absolute()
        if candidate.exists() and candidate.is_dir():
            restored["source_root"] = str(candidate)

    try:
        refresh = int(saved.get("refresh_seconds", 300))
        if refresh in (180, 300, 420, 600, 900):
            restored["refresh_seconds"] = refresh
    except Exception:
        pass

    if isinstance(saved.get("auto_refresh"), bool):
        restored["auto_refresh"] = bool(saved["auto_refresh"])
    return restored


# ============================================================================
# SESSION STATE
# ============================================================================

_persisted = _restore_persisted_settings()
defaults = {
    "page": "Decision Board",
    "auto_refresh": _persisted.get("auto_refresh", False),
    # Stored internally as seconds; displayed to the operator as minutes.
    "refresh_seconds": _persisted.get("refresh_seconds", 300),
    "queue_limit": 12,
    "replay_path": None,
    "source_root": _persisted.get(
        "source_root",
        str(getattr(sdl_pipeline, "INTRADAY_SOURCE_ROOT", getattr(sdl_config, "INTRADAY_SOURCE_ROOT", ""))),
    ),
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# One-time migration from the previous preview's 5/10/15/30/60-second values.
_refresh_value = int(st.session_state.get("refresh_seconds", 300))
if _refresh_value in (5, 10, 15, 30, 60):
    st.session_state["refresh_seconds"] = _refresh_value * 60
elif _refresh_value not in (180, 300, 420, 600, 900):
    st.session_state["refresh_seconds"] = 300

# Ensure the selected source is reflected in the existing pipeline/config runtime.
try:
    _initial_source = Path(str(st.session_state.get("source_root", ""))).expanduser().resolve()
    if _initial_source.exists() and _initial_source.is_dir():
        sdl_pipeline.INTRADAY_SOURCE_ROOT = _initial_source
        sdl_config.INTRADAY_SOURCE_ROOT = _initial_source
except Exception:
    pass


# ============================================================================
# APPROVED HEADER — NATIVE STREAMLIT CONTROLS, NO HTML WRAPPER
# ============================================================================

live_path_for_header, live_ts_for_header = latest_snapshot()
clock_now = pd.Timestamp.now()

# The approved reference contains a reserved upper header band. It is now
# used as a compact operational strip rather than remaining visually empty.
utility_source = active_source_root()
utility_source_text = str(utility_source)
utility_snapshot = live_ts_for_header
utility_exists = live_path_for_header is not None
utility_age = ""
if pd.notna(utility_snapshot):
    age_seconds = max(0, int((pd.Timestamp.now() - utility_snapshot).total_seconds()))
    if age_seconds < 60:
        utility_age = f"{age_seconds}s ago"
    elif age_seconds < 3600:
        utility_age = f"{age_seconds // 60}m ago"
    else:
        utility_age = f"{age_seconds // 3600}h ago"
india_now = pd.Timestamp.now(tz="Asia/Kolkata")
market_open = india_now.hour > 9 or (india_now.hour == 9 and india_now.minute >= 15)
market_close = india_now.hour < 15 or (india_now.hour == 15 and india_now.minute <= 30)
session_label = "OPEN" if market_open and market_close else "CLOSED"

st.markdown(
    f'''
    <div class="utility-strip">
      <div style="display:grid;grid-template-columns:2.35fr 1.35fr .85fr 1.15fr;gap:0">
        <div class="utility-cell">
          <div class="utility-label">ACTIVE SDL SOURCE</div>
          <div class="utility-value">{safe_text(utility_source_text)}</div>
          <div class="utility-note">Dashboard runtime source · read only</div>
        </div>
        <div class="utility-cell">
          <div class="utility-label">LATEST SNAPSHOT</div>
          <div class="utility-value cyan">{safe_text(fmt_time(utility_snapshot, True))}</div>
          <div class="utility-note">{safe_text(utility_age) if utility_age else "No completed snapshot"}</div>
        </div>
        <div class="utility-cell">
          <div class="utility-label">MARKET SESSION</div>
          <div class="utility-value {"green" if session_label == "OPEN" else "amber"}">{session_label}</div>
          <div class="utility-note">NSE cash hours</div>
        </div>
        <div class="utility-cell">
          <div class="utility-label">DECISION MODE</div>
          <div class="utility-value">FACTS ONLY</div>
          <div class="utility-note">Existing SDL engine</div>
        </div>
      </div>
    </div>
    ''',
    unsafe_allow_html=True,
)

h1, h2, h3 = st.columns([2.0, 3.55, 3.65], gap="small")

with h1:
    st.markdown(
        '<div class="sdl-brand">◉ NTIS SDL</div>'
        '<div class="sdl-sub">INTRADAY DECISION CENTRE · STRADDLE BREAKOUT</div>',
        unsafe_allow_html=True,
    )

with h2:
    n1, n2, n3 = st.columns([1.0, 1.25, .85], gap="small")
    with n1:
        if st.button(
            "▣ Decision Board",
            type="primary" if st.session_state["page"] == "Decision Board" else "secondary",
            use_container_width=True,
            key="nav_decision",
        ):
            st.session_state["page"] = "Decision Board"
            st.rerun()
    with n2:
        if st.button(
            "▤ Historical Evidence",
            type="primary" if st.session_state["page"] == "Historical Evidence" else "secondary",
            use_container_width=True,
            key="nav_history",
        ):
            st.session_state["page"] = "Historical Evidence"
            st.rerun()
    with n3:
        if st.button(
            "⚙ Settings",
            type="primary" if st.session_state["page"] == "Settings" else "secondary",
            use_container_width=True,
            key="nav_settings",
        ):
            st.session_state["page"] = "Settings"
            st.rerun()

with h3:
    q1, q2, q3, q4, q5 = st.columns([.62, 1.0, .72, 1.08, .72], gap="small")
    with q1:
        st.markdown('<div style="padding-top:4px"><span class="live-pill"><i></i>LIVE</span></div>', unsafe_allow_html=True)
    with q2:
        st.markdown(
            f'<div class="clock-box"><b>{clock_now.strftime("%I:%M:%S %p")}</b>'
            f'<small>{clock_now.strftime("%d %b %Y")}</small></div>',
            unsafe_allow_html=True,
        )
    with q3:
        if st.button("⟳ Refresh", use_container_width=True, key="header_refresh"):
            st.rerun()
    with q4:
        st.session_state["auto_refresh"] = st.checkbox(
            "Auto Refresh",
            value=bool(st.session_state["auto_refresh"]),
            key="auto_refresh_checkbox",
        )
        _save_dashboard_settings(auto_refresh=st.session_state["auto_refresh"])
    with q5:
        st.session_state["refresh_seconds"] = st.selectbox(
            "Interval",
            [180, 300, 420, 600, 900],
            index=[180, 300, 420, 600, 900].index(int(st.session_state["refresh_seconds"])),
            key="refresh_seconds_select",
            format_func=lambda x: f"{int(x // 60)} min",
            label_visibility="collapsed",
        )
        _save_dashboard_settings(refresh_seconds=st.session_state["refresh_seconds"])


# ============================================================================
# DECISION BOARD
# ============================================================================

if st.session_state["page"] == "Decision Board":

    # Fixed presentation filters live outside the fragment so auto refresh
    # cannot reset them. The fragment reads their session state on each cycle.
    st.markdown(
        '<div class="section-bar">✦ FOUR INDEPENDENT TRADER DIMENSIONS · FILTERING NEVER CHANGES THE UNDERLYING SDL DECISION SCORE</div>',
        unsafe_allow_html=True,
    )

    if st.button("↻ Reset Filters", key="reset_filters"):
        for key in ("board_progress", "board_direction", "board_strength", "board_stage"):
            st.session_state[key] = "All"
        st.session_state["queue_limit"] = 12
        st.rerun()

    # Render filters as native Streamlit controls.  Native controls are kept
    # outside auto-refresh so their selections persist while live data changes.
    filter_cols = st.columns(4)
    filter_specs = [
        ("PROGRESS", ["All", "25%+", "50%+", "70%+", "75%+", "Breakout"], "board_progress"),
        ("DIRECTION", ["All", "Bullish", "Bearish"], "board_direction"),
        ("STRENGTH", ["All", "Developing", "Strong", "Supported", "Wait / Conflict"], "board_strength"),
        ("STAGE", ["All", "100%+ BREAKOUT", "25–<50% EARLY", "50–<75%", "75–<100% APPROACHING"], "board_stage"),
    ]
    for col, (title, options, key) in zip(filter_cols, filter_specs):
        with col:
            st.markdown(f'<div class="filter-title">{title} ⓘ</div>', unsafe_allow_html=True)
            st.radio(
                title,
                options,
                horizontal=True,
                key=key,
                label_visibility="collapsed",
            )

    def render_live_region() -> None:
        current_path, current_ts = latest_snapshot()
        live = run_snapshot(current_path)

        first_alert = pd.NaT
        if not live.empty:
            values = [first_seen(row) for _, row in live.iterrows()]
            values = [x for x in values if pd.notna(x)]
            first_alert = min(values) if values else pd.NaT

        st.markdown(
            f'<div class="status-strip">'
            f'<div class="status-cell"><div class="status-label">FIRST ALERT ⓘ</div>'
            f'<div class="status-value">{fmt_time(first_alert, True)}</div>'
            f'<div class="status-foot">Data updated {fmt_time(current_ts)}</div></div>'
            f'<div class="status-cell" style="text-align:right"><div class="status-label">DATA UPDATED ⓘ</div>'
            f'<div class="status-value green">{fmt_time(current_ts, True)}</div>'
            f'<div class="status-foot">Latest completed snapshot</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if current_path is not None:
            st.markdown(
                f'<div class="live-state">Live source: <b>{safe_text(current_path.name)}</b> · '
                f'Snapshot: <b>{fmt_time(current_ts, True)}</b></div>',
                unsafe_allow_html=True,
            )

        if st.session_state.get("sdl_live_error"):
            st.warning(st.session_state["sdl_live_error"])

        # Six KPI cards are deliberately native Streamlit columns. This is the
        # fix for the vertical stacking seen in the 28-Aug screenshot.
        qualified = len(live)
        bullish = int(live.get("direction_label", pd.Series(dtype=str)).astype(str).str.upper().eq("BULLISH").sum()) if not live.empty else 0
        bearish = int(live.get("direction_label", pd.Series(dtype=str)).astype(str).str.upper().eq("BEARISH").sum()) if not live.empty else 0
        strong = int(live.get("strength_label", pd.Series(dtype=str)).astype(str).str.upper().eq("STRONG").sum()) if not live.empty else 0
        breakout = int(breakout_series(live).sum()) if not live.empty else 0

        kpi_first = fmt_time(first_alert)
        kpis = [
            ("◉", "QUALIFIED", qualified, "", ""),
            ("◆", "BULLISH", bullish, "green", ""),
            ("◆", "BEARISH", bearish, "red", ""),
            ("★", "STRONG", strong, "purple", ""),
            ("◎", "BREAKOUT", breakout, "amber", ""),
            ("♢", "FIRST ALERT", kpi_first, "cyan", ""),
        ]

        kcols = st.columns(6, gap="small")
        for col, (icon, label, value, cls, _) in zip(kcols, kpis):
            with col:
                st.markdown(
                    f'<div class="kpi-card {cls}"><div class="kpi-icon">{icon}</div>'
                    f'<div class="kpi-label">{label}</div>'
                    f'<div class="kpi-value">{safe_text(value)}</div>'
                    f'<div class="kpi-foot">Data updated {fmt_time(current_ts)}</div></div>',
                    unsafe_allow_html=True,
                )

        # Apply only the already-qualified dataframe as a presentation filter.
        filtered = live.copy()
        direction_choice = st.session_state.get("board_direction", "All")
        strength_choice = st.session_state.get("board_strength", "All")
        progress_choice = st.session_state.get("board_progress", "All")
        stage_choice = st.session_state.get("board_stage", "All")

        if direction_choice != "All":
            filtered = filtered[
                filtered.get("direction_label", pd.Series("", index=filtered.index))
                .astype(str).str.upper().eq(direction_choice.upper())
            ]

        if strength_choice != "All":
            wanted = strength_choice.upper().split("/")[0].strip()
            filtered = filtered[
                filtered.get("strength_label", pd.Series("", index=filtered.index))
                .astype(str).str.upper().str.contains(wanted, regex=False, na=False)
            ]

        progress = pd.to_numeric(
            filtered.get("progress", pd.Series(index=filtered.index, dtype=float)),
            errors="coerce",
        ).fillna(-1)

        if progress_choice == "25%+":
            filtered = filtered[progress >= 25]
        elif progress_choice == "50%+":
            filtered = filtered[progress >= 50]
        elif progress_choice == "70%+":
            filtered = filtered[progress >= 70]
        elif progress_choice == "75%+":
            filtered = filtered[progress >= 75]
        elif progress_choice == "Breakout":
            filtered = filtered[breakout_series(filtered)]

        if stage_choice != "All":
            p = pd.to_numeric(
                filtered.get("progress", pd.Series(index=filtered.index, dtype=float)),
                errors="coerce",
            )
            if stage_choice == "100%+ BREAKOUT":
                filtered = filtered[breakout_series(filtered)]
            elif stage_choice == "25–<50% EARLY":
                filtered = filtered[(p >= 25) & (p < 50)]
            elif stage_choice == "50–<75%":
                filtered = filtered[(p >= 50) & (p < 75)]
            elif stage_choice == "75–<100% APPROACHING":
                filtered = filtered[(p >= 75) & (p < 100)]

        st.markdown(
            f'<div class="panel-meta" style="margin:1px 2px 7px">'
            f'{len(filtered)} matching stock(s) · filtering never changes the underlying SDL decision score.</div>',
            unsafe_allow_html=True,
        )

        # Priority Radar: controls are retained above the cards and the cards
        # update with the live fragment without rebuilding the rest of the page.
        st.markdown(
            '<div class="section-bar">PRIORITY RADAR · INDEPENDENT FILTER</div>',
            unsafe_allow_html=True,
        )

        # Radar controls are rendered using persistent native radios.
        rcols = st.columns([2.1, 1.2, 4.7], gap="small")
        with rcols[0]:
            st.markdown('<div class="radar-title">PROGRESS</div>', unsafe_allow_html=True)
            radar_progress = st.radio(
                "Radar Progress",
                ["All", "25%+", "50%+", "70%+", "75%+", "Breakout"],
                horizontal=True,
                key="radar_progress",
                label_visibility="collapsed",
            )
        with rcols[1]:
            st.markdown('<div class="radar-title">STRENGTH</div>', unsafe_allow_html=True)
            radar_strength = st.radio(
                "Radar Strength",
                ["All", "Strong", "Developing"],
                horizontal=True,
                key="radar_strength",
                label_visibility="collapsed",
            )
        with rcols[2]:
            radar = filtered.copy()
            rp = pd.to_numeric(
                radar.get("progress", pd.Series(index=radar.index, dtype=float)),
                errors="coerce",
            ).fillna(-1)
            if radar_progress == "25%+":
                radar = radar[rp >= 25]
            elif radar_progress == "50%+":
                radar = radar[rp >= 50]
            elif radar_progress == "70%+":
                radar = radar[rp >= 70]
            elif radar_progress == "75%+":
                radar = radar[rp >= 75]
            elif radar_progress == "Breakout":
                radar = radar[breakout_series(radar)]
            if radar_strength != "All":
                radar = radar[
                    radar.get("strength_label", pd.Series("", index=radar.index))
                    .astype(str).str.upper().str.contains(radar_strength.upper(), regex=False, na=False)
                ]

            radar = radar.sort_values(
                "progress",
                ascending=False,
                na_position="last",
            ).head(5)

            card_cols = st.columns(5, gap="small")
            for idx in range(5):
                with card_cols[idx]:
                    if idx < len(radar):
                        row = radar.iloc[idx]
                        sym = str(row.get("symbol", "—")).upper()
                        d = str(row.get("direction_label", "—")).title()
                        s = str(row.get("strength_label", "—")).title()
                        p = pd.to_numeric(row.get("progress"), errors="coerce")
                        p = 0 if pd.isna(p) else float(p)
                        stage = str(row.get("stage", "—"))
                        st.markdown(
                            f'<div class="radar-card">'
                            f'<div class="radar-symbol">{safe_text(sym)}</div>'
                            f'<div class="radar-meta">{safe_text(d)} · {safe_text(s)}</div>'
                            f'<div class="radar-meta">{safe_text(stage)}</div>'
                            f'<div class="radar-progress">{p:.1f}%</div>'
                            f'<div class="radar-first">First: {fmt_time(first_seen(row))}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            '<div class="radar-card"><div class="radar-meta">No additional qualified decision</div></div>',
                            unsafe_allow_html=True,
                        )

        # Main approved three-column workspace.
        qcol, dcol, ncol = st.columns([2.25, 1.05, .82], gap="small")

        with qcol:
            limit = int(st.session_state.get("queue_limit", 12))
            queue_view = filtered.head(limit)

            st.markdown(
                f'<div class="workspace-panel"><div class="panel-head">'
                f'<div class="panel-title">LIVE QUEUE</div>'
                f'<div class="panel-meta">As of {fmt_time(current_ts, True)} · FIRST TIME is immutable · UPDATED = snapshot time · {len(filtered)} visible</div>'
                f'</div>{queue_html(queue_view)}</div>',
                unsafe_allow_html=True,
            )

            st.markdown('<div class="view-more-row">', unsafe_allow_html=True)
            if len(filtered) > limit:
                if st.button("View More ⌄", key="view_more_queue", use_container_width=True):
                    st.session_state["queue_limit"] = min(limit + 12, len(filtered))
                    st.rerun()
            elif limit > 12 and len(filtered) <= limit:
                if st.button("View Less ⌃", key="view_less_queue", use_container_width=True):
                    st.session_state["queue_limit"] = 12
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with dcol:
            detail_open = bool(st.session_state.get("live_detail_open", True))
            detail_label = "▼ STOCK DETAIL" if detail_open else "▶ STOCK DETAIL"
            if st.button(
                f"{detail_label}  ·  Selected decision · click to {'collapse' if detail_open else 'expand'}",
                key="live_detail_toggle",
                use_container_width=True,
            ):
                st.session_state["live_detail_open"] = not detail_open
                st.rerun()

            if detail_open:
                st.markdown(
                    '<div class="workspace-panel"><div class="panel-head">'
                    '<div class="panel-title">SELECTED DECISION</div></div>',
                    unsafe_allow_html=True,
                )
                detail_panel(filtered, "live_detail")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div class="workspace-panel"><div class="panel-meta" style="padding:11px">'
                    'Stock detail collapsed.</div></div>',
                    unsafe_allow_html=True,
                )

        with ncol:
            planned_panel("LATEST NEWS (PLANNED)", "Real-time stock related news will appear here.")
            planned_panel("LATEST RESULT (PLANNED)", "Latest results & earnings updates will appear here.")
            planned_panel("IMPACT ANALYSIS (PLANNED)", "AI-driven impact analysis of news & results will appear here.")

    # Only the live Decision Board body is auto-refreshed.
    if hasattr(st, "fragment"):
        @st.fragment(run_every=(int(st.session_state["refresh_seconds"]) if st.session_state["auto_refresh"] else None))
        def live_fragment():
            render_live_region()
        live_fragment()
    else:
        render_live_region()

    # ------------------------------------------------------------------------
    # REPLAY — deliberately outside live fragment
    # ------------------------------------------------------------------------
    st.markdown(
        '<div class="section-bar">⌄ INTRADAY REPLAY · SAME PAGE · LIVE STATE REMAINS UNCHANGED</div>'
        '<div class="replay-note">Replay loads an existing completed snapshot only. Later observations cannot upgrade that replay result.</div>',
        unsafe_allow_html=True,
    )

    all_files = snapshot_files()
    replay_dates = sorted(
        {observation_ts(p).date() for p in all_files if pd.notna(observation_ts(p))},
        reverse=True,
    )

    if replay_dates:
        if "replay_day" not in st.session_state or st.session_state["replay_day"] not in replay_dates:
            st.session_state["replay_day"] = replay_dates[0]

        r1, r2, r3 = st.columns([1.0, 1.0, 1.1], gap="small")
        with r1:
            replay_day = st.date_input(
                "Trading day",
                value=st.session_state["replay_day"],
                key="replay_day_input",
            )
            st.session_state["replay_day"] = replay_day

        day_files = [p for p in all_files if observation_ts(p).date() == replay_day]
        day_files.sort(key=observation_ts)

        with r2:
            if day_files:
                labels = [fmt_time(observation_ts(p)) for p in day_files]
                selected_label = st.selectbox(
                    "Snapshot time",
                    labels,
                    index=max(0, len(labels) - 1),
                    key="replay_snapshot_label",
                )
                selected = day_files[labels.index(selected_label)]
            else:
                selected = None
                st.selectbox(
                    "Snapshot time",
                    ["No snapshots available"],
                    disabled=True,
                    key="replay_snapshot_empty",
                )

        with r3:
            if st.button(
                "Load Replay",
                type="primary",
                use_container_width=True,
                key="load_replay",
                disabled=selected is None,
            ):
                st.session_state["replay_path"] = str(selected) if selected is not None else None
                st.session_state.pop("replay_df", None)
                st.rerun()

        replay_path = Path(st.session_state["replay_path"]) if st.session_state.get("replay_path") else None

        if replay_path is not None and replay_path.exists():
            replay_ts = observation_ts(replay_path)
            replay_df = st.session_state.get("replay_df")
            if not isinstance(replay_df, pd.DataFrame):
                replay_df = run_snapshot(replay_path)
                st.session_state["replay_df"] = replay_df

            st.markdown(
                f'<div class="replay-note"><b>Replay boundary:</b> {fmt_time(replay_ts, True)} · '
                f'<b>Live snapshot remains:</b> {fmt_time(live_ts_for_header, True)} · '
                'Later observations cannot upgrade this result.</div>',
                unsafe_allow_html=True,
            )

            replay_visible = replay_df.copy() if isinstance(replay_df, pd.DataFrame) else pd.DataFrame()
            if not replay_visible.empty:
                st.markdown(
                    '<div class="filter-caption">Replay filters are independent of Live filters and apply only to the selected completed snapshot.</div>',
                    unsafe_allow_html=True,
                )
                if st.button("↻ Reset Replay Filters", key="reset_replay_filters"):
                    for replay_key in (
                        "replay_progress",
                        "replay_direction",
                        "replay_strength",
                        "replay_stage",
                    ):
                        st.session_state[replay_key] = "All"
                    st.session_state["replay_limit"] = 12
                    st.rerun()

                replay_visible = apply_filters(replay_visible, "replay")

            if not replay_visible.empty:
                st.markdown(
                    f'<div class="panel-meta">{len(replay_visible)} qualified decision(s) in selected replay snapshot.</div>',
                    unsafe_allow_html=True,
                )
                replay_limit = min(int(st.session_state.get("replay_limit", 12)), len(replay_visible))
                st.markdown(queue_html(replay_visible.head(replay_limit)), unsafe_allow_html=True)
                if len(replay_visible) > replay_limit:
                    if st.button("View More ⌄", key="replay_view_more", use_container_width=True):
                        st.session_state["replay_limit"] = min(replay_limit + 12, len(replay_visible))
                        st.rerun()
                elif int(st.session_state.get("replay_limit", 12)) > 12:
                    if st.button("View Less ⌃", key="replay_view_less", use_container_width=True):
                        st.session_state["replay_limit"] = 12
                        st.rerun()
            else:
                st.markdown(
                    '<div class="replay-note">No qualified decisions are present at this exact replay boundary.</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="replay-note">Select a trading day and snapshot time, then Load Replay.</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div class="replay-note">No historical snapshots are available.</div>', unsafe_allow_html=True)

    
# ============================================================================
# HISTORICAL EVIDENCE
# ============================================================================

elif st.session_state["page"] == "Historical Evidence":
    st.markdown('<div class="section-bar">HISTORICAL EVIDENCE</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="workspace-panel" style="padding:11px">'
        '<div class="panel-meta">Factual historical evidence only. Historical outcomes never feed information backward into Live or Replay.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    # Ensure the latest completed source snapshot has had the opportunity to
    # persist any newly detected factual breakout events before evidence is read.
    # This uses the existing SDL processor; it does not change scoring logic.
    latest_evidence_path, latest_evidence_ts = latest_snapshot()
    if latest_evidence_path is not None:
        run_snapshot(latest_evidence_path)

    try:
        events = load_events(EVENT_CSV)
    except Exception as exc:
        events = pd.DataFrame()
        st.warning(f"Historical evidence could not be loaded: {type(exc).__name__}: {exc}")

    if events is None or events.empty:
        st.info("No historical SDL evidence records are available.")
    else:
        events = events.copy()
        if "observation_timestamp" in events.columns:
            events["observation_timestamp"] = pd.to_datetime(
                events["observation_timestamp"], errors="coerce"
            )
            events = events.sort_values("observation_timestamp", ascending=False)

        latest_event_ts = pd.NaT
        if "observation_timestamp" in events.columns:
            latest_event_ts = events["observation_timestamp"].dropna().max()
        st.markdown(
            f'<div class="panel-meta">Latest completed source snapshot: {fmt_time(latest_evidence_ts, True)} · '
            f'Latest stored breakout evidence: {fmt_time(latest_event_ts, True)} · '
            f'Event store: {safe_text(str(EVENT_CSV))}</div>',
            unsafe_allow_html=True,
        )

        keep = [
            c for c in [
                "observation_timestamp",
                "symbol",
                "direction",
                "price_chg_pct",
                "breakout_distance",
                "strength",
            ]
            if c in events.columns
        ]
        if keep:
            display = events[keep].copy()
            display["observation_timestamp"] = display["observation_timestamp"].dt.strftime("%d %b %Y, %H:%M:%S")
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.dataframe(events, use_container_width=True, hide_index=True)


# ============================================================================
# SETTINGS
# ============================================================================

else:
    st.markdown('<div class="section-bar">SETTINGS</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="workspace-panel" style="padding:12px">'
        '<div class="panel-title">Presentation controls only</div>'
        '<div class="panel-meta">Existing SDL decision and stock-selection logic is not changed by dashboard settings. '
        'SDL/app.py remains untouched.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.session_state["auto_refresh"] = st.checkbox(
        "Auto Refresh",
        value=bool(st.session_state["auto_refresh"]),
        key="settings_auto_refresh",
    )
    st.session_state["refresh_seconds"] = st.selectbox(
        "Refresh interval",
        [180, 300, 420, 600, 900],
        index=[180, 300, 420, 600, 900].index(int(st.session_state["refresh_seconds"])),
        key="settings_refresh_interval",
        format_func=lambda x: f"{int(x // 60)} min",
    )
    _save_dashboard_settings(
        auto_refresh=st.session_state["auto_refresh"],
        refresh_seconds=st.session_state["refresh_seconds"],
    )

    current_root = active_source_root()
    source_text = st.text_input(
        "Active SDL source data folder",
        value=str(current_root),
        key="settings_source_root",
        help="Dashboard-only runtime source location. No source files are copied or modified.",
    )
    if st.button("Apply source folder", type="primary", key="apply_source_folder"):
        ok, message = apply_source_root(source_text)
        if ok:
            _save_dashboard_settings(source_root=active_source_root())
            st.success(f"Source folder applied: {message}")
            st.rerun()
        else:
            st.error(message)

    st.caption(
        f"Configured SDL source root: {active_source_root()}"
    )

    st.markdown(
        '<div class="section-bar">SOURCE SNAPSHOT PROCESSING</div>',
        unsafe_allow_html=True,
    )
    settings_files = snapshot_files()
    if settings_files:
        settings_labels = [f"{fmt_time(observation_ts(p), True)} · {p.name}" for p in settings_files]
        current_setting_path = st.session_state.get("settings_snapshot_path")
        if current_setting_path not in [str(p) for p in settings_files]:
            current_setting_path = str(settings_files[-1])
            st.session_state["settings_snapshot_path"] = current_setting_path

        selected_setting_label = st.selectbox(
            "Source snapshot",
            settings_labels,
            index=[str(p) for p in settings_files].index(current_setting_path),
            key="settings_snapshot_select",
        )
        selected_setting_path = settings_files[settings_labels.index(selected_setting_label)]
        st.session_state["settings_snapshot_path"] = str(selected_setting_path)

        if st.button(
            "Process Selected Snapshot",
            type="primary",
            key="process_selected_snapshot",
            use_container_width=True,
        ):
            st.session_state.pop("sdl_live_error", None)
            processed = run_snapshot(selected_setting_path)
            if st.session_state.get("sdl_live_error"):
                st.error(st.session_state["sdl_live_error"])
            else:
                st.success(
                    f"Processed completed snapshot: {fmt_time(observation_ts(selected_setting_path), True)}"
                )
                st.rerun()
    else:
        st.info("No Daywise snapshots are available under the configured source root.")


# ============================================================================
# FOOTER
# ============================================================================

st.markdown(
    '<div class="sdl-footer">'
    '<span>NTIS SDL — Intraday Decision Centre</span>'
    '<span>Decision-first · Facts only · No future leakage</span>'
    f'<span>Preview 8587 · Latest completed: {fmt_time(live_ts_for_header, True)}</span>'
    '</div>',
    unsafe_allow_html=True,
)
