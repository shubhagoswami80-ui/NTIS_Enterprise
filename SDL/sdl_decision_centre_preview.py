from __future__ import annotations
from pathlib import Path
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

# ---------------------------------------------------------------------------
# PRESENTATION LAYER
# Existing SDL decision / scoring / replay engine is intentionally untouched.
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
:root{
  --bg:#0a1222; --bg2:#0e1729; --card:#111c2f; --card2:#152238;
  --ink:#edf3ff; --muted:#9eacc3; --line:#263650; --line2:#1c2a41;
  --navy:#07142d; --navy2:#102b5d; --purple:#6842f2; --purple2:#8061ff;
  --green:#19c878; --green-bg:#0d2b20; --green-line:#175d43;
  --red:#ff6670; --red-bg:#32171d; --red-line:#6a2b34;
  --amber:#f3b63f; --amber-bg:#342812; --amber-line:#70531e;
  --blue:#6f92ff; --blue-bg:#16264d; --blue-line:#34539a;
  --slate:#a9b5c9; --slate-bg:#172235;
}
.stApp{background:linear-gradient(180deg,#091222 0%,#0b1424 100%);color:var(--ink);font-size:12px!important}
body,.stApp,.stMarkdown,.stText, p, label, [data-testid="stCaptionContainer"]{color:var(--ink)}
div[data-testid="stVerticalBlock"]{gap:.35rem!important}
.block-container{max-width:1660px;padding:0 16px 24px}
[data-testid="stSidebar"]{display:none!important}
header[data-testid="stHeader"]{background:#07101f!important;height:42px}
footer{display:none}
div[data-testid="stToolbar"],div[data-testid="stDecoration"]{display:none}
div[data-testid="stAppViewContainer"]{background:transparent}

/* FINAL DARK HEADER */
.header-shell{
  margin:0 -16px 10px;
  background:linear-gradient(105deg,#061126 0%,#0b1a38 58%,#11295a 100%);
  color:#fff;border-bottom:1px solid #24385d;
  min-height:62px;padding:8px 16px;
  box-shadow:0 8px 24px rgba(0,0,0,.28)
}
.header-row{display:grid;grid-template-columns:2.1fr 3.4fr 3.0fr;gap:10px;align-items:center}
.header-brand{font-size:20px;font-weight:950;letter-spacing:.01em;white-space:nowrap}
.header-sub{font-size:10px;color:#c0cce0;letter-spacing:.08em;margin-top:2px}
.header-nav{display:flex;align-items:center;gap:4px}
.header-nav div[data-testid="stButton"] button{
  min-height:32px!important;border-radius:7px!important;
  font-size:10px!important;font-weight:900!important;padding:3px 9px!important
}
.header-nav div[data-testid="stButton"] button[kind="primary"]{
  background:linear-gradient(135deg,#6036e7,#7a4cff)!important;
  color:#fff!important;border:1px solid #8b70ff!important
}
.header-nav div[data-testid="stButton"] button[kind="secondary"]{
  background:transparent!important;color:#e8eefb!important;border:1px solid transparent!important
}
.header-controls{display:flex;align-items:center;justify-content:flex-end;gap:6px}
.header-live{
  display:inline-flex;align-items:center;gap:5px;color:#57e39a;
  border:1px solid #1c6046;background:#0a2a20;border-radius:999px;
  padding:6px 9px;font-size:9px;font-weight:950
}
.header-live i{width:7px;height:7px;border-radius:50%;background:#20d27b;box-shadow:0 0 0 3px rgba(32,210,123,.13)}
.header-time{text-align:right;font-variant-numeric:tabular-nums;line-height:1.05}
.header-time b{font-size:14px}.header-time span{display:block;font-size:8px;color:#aebbd2;margin-top:3px}
.header-controls div[data-testid="stButton"] button{
  min-height:31px!important;border-radius:7px!important;font-size:9px!important;
  font-weight:900!important;background:#111f3a!important;color:#eef3ff!important;
  border:1px solid #344767!important
}
.header-controls div[data-testid="stCheckbox"] label p{
  font-size:9px!important;color:#edf3ff!important;font-weight:850!important
}
.header-controls div[data-testid="stSelectbox"]>div>div{
  min-height:31px!important;background:#111f3a!important;border:1px solid #344767!important;color:#fff!important;
  font-size:9px!important
}

/* KPI STRIP */
.kpi-strip{
  background:var(--card);border:1px solid var(--line);border-radius:10px;
  display:grid;grid-template-columns:repeat(6,1fr);
  margin-bottom:10px;box-shadow:0 5px 18px rgba(0,0,0,.16)
}
.kpi-item{padding:9px 13px;border-right:1px solid var(--line2);min-height:70px}
.kpi-item:last-child{border-right:0}
.kpi-label{font-size:10px;color:#a9b9d2;font-weight:950;letter-spacing:.08em}
.kpi-value{font-size:23px;font-weight:950;line-height:1.05;margin-top:4px;color:#f5f8ff}
.kpi-foot{font-size:9px;color:#92a1b8;margin-top:4px}
.kpi-live{float:right;width:7px;height:7px;background:#19c878;border-radius:50%;margin-top:3px;box-shadow:0 0 0 4px rgba(25,200,120,.10)}

/* FILTERS — compact 2x2, all controls retained */
.filter-panel{
  background:#101b2d;border:1px solid var(--line);border-radius:10px;
  padding:8px 10px;margin:8px 0;box-shadow:0 4px 14px rgba(0,0,0,.13)
}
.filter-grid{display:grid;grid-template-columns:1fr 1fr;gap:3px 14px;align-items:start}
.filter-group{
  min-width:0;border-right:1px solid var(--line2);padding:0 10px 5px 0
}
.filter-group:nth-child(2n){border-right:0;padding-right:0}
.filter-title{
  font-size:9px;letter-spacing:.09em;font-weight:950;color:#9eb7e7;margin:0 0 4px
}
.filter-note{font-size:9px;color:#91a1bb;margin:0 0 3px}
div[data-testid="stRadio"]>label{display:none!important}
div[data-testid="stRadio"] [role="radiogroup"]{
  display:flex!important;flex-wrap:wrap!important;gap:4px!important;align-items:center!important
}
div[data-testid="stRadio"] [role="radiogroup"] label{
  border:1px solid #34435c!important;border-radius:999px!important;
  padding:4px 10px!important;background:#131f33!important;margin:0!important;
  min-height:26px!important;box-shadow:none!important
}
div[data-testid="stRadio"] [role="radiogroup"] label p{
  font-size:12px!important;font-weight:850!important;color:#e7edf8!important;margin:0!important
}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked){
  background:#192c54!important;border-color:#6283e6!important
}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p{color:#fff!important}
div[data-testid="stButton"] button{
  border-radius:7px!important;font-weight:850!important;min-height:32px
}

/* PRIORITY RADAR */
.priority-strip{
  background:linear-gradient(110deg,#081833,#102b5b);
  border:1px solid #29436f;border-radius:9px;padding:7px 9px;margin:8px 0;color:#fff
}
.priority-caption{
  font-size:9px;letter-spacing:.11em;font-weight:950;opacity:.88;margin-bottom:5px
}
.priority-card{
  background:rgba(255,255,255,.065);border:1px solid rgba(157,183,235,.20);
  border-radius:8px;padding:6px 8px;min-height:55px
}
.priority-symbol{font-size:12px;font-weight:950}.priority-meta{font-size:8px;color:#aebdd5;margin-top:2px}
.priority-progress{font-size:13px;font-weight:950;margin-top:3px;color:#fff}

/* TABLE */
.table-head{
  background:#121e31!important;border:1px solid var(--line)!important;
  color:#f0f4fb!important
}
.table-title{font-size:13px;font-weight:950;letter-spacing:.02em}
.table-meta{font-size:9px;color:#8fa0ba}
.table-wrap{
  background:#101a2b;border:1px solid var(--line);border-radius:0 0 10px 10px;
  overflow:hidden;box-shadow:0 5px 18px rgba(0,0,0,.16)
}
table.sdlq{
  width:100%;border-collapse:separate;border-spacing:0;font-size:12px;table-layout:fixed
}
table.sdlq th{
  background:#18263b;color:#aebbd1;text-align:left;font-size:10px;
  letter-spacing:.07em;font-weight:950;padding:10px 7px;
  border-bottom:1px solid #33445f;white-space:nowrap
}
table.sdlq td{
  padding:10px 7px;background:#101a2b;color:#e8eef8;
  border-bottom:1px solid #1f2d43;vertical-align:middle;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis
}
table.sdlq tr:hover td{background:#142238}
table.sdlq tr:last-child td{border-bottom:0}
.row-no{color:#7e8da7;font-size:10px}
.stock-cell{display:flex;align-items:center;gap:7px;font-weight:950;font-size:11.5px}
.stock-logo{
  width:27px;height:27px;border-radius:7px;object-fit:contain;background:#fff;
  border:1px solid #3a4b66;padding:3px;display:inline-flex;
  align-items:center;justify-content:center;font-size:8px;color:#19366f;flex:0 0 27px
}
.direction-up{color:#2cda8b;font-weight:950}.direction-down{color:#ff6c76;font-weight:950}
.behaviour-badge{display:inline-block;border-radius:5px;padding:5px 8px;font-size:10px;font-weight:950;white-space:nowrap}
.behaviour-green{background:#0d2d21;color:#41e39a;border:1px solid #1b684a}
.behaviour-red{background:#33171d;color:#ff7b83;border:1px solid #71303a}
.behaviour-amber{background:#342812;color:#ffc95f;border:1px solid #74531e}
.behaviour-slate{background:#182338;color:#aebbd0;border:1px solid #34445e}
.progress-value{font-weight:950;font-variant-numeric:tabular-nums}
.progress-rail{display:inline-block;width:65px;height:7px;border-radius:9px;background:#27364c;vertical-align:middle;margin-left:5px;overflow:hidden}
.progress-fill{height:100%;border-radius:9px;background:#6f92ff}.progress-fill.hot{background:#f3b63f}.progress-fill.break{background:#19c878}
.stage-chip{
  display:inline-block;border-radius:999px;padding:4px 8px;
  background:#172238;border:1px solid #3a4a62;color:#dce5f4;font-size:9.5px;font-weight:850
}
.confirm-chip{
  display:inline-block;border-radius:999px;padding:4px 8px;
  background:#18284e;border:1px solid #405da4;color:#91adff;font-size:9.5px;font-weight:900
}
.strength-strong{color:#25d583;font-weight:950}.strength-mid{color:#c38aff;font-weight:900}.strength-low{color:#9aa9c0;font-weight:850}
.breakout-yes{color:#28d887;font-weight:950}.breakout-no{color:#74839c;font-weight:750}
.time-cell{font-variant-numeric:tabular-nums;font-weight:900;color:#d7e1f2}

/* DETAIL */
.detail{
  background:#111c2f;border:1px solid var(--line);border-radius:10px;
  padding:11px 13px;margin-top:0;box-shadow:0 5px 18px rgba(0,0,0,.16)
}
.detail-head{display:flex;justify-content:space-between;align-items:center;gap:10px}
.detail-symbol{font-size:19px;font-weight:950;color:#f4f7fd}.detail-sub{font-size:9px;color:#8999b3;margin-top:3px}
.detail-card{background:#152238;border:1px solid #2b3b55;border-radius:8px;padding:8px 9px;min-height:65px}
.detail-card{min-width:0;display:flex;flex-direction:column;justify-content:center;overflow:hidden}
.detail-card .detail-value{overflow-wrap:anywhere;word-break:break-word}
.detail .detail-label{font-size:8.5px}
.detail .detail-foot{font-size:8.5px}
.detail-label{font-size:8px;letter-spacing:.09em;font-weight:950;color:#93a5c0}
.detail-value{font-size:18px;font-weight:950;margin-top:3px;color:#f2f6fd;line-height:1.12}
.detail-foot{font-size:8px;color:#8190a8;margin-top:2px}
.factor-list{background:#111c2f;border:1px solid #2a3a54;border-radius:8px;padding:7px 9px}
.factor{display:flex;justify-content:space-between;gap:10px;padding:6px 2px;border-bottom:1px solid #233149;font-size:10px;color:#dce4f1}
.factor:last-child{border-bottom:0}.factor-support{color:#29d687;font-weight:900}.factor-contradict{color:#ff6973;font-weight:900}.factor-neutral{color:#94a2b9;font-weight:800}
.progress-box{background:#121f33;border:1px solid #2a3b55;border-radius:8px;padding:9px 10px}
.progress-title{font-size:9px;letter-spacing:.09em;font-weight:950;color:#93a5c0}.big-progress{font-size:26px;font-weight:950;color:#f5f8ff;margin-top:2px}
.progress-line{height:9px;background:#27364c;border-radius:9px;overflow:hidden;margin:7px 0}
.progress-line-fill{height:100%;background:#19c878;border-radius:9px}
.detail-time{color:#9aa9c0}.first-time{color:#75a0ff;font-weight:950}

/* page cards / replay / history / settings */
.board-head{
  background:#111c2f;border:1px solid var(--line);border-radius:10px;
  padding:9px 12px;margin:0 0 8px;box-shadow:0 4px 14px rgba(0,0,0,.14)
}
.board-title{font-size:15px;font-weight:950;color:#f5f8ff}.board-sub{font-size:10px;color:#a8b6ca;margin-top:2px}
.page-card{background:#111c2f;border:1px solid var(--line);border-radius:9px;padding:12px}
.refresh-row{font-size:9px;color:#8f9eb5;display:flex;justify-content:flex-end;align-items:center;gap:7px;margin-top:-2px}
.footer{border-top:1px solid #223149;margin-top:10px;padding-top:7px;display:flex;justify-content:space-between;gap:10px;font-size:8px;color:#72819a}

/* Streamlit native inputs */
div[data-testid="stSelectbox"]>div>div,
div[data-testid="stDateInput"] input,
div[data-testid="stTextInput"] input{
  background:#131f33!important;color:#edf3ff!important;border:1px solid #34445f!important
}
div[data-testid="stSelectbox"] label,div[data-testid="stDateInput"] label,div[data-testid="stTextInput"] label{
  color:#aebbd0!important;font-size:10px!important;font-weight:850!important
}
.stCaption{color:#8190a8!important}

/* compact replay expander */
div[data-testid="stExpander"]{
  background:#111c2f!important;border:1px solid #2a3b55!important;border-radius:9px!important
}
div[data-testid="stExpander"] summary p{color:#dce5f4!important;font-size:10px!important;font-weight:900!important}

/* mobile */
@media(max-width:1100px){
  .header-row{grid-template-columns:1fr}.header-controls{justify-content:flex-start;flex-wrap:wrap}
  .filter-grid{grid-template-columns:1fr 1fr}.workspace{grid-template-columns:1fr}
}
@media(max-width:700px){
  .block-container{padding:0 8px 16px}.header-shell{margin:0 -8px 8px;padding:8px}
  .header-brand{font-size:18px}.header-sub{font-size:8px}
  .kpi-strip{grid-template-columns:repeat(3,1fr)}.filter-grid{grid-template-columns:1fr}
  .filter-group{border-right:0;border-bottom:1px solid #233149;padding:0 0 3px}
  .table-wrap{overflow-x:auto}table.sdlq{min-width:1120px}
  .footer{flex-direction:column}
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
            result[symbol] = {
                "open_price": float(open_price),
                "opening_straddle_premium": float(premium),
            }
    return result


def candidates(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return build_current_predictions(df, frozen_base(df))


def bucket(row):
    if bool(row.get("factual_breakout", False)):
        return "Breakout"
    strength = str(row.get("strength_label", "")).upper()
    progress = float(row.get("progress", 0) or 0)
    direction = str(row.get("direction_label", "")).upper()
    if "WAIT" in strength:
        return "Wait"
    if progress >= 75:
        return "Approaching"
    if strength == "DEVELOPING":
        return "Developing"
    return "Bullish" if direction == "BULLISH" else "Bearish"


def first_seen(row):
    for key in (
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


def pct(value):
    x = pd.to_numeric(value, errors="coerce")
    return "—" if pd.isna(x) else f"{x:+.2f}%"


def time_text(value, date=True):
    x = pd.to_datetime(value, errors="coerce")
    if pd.isna(x):
        return "—"
    return x.strftime("%d %b %Y, %H:%M:%S" if date else "%H:%M:%S")


def logo(symbol):
    symbol = str(symbol).upper().strip()
    if not symbol or symbol == "NAN":
        return '<span class="stock-logo">—</span>'
    safe = (
        symbol.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    # Original stock logo source with initials always retained as fallback.
    return (
        f'<span class="stock-logo" title="{safe}" aria-label="{safe} logo" '
        f'style="background:#fff url(https://s3-symbol-logo.tradingview.com/'
        f'{symbol.lower()}.svg) center/contain no-repeat;">{safe[:4]}</span>'
    )


def apply_filters(df, key):
    """Presentation filters only. The qualified SDL decision universe is unchanged."""
    if df.empty:
        return df

    progress_options = ["All", "25%+", "50%+", "70%+", "75%+", "Breakout"]
    direction_options = ["All", "Bullish", "Bearish"]
    strength_options = ["All"] + sorted({
        str(x).title()
        for x in df.get("strength_label", pd.Series(dtype=str)).dropna()
        if str(x).strip()
    })
    stage_options = ["All"] + sorted({
        str(x)
        for x in df.get("stage", pd.Series(dtype=str)).dropna()
        if str(x).strip() and str(x).lower() != "nan"
    })

    st.markdown(
        '<div class="filter-panel"><div class="filter-note">'
        'Four independent trader dimensions · filtering never changes the SDL decision score.'
        '</div><div class="filter-grid">',
        unsafe_allow_html=True,
    )

    groups = [
        ("PROGRESS", "Progress", progress_options),
        ("DECISION DIRECTION", "Direction", direction_options),
        ("STRENGTH", "Strength", strength_options),
        ("STAGE", "Stage", stage_options),
    ]
    values = {}
    c1, c2 = st.columns(2)
    for i, (title, label, options) in enumerate(groups):
        with (c1 if i % 2 == 0 else c2):
            st.markdown(
                f'<div class="filter-group"><div class="filter-title">{title}</div>',
                unsafe_allow_html=True,
            )
            values[label] = st.radio(
                label,
                options,
                horizontal=True,
                key=f"{key}_{label.lower().replace(' ', '_')}",
                label_visibility="collapsed",
            )
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)

    out = df.copy()
    direction = values["Direction"]
    strength = values["Strength"]
    stage = values["Stage"]
    progress = values["Progress"]

    if direction != "All":
        out = out[out.direction_label.astype(str).str.upper().eq(direction.upper())]
    if strength != "All":
        out = out[out.strength_label.astype(str).str.upper().eq(strength.upper())]
    if stage != "All":
        out = out[out.stage.astype(str).eq(stage)]

    progress_values = pd.to_numeric(
        out.get("progress", pd.Series(index=out.index, dtype=float)),
        errors="coerce",
    ).fillna(-1)

    if progress == "25%+":
        out = out[progress_values >= 25]
    elif progress == "50%+":
        out = out[progress_values >= 50]
    elif progress == "70%+":
        out = out[progress_values >= 70]
    elif progress == "75%+":
        out = out[progress_values >= 75]
    elif progress == "Breakout":
        out = out[out.factual_breakout.astype(bool)]

    return out


def behaviour_class(row):
    direction = str(row.get("direction_label", "")).upper()
    strength = str(row.get("strength_label", "")).upper()
    if direction == "BULLISH":
        return "behaviour-green"
    if direction == "BEARISH":
        return "behaviour-red"
    if strength == "DEVELOPING":
        return "behaviour-amber"
    return "behaviour-slate"


def queue_html(df):
    if df.empty:
        return '<div style="padding:18px;text-align:center;color:#7d8797;font-size:12px">No stocks match the current filters.</div>'

    rows = []
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        price = pd.to_numeric(row.get("signed_price_move_pct"), errors="coerce")
        progress = float(pd.to_numeric(row.get("progress"), errors="coerce") or 0)
        strength_value = pd.to_numeric(row.get("strength"), errors="coerce")
        strength_label = str(row.get("strength_label", "—")).upper()
        direction = str(row.get("direction_label", "—")).upper()
        stage = str(row.get("stage", "—"))
        confirmation = str(row.get("confirmation", row.get("confirmation_label", "STRONG")))
        breakout = bool(row.get("factual_breakout", False))
        first = first_seen(row)
        updated = pd.to_datetime(row.get("observation_timestamp"), errors="coerce")

        price_class = (
            "direction-up" if pd.notna(price) and price > 0
            else "direction-down" if pd.notna(price) and price < 0
            else ""
        )
        strength_class = (
            "strength-strong" if strength_label == "STRONG"
            else "strength-mid" if strength_label == "DEVELOPING"
            else "strength-low"
        )
        fill_class = "break" if breakout else "hot" if progress >= 70 else ""
        width = min(max(progress, 0), 100)
        title = f"First trigger: {time_text(first)} | Updated: {time_text(updated)}"

        rows.append(
            f'''<tr title="{title}">
<td class="row-no">{idx}</td>
<td><div class="stock-cell">{logo(row.get("symbol"))}<span>{str(row.get("symbol")).upper()}</span></div></td>
<td><span class="behaviour-badge {behaviour_class(row)}">{direction.title()} · {strength_label.title()}</span></td>
<td class="{price_class}">{pct(price)}</td>
<td><span class="progress-value">{progress:.1f}%</span><span class="progress-rail"><span class="progress-fill {fill_class}" style="width:{width:.0f}%"></span></span></td>
<td><span class="stage-chip">{stage}</span></td>
<td><span class="confirm-chip">{confirmation}</span></td>
<td class="{strength_class}">{'—' if pd.isna(strength_value) else f'{float(strength_value):.0f}'}</td>
<td class="{'breakout-yes' if breakout else 'breakout-no'}">{'YES' if breakout else '—'}</td>
<td class="time-cell">{time_text(first, False)}</td>
<td class="time-cell">{time_text(updated, False)}</td>
</tr>'''
        )

    return (
        '<div class="table-wrap"><table class="sdlq">'
        '<thead><tr>'
        '<th style="width:3%">#</th><th style="width:14%">STOCK</th>'
        '<th style="width:18%">DIRECTION / STRENGTH</th><th style="width:9%">MOMENTUM</th>'
        '<th style="width:15%">STRADDLE PROGRESS</th><th style="width:13%">STAGE</th>'
        '<th style="width:11%">CONFIRMATION</th><th style="width:7%">STRENGTH</th>'
        '<th style="width:6%">BREAKOUT</th><th style="width:7%">FIRST TIME</th>'
        '<th style="width:7%">UPDATED</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    )


def priority_strip(df, key="priority_filter"):
    if df.empty:
        return

    st.markdown(
        '<div class="priority-strip"><div class="priority-caption">'
        'PRIORITY RADAR · INDEPENDENT FILTER</div>',
        unsafe_allow_html=True,
    )
    p1, p2 = st.columns(2)
    with p1:
        st.markdown('<div class="filter-title">PROGRESS</div>', unsafe_allow_html=True)
        priority_progress = st.radio(
            "Priority progress",
            ["All", "25%+", "50%+", "70%+", "75%+", "Breakout"],
            horizontal=True,
            key=f"{key}_progress",
            label_visibility="collapsed",
        )
    with p2:
        st.markdown('<div class="filter-title">STRENGTH</div>', unsafe_allow_html=True)
        priority_strength = st.radio(
            "Priority strength",
            ["All", "Strong", "Developing"],
            horizontal=True,
            key=f"{key}_strength",
            label_visibility="collapsed",
        )

    top = df.copy()
    pv = pd.to_numeric(
        top.get("progress", pd.Series(index=top.index, dtype=float)),
        errors="coerce",
    ).fillna(-1)

    if priority_progress == "25%+":
        top = top[pv >= 25]
    elif priority_progress == "50%+":
        top = top[pv >= 50]
    elif priority_progress == "70%+":
        top = top[pv >= 70]
    elif priority_progress == "75%+":
        top = top[pv >= 75]
    elif priority_progress == "Breakout":
        top = top[top.factual_breakout.astype(bool)]

    if priority_strength != "All":
        top = top[top.strength_label.astype(str).str.upper().eq(priority_strength.upper())]

    top = top.sort_values(
        ["factual_breakout", "strength", "progress"],
        ascending=[False, False, False],
    ).head(5)

    if top.empty:
        st.markdown(
            '<div style="font-size:10px;opacity:.8;padding:6px 0">No priority stocks match these filters.</div>',
            unsafe_allow_html=True,
        )
        return

    cards = []
    for _, row in top.iterrows():
        progress = float(pd.to_numeric(row.get("progress"), errors="coerce") or 0)
        first = first_seen(row)
        cards.append(
            f'<div class="priority-card">'
            f'<div class="priority-symbol">{logo(row.get("symbol"))} '
            f'{str(row.get("symbol")).upper()}</div>'
            f'<div class="priority-meta">{str(row.get("direction_label","—")).title()} · '
            f'{str(row.get("strength_label","—")).title()} · {str(row.get("stage","—"))}</div>'
            f'<div class="priority-progress">{progress:.1f}%'
            f'{" · BREAKOUT" if bool(row.get("factual_breakout",False)) else ""}</div>'
            f'<div class="priority-meta">First: {time_text(first, False)}</div>'
            f'</div>'
        )

    st.markdown(
        '<div style="display:flex;gap:8px;overflow-x:auto">' + "".join(cards) +
        '</div></div>',
        unsafe_allow_html=True,
    )


def selected_detail(df, key):
    if df.empty or "symbol" not in df.columns:
        return

    symbols = [str(x).upper() for x in df["symbol"].dropna().tolist()]
    if not symbols:
        return

    symbol = st.selectbox(
        "Selected stock — detail opens here",
        symbols,
        key=f"{key}_stock",
    )
    row = df[df.symbol.astype(str).str.upper().eq(symbol)].iloc[0]

    direction = str(row.get("direction_label", "—")).upper()
    strength_label = str(row.get("strength_label", "—")).upper()
    stage = str(row.get("stage", "—"))
    progress = float(pd.to_numeric(row.get("progress"), errors="coerce") or 0)
    price_move = pd.to_numeric(row.get("signed_price_move_pct"), errors="coerce")
    strength = pd.to_numeric(row.get("strength"), errors="coerce")
    breakout = bool(row.get("factual_breakout", False))
    updated = row.get("observation_timestamp")
    first = first_seen(row)

    badge_class = (
        "behaviour-green" if direction == "BULLISH"
        else "behaviour-red" if direction == "BEARISH"
        else "behaviour-amber"
    )

    st.markdown(
        f"""
<div class="detail">
  <div class="detail-head">
    <div>
      <div class="detail-symbol">{logo(symbol)} {symbol}</div>
      <div class="detail-sub">
        First seen: <b>{time_text(first)}</b> · Updated: <b>{time_text(updated)}</b>
      </div>
    </div>
    <span class="behaviour-badge {badge_class}">
      {direction.title()} · {strength_label.title()}
    </span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    a, b, c, d = st.columns([1,1.15,1,1])
    a.markdown(
        f'<div class="detail-card"><div class="detail-label">STRENGTH</div>'
        f'<div class="detail-value">{"—" if pd.isna(strength) else f"{float(strength):.0f}"}</div>'
        f'<div class="detail-foot">{strength_label.title()}</div></div>',
        unsafe_allow_html=True,
    )
    b.markdown(
        f'<div class="detail-card"><div class="detail-label">STRADDLE PROGRESS</div>'
        f'<div class="detail-value">{progress:.1f}%</div>'
        f'<div class="detail-foot">Next: {"Breakout" if progress >= 75 else "75%" if progress >= 50 else "50%" if progress >= 25 else "25%"}</div></div>',
        unsafe_allow_html=True,
    )
    c.markdown(
        f'<div class="detail-card"><div class="detail-label">STAGE</div>'
        f'<div class="detail-value" style="font-size:16px">{stage}</div>'
        f'<div class="detail-foot">Existing SDL stage</div></div>',
        unsafe_allow_html=True,
    )
    d.markdown(
        f'<div class="detail-card"><div class="detail-label">MOMENTUM</div>'
        f'<div class="detail-value">{pct(price_move)}</div>'
        f'<div class="detail-foot">As of {time_text(updated, False)}</div></div>',
        unsafe_allow_html=True,
    )

    p1, p2 = st.columns([1.35, 1])
    with p1:
        st.markdown(
            f'<div class="progress-box"><div class="progress-title">STRADDLE PROCESS</div>'
            f'<div class="big-progress">{progress:.1f}%</div>'
            f'<div class="progress-line"><div class="progress-line-fill" style="width:{min(max(progress,0),100):.0f}%"></div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:8px;color:#778196;font-weight:800">'
            f'<span>25%</span><span>50%</span><span>75%</span><span>100% BREAKOUT</span></div></div>',
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown('<div class="factor-list">', unsafe_allow_html=True)
        for factor in row.get("factors", []) or []:
            state = str(getattr(factor, "state", ""))
            css = (
                "factor-support" if state == "SUPPORT"
                else "factor-contradict" if state == "CONTRADICT"
                else "factor-neutral"
            )
            st.markdown(
                f'<div class="factor"><span>{getattr(factor, "label", "Factor")}</span>'
                f'<b class="{css}">{state}</b></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    try:
        labels = factor_labels(row.to_dict())
        if labels:
            st.caption(" · ".join(labels))
    except Exception:
        pass

    st.markdown(
        '<div style="font-size:9px;color:#8b9ab2;margin-top:5px">'
        'Selection uses the existing qualified decision record; no new scoring is performed.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="detail-card" style="margin-top:8px">'
        '<div class="detail-label">MARKET CONTEXT · PLANNED</div>'
        '<div class="detail-foot" style="font-size:9px;margin-top:5px">'
        'Latest stock news + latest result → impact analysis will be added as a separate evidence feed. '
        'No placeholder/news data is injected into the SDL decision.'
        '</div></div>',
        unsafe_allow_html=True,
    )


def metrics(df, stamp):
    values = [
        len(df),
        int(df.direction_label.eq("BULLISH").sum()) if not df.empty else 0,
        int(df.direction_label.eq("BEARISH").sum()) if not df.empty else 0,
        int(df.strength_label.eq("STRONG").sum()) if not df.empty else 0,
        int(df.factual_breakout.sum()) if not df.empty else 0,
    ]
    first_alert = pd.NaT
    if not df.empty:
        try:
            first_alert = min(
                (x for x in (first_seen(row) for _, row in df.iterrows()) if pd.notna(x)),
                default=pd.NaT,
            )
        except Exception:
            first_alert = pd.NaT

    labels = ["QUALIFIED", "BULLISH", "BEARISH", "STRONG", "BREAKOUT", "FIRST ALERT"]
    values = values + [time_text(first_alert, False)]
    cols = st.columns(6)
    for col, label, value in zip(cols, labels, values):
        col.markdown(
            f'<div class="kpi"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="font-size:{"14px" if label=="FIRST ALERT" else "23px"}">{value}</div>'
            f'<div class="kpi-foot">Data updated · {time_text(stamp, False)}</div></div>',
            unsafe_allow_html=True,
        )


def run_live(path, stamp):
    try:
        result = process_snapshot(path, stamp)
        frames = (
            [x for x in result if isinstance(x, pd.DataFrame)]
            if isinstance(result, tuple)
            else [result]
        )
        # Preserve the existing application's current-snapshot selection.
        df = frames[1] if len(frames) > 1 else (frames[0] if frames else pd.DataFrame())
        return candidates(df)
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# FINAL HEADER / NAVIGATION
# Presentation only. No decision-engine state is changed here.
# ---------------------------------------------------------------------------
if "page" not in st.session_state:
    st.session_state["page"] = "Decision Board"
if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = False
if "refresh_seconds" not in st.session_state:
    st.session_state["refresh_seconds"] = 10

page = st.session_state["page"]

# Current live source is resolved before the header so the first/updated
# timestamps shown in the header are the same timestamps used by the board.
today = pd.Timestamp.now().date().isoformat()
today_files = files(today)
live_path = max(today_files, key=ts) if today_files else None
live_ts = ts(live_path) if live_path else pd.NaT
live = run_live(live_path, live_ts) if live_path is not None else pd.DataFrame()

first_alert = pd.NaT
if not live.empty:
    try:
        first_alert = min(
            (x for x in (first_seen(row) for _, row in live.iterrows()) if pd.notna(x)),
            default=pd.NaT,
        )
    except Exception:
        first_alert = pd.NaT

st.markdown('<div class="header-shell">', unsafe_allow_html=True)
h1, h2, h3 = st.columns([2.0, 3.45, 3.1])
with h1:
    st.markdown(
        '<div class="header-brand">◉ NTIS SDL</div>'
        '<div class="header-sub">INTRADAY DECISION CENTRE · STRADDLE BREAKOUT</div>',
        unsafe_allow_html=True,
    )
with h2:
    st.markdown('<div class="header-nav">', unsafe_allow_html=True)
    n1, n2, n3 = st.columns([1.2, 1.45, .95])
    with n1:
        if st.button(
            "Decision Board",
            type="primary" if page == "Decision Board" else "secondary",
            key="nav_decision",
            use_container_width=True,
        ):
            st.session_state["page"] = "Decision Board"
            st.rerun()
    with n2:
        if st.button(
            "Historical Evidence",
            type="primary" if page == "Historical Evidence" else "secondary",
            key="nav_history",
            use_container_width=True,
        ):
            st.session_state["page"] = "Historical Evidence"
            st.rerun()
    with n3:
        if st.button(
            "Settings",
            type="primary" if page == "Settings" else "secondary",
            key="nav_settings",
            use_container_width=True,
        ):
            st.session_state["page"] = "Settings"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
with h3:
    st.markdown('<div class="header-controls">', unsafe_allow_html=True)
    q1, q2, q3, q4, q5 = st.columns([.78, 1.25, .9, 1.05, .72])
    with q1:
        st.markdown(
            '<div style="padding-top:3px"><span class="header-live"><i></i>LIVE</span></div>',
            unsafe_allow_html=True,
        )
    with q2:
        now = pd.Timestamp.now()
        st.markdown(
            f'<div class="header-time"><b>{now.strftime("%I:%M:%S %p")}</b>'
            f'<span>{now.strftime("%d %b %Y")}</span></div>',
            unsafe_allow_html=True,
        )
    with q3:
        if st.button("↻ Refresh", key="header_refresh", use_container_width=True):
            st.rerun()
    with q4:
        st.session_state["auto_refresh"] = st.checkbox(
            "Auto Refresh",
            value=st.session_state["auto_refresh"],
            key="header_auto_refresh",
        )
    with q5:
        st.selectbox(
            "Refresh interval",
            [5, 10, 15, 30, 60],
            index=[5, 10, 15, 30, 60].index(
                st.session_state.get("refresh_seconds", 10)
            ),
            key="refresh_seconds",
            label_visibility="collapsed",
        )
    st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# A small timestamp strip directly under the header makes the immutable first
# trigger visible without consuming a table column.
st.markdown(
    f'<div style="display:flex;justify-content:flex-end;gap:18px;align-items:center;'
    f'font-size:10px;color:#a8b6ca;margin:0 1px 7px">'
    f'<span>FIRST ALERT <b style="color:#79a2ff">{time_text(first_alert)}</b></span>'
    f'<span>DATA UPDATED <b style="color:#dce6f6">{time_text(live_ts)}</b></span>'
    f'</div>',
    unsafe_allow_html=True,
)

page = st.session_state["page"]

today = pd.Timestamp.now().date().isoformat()
today_files = files(today)
live_path = max(today_files, key=ts) if today_files else None
live_ts = ts(live_path) if live_path else pd.NaT
live = run_live(live_path, live_ts) if live_path is not None else pd.DataFrame()

st.markdown(
    f"""
<div class="topbar">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:16px">
    <div>
      <div class="top-title">NTIS SDL — Intraday Decision Centre</div>
      <div class="top-sub">Decision-first view · existing SDL engine · presentation layer only</div>
    </div>
    <div class="top-meta">
      <div class="live-dot">● LIVE</div>
      <div>As of: <span class="clock">{time_text(live_ts)}</span></div>
      <div>Timestamp retained on every decision</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if page == "Decision Board":
    st.markdown(
        '<div class="board-head"><div class="board-title">LIVE DECISION BOARD</div>'
        '<div class="board-sub">Quick selection by the four primary trader dimensions: '
        'Strength · Direction · Stage · Straddle Progress. Confirmation follows.</div></div>',
        unsafe_allow_html=True,
    )

    m1, m2 = st.columns([1, 1])
    with m1:
        if st.button("↻ Refresh evidence", use_container_width=True):
            st.rerun()
    with m2:
        st.markdown(
            f'<div class="refresh-row">Latest completed snapshot · '
            f'<span class="clock">{time_text(live_ts)}</span></div>',
            unsafe_allow_html=True,
        )

    metrics(live, live_ts)
    visible = apply_filters(live, "board_filter")

    st.markdown(
        f'<div style="font-size:10px;color:#6f7b8e;margin:4px 2px 5px">'
        f'<b>{len(visible)}</b> matching stock(s) · '
        f'filtering never changes the underlying SDL decision score.</div>',
        unsafe_allow_html=True,
    )

    priority_strip(live, "priority_filter")

    left, right = st.columns([3.25, 1.05], gap="small")
    with left:
        st.markdown(
            f'<div class="table-head" style="background:#fff;border:1px solid #dce3ed;'
            f'border-radius:11px 11px 0 0"><div><div class="table-title">LIVE QUEUE</div>'
            f'<div class="table-meta">UPDATED {time_text(live_ts)} · FIRST TIME is immutable</div></div>'
            f'<div class="table-meta">{len(visible)} visible</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(queue_html(visible), unsafe_allow_html=True)

        with st.expander("INTRADAY REPLAY · same page · Live state remains unchanged", expanded=False):
            all_files = files()
            days = sorted(
                {ts(p).date().isoformat() for p in all_files if pd.notna(ts(p))},
                reverse=True,
            )
            if days:
                r1, r2, r3 = st.columns([1.0, 1.35, .95])
                with r1:
                    day = st.date_input("Trading day", pd.Timestamp(days[0]).date(), key="replay_day_home")
                day_files = files(day.isoformat())
                times = [ts(p) for p in day_files]
                with r2:
                    if times:
                        labels = [t.strftime("%H:%M:%S") for t in times]
                        label = st.selectbox("Snapshot time", labels, key="replay_time_home")
                        selected = day_files[labels.index(label)]
                    else:
                        selected = None
                        st.info("No snapshots for selected day.")
                with r3:
                    if selected is not None and st.button("Load Replay", type="primary", use_container_width=True, key="load_replay_home"):
                        try:
                            replay_trading_date(day.isoformat())
                            _, replay_df, replay_ts = process_snapshot(selected, ts(selected))
                            st.session_state["replay_df"] = replay_df
                            st.session_state["replay_ts"] = replay_ts
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Replay failed: {exc}")

                replay_df = st.session_state.get("replay_df", pd.DataFrame())
                if isinstance(replay_df, pd.DataFrame) and not replay_df.empty:
                    replay_predictions = candidates(replay_df)
                    replay_ts = st.session_state.get("replay_ts", pd.NaT)
                    st.markdown(
                        f'<div class="filter-panel"><b>Replay boundary:</b> '
                        f'<span class="clock">{time_text(replay_ts)}</span> · '
                        'Later observations cannot upgrade this result.</div>',
                        unsafe_allow_html=True,
                    )
                    replay_visible = apply_filters(replay_predictions, "replay_home")
                    st.markdown(queue_html(replay_visible), unsafe_allow_html=True)
                else:
                    st.caption("Select a trading day and snapshot, then Load Replay.")
            else:
                st.info("No historical snapshots available.")

    with right:
        st.markdown(
            '<div class="table-head" style="background:#fff;border:1px solid #dce3ed;'
            'border-radius:11px 11px 0 0"><div class="table-title">STOCK DETAIL</div>'
            '<div class="table-meta">Selected decision</div></div>',
            unsafe_allow_html=True,
        )
        selected_detail(visible, "board_detail")

elif page == "Replay":
    st.markdown(
        '<div class="board-head"><div class="board-title">HISTORICAL REPLAY</div>'
        '<div class="board-sub">Trading day and exact snapshot timestamp. Existing replay implementation '
        'is used; later observations cannot upgrade the selected result.</div></div>',
        unsafe_allow_html=True,
    )

    all_files = files()
    days = sorted(
        {ts(p).date().isoformat() for p in all_files if pd.notna(ts(p))},
        reverse=True,
    )

    if days:
        day = st.date_input(
            "Trading day",
            pd.Timestamp(days[0]).date(),
            key="replay_day",
        )
        day_files = files(day.isoformat())
        times = [ts(p) for p in day_files]

        if times:
            labels = [t.strftime("%H:%M:%S") for t in times]
            label = st.selectbox("Snapshot time", labels, key="replay_time")
            selected = day_files[labels.index(label)]

            if st.button("Replay selected snapshot", type="primary"):
                try:
                    replay_trading_date(day.isoformat())
                    _, replay_df, replay_ts = process_snapshot(selected, ts(selected))
                    st.session_state["replay_df"] = replay_df
                    st.session_state["replay_ts"] = replay_ts
                    st.rerun()
                except Exception as exc:
                    st.error(f"Replay failed: {exc}")

    replay_df = st.session_state.get("replay_df", pd.DataFrame())
    if isinstance(replay_df, pd.DataFrame) and not replay_df.empty:
        replay_predictions = candidates(replay_df)
        replay_ts = st.session_state.get("replay_ts", pd.NaT)
        st.markdown(
            f'<div class="filter-panel"><b>Replay boundary:</b> '
            f'<span class="clock">{time_text(replay_ts)}</span> · '
            f'Later observations cannot upgrade this result.</div>',
            unsafe_allow_html=True,
        )
        replay_visible = apply_filters(replay_predictions, "replay_filter")
        st.markdown(queue_html(replay_visible), unsafe_allow_html=True)
        selected_detail(replay_visible, "replay_detail")
    else:
        st.info("Select a trading day and snapshot time, then load Replay.")

elif page == "Inspector":
    source = live
    if (
        isinstance(st.session_state.get("replay_df"), pd.DataFrame)
        and not st.session_state["replay_df"].empty
    ):
        source = candidates(st.session_state["replay_df"])

    st.markdown(
        '<div class="board-head"><div class="board-title">DECISION INSPECTOR</div>'
        '<div class="board-sub">Detailed evidence for an already-qualified decision. '
        'No new scoring is performed.</div></div>',
        unsafe_allow_html=True,
    )

    if source.empty:
        st.info("No qualified decision available.")
    else:
        selected_detail(source, "inspector")

elif page == "Historical Evidence":
    st.markdown(
        '<div class="board-head"><div class="board-title">HISTORICAL EVIDENCE</div>'
        '<div class="board-sub">Factual historical evidence only; it never feeds information '
        'backward into Live or Replay.</div></div>',
        unsafe_allow_html=True,
    )
    events = load_events(EVENT_CSV)
    if events is None or events.empty:
        st.info("No historical evidence records available.")
    else:
        events = events.copy()
        if "observation_timestamp" in events.columns:
            events["observation_timestamp"] = pd.to_datetime(
                events["observation_timestamp"], errors="coerce"
            )
            events = events.sort_values("observation_timestamp", ascending=False)
            events["observation_timestamp"] = events["observation_timestamp"].dt.strftime(
                "%d %b %Y, %H:%M:%S"
            )
        keep = [
            c for c in [
                "observation_timestamp", "symbol", "direction",
                "price_chg_pct", "breakout_distance", "strength"
            ]
            if c in events.columns
        ]
        st.dataframe(
            events[keep] if keep else events,
            width="stretch",
            hide_index=True,
        )

else:
    st.markdown(
        '<div class="board-head"><div class="board-title">SETTINGS</div>'
        '<div class="board-sub">Administrator settings. Source location is intentionally '
        'absent from the live decision view.</div></div>',
        unsafe_allow_html=True,
    )
    root = st.text_input(
        "Active source data folder",
        str(getattr(sdl_pipeline, "INTRADAY_SOURCE_ROOT", "")),
    )
    if st.button("Apply source folder", type="primary"):
        source_path = Path(root).expanduser().resolve()
        sdl_pipeline.INTRADAY_SOURCE_ROOT = source_path
        sdl_config.INTRADAY_SOURCE_ROOT = source_path
        st.success("Source folder applied for this SDL application session.")

    st.markdown(
        '<div class="filter-panel"><b>Runtime:</b> Preview 8587 · Production 8504 untouched.<br>'
        '<b>Decision engine:</b> existing SDL pipeline / prediction / replay implementation.</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# AUTO REFRESH
# ---------------------------------------------------------------------------
if st.session_state.get("auto_refresh"):
    st.markdown(
        f'<meta http-equiv="refresh" content="{int(st.session_state.get("refresh_seconds", 10))}">',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="footer"><span>NTIS SDL · Intraday Straddle Breakout Decision Centre</span>'
    '<span>First trigger retained · Latest snapshot shown · Preview 8587 · Production 8504 untouched</span></div>',
    unsafe_allow_html=True,
)
