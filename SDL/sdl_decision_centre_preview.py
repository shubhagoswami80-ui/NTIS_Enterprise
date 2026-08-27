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
  --navy:#07162f; --navy2:#102b5c; --ink:#18243d; --muted:#69758a;
  --page:#f4f7fb; --card:#ffffff; --line:#dfe5ee; --soft:#f7f9fc;
  --green:#11834a; --green-bg:#eaf8f0; --green-line:#bfe4cd;
  --red:#c52b35; --red-bg:#fff0f1; --red-line:#f1c4c8;
  --amber:#a46a00; --amber-bg:#fff7e5; --amber-line:#efd9a1;
  --blue:#315dcc; --blue-bg:#eef2ff; --blue-line:#d4ddff;
  --slate:#5d687a; --slate-bg:#f1f4f8;
}
.stApp{background:var(--page);color:var(--ink)}
.block-container{max-width:1540px;padding:12px 18px 28px}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line)}
[data-testid="stSidebar"] .block-container{padding:18px 14px}
header[data-testid="stHeader"]{background:rgba(244,247,251,.94)}

.topbar{
  background:linear-gradient(112deg,var(--navy),#0b2047 58%,var(--navy2));
  color:#fff;border-radius:14px;padding:13px 18px;margin:2px 0 10px;
  box-shadow:0 8px 24px rgba(7,22,47,.13)
}
.top-title{font-size:25px;font-weight:850;letter-spacing:-.02em}
.top-sub{font-size:11px;opacity:.74;margin-top:2px}
.top-meta{text-align:right;font-size:11px;line-height:1.55}
.live-dot{color:#63e39b;font-weight:850}
.clock{font-variant-numeric:tabular-nums;font-weight:800}

.board-head{
  background:#fff;border:1px solid var(--line);border-radius:13px;
  padding:11px 14px;margin:0 0 9px;box-shadow:0 2px 10px rgba(20,35,60,.035)
}
.board-title{font-size:17px;font-weight:850}
.board-sub{font-size:11px;color:var(--muted);margin-top:2px}

.kpi{
  background:#fff;border:1px solid var(--line);border-radius:10px;
  padding:8px 11px;min-height:63px
}
.kpi-label{font-size:9px;letter-spacing:.09em;font-weight:850;color:#788397}
.kpi-value{font-size:21px;font-weight:850;line-height:1.1;margin-top:2px}
.kpi-foot{font-size:9px;color:#8a94a5;margin-top:3px}

.filter-panel{
  background:#fff;border:1px solid var(--line);border-radius:12px;
  padding:10px 12px;margin:9px 0;box-shadow:0 2px 9px rgba(20,35,60,.03)
}
.filter-label{
  font-size:9px;letter-spacing:.10em;font-weight:850;color:#69758a;
  margin-bottom:4px
}
div[data-testid="stHorizontalBlock"] div[data-testid="stRadio"] label p{
  font-size:11px!important;font-weight:750!important
}
div[data-testid="stRadio"] [role="radiogroup"]{gap:4px!important}
div[data-testid="stRadio"] label{
  border:1px solid #dfe5ee!important;border-radius:999px!important;
  padding:4px 10px!important;background:#fff!important
}
div[data-testid="stRadio"] label:has(input:checked){
  background:#eef2ff!important;border-color:#b9c7f6!important;color:#294fb5!important
}
div[data-testid="stButton"] button{
  border-radius:9px;font-weight:800;min-height:34px
}
.refresh-row{
  font-size:10px;color:var(--muted);display:flex;justify-content:flex-end;
  align-items:center;gap:7px;margin-top:-4px
}

.priority-strip{
  background:linear-gradient(110deg,#091a38,#132e61);
  border-radius:12px;padding:9px 11px;margin:9px 0;color:#fff
}
.priority-caption{
  font-size:9px;letter-spacing:.10em;font-weight:850;opacity:.72;margin-bottom:6px
}
.priority-card{
  background:rgba(255,255,255,.085);border:1px solid rgba(255,255,255,.12);
  border-radius:9px;padding:7px 9px;min-height:60px
}
.priority-symbol{font-size:12px;font-weight:850}
.priority-meta{font-size:9px;opacity:.78;margin-top:3px}
.priority-progress{font-size:13px;font-weight:850;margin-top:4px}

.table-wrap{
  background:#fff;border:1px solid var(--line);border-radius:12px;
  overflow:hidden;box-shadow:0 2px 11px rgba(20,35,60,.04)
}
table.sdlq{
  width:100%;border-collapse:separate;border-spacing:0;
  font-size:12px;table-layout:fixed
}
table.sdlq th{
  background:#f7f9fc;color:#667286;text-align:left;
  font-size:9px;letter-spacing:.075em;font-weight:850;
  padding:9px 7px;border-bottom:1px solid var(--line);white-space:nowrap
}
table.sdlq td{
  padding:9px 7px;background:#fff;border-bottom:1px solid #edf0f4;
  vertical-align:middle;white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
table.sdlq tr:last-child td{border-bottom:0}
.row-no{color:#8b95a5;font-size:10px}
.stock-cell{display:flex;align-items:center;gap:7px;font-weight:850}
.stock-logo{
  width:26px;height:26px;border-radius:7px;object-fit:contain;background:#fff;
  border:1px solid #dfe5ee;padding:3px;display:inline-flex;
  align-items:center;justify-content:center;font-size:8px;color:#19366f;
  flex:0 0 26px
}
.direction-up{color:var(--green);font-weight:850}
.direction-down{color:var(--red);font-weight:850}
.progress-value{font-weight:850;font-variant-numeric:tabular-nums}
.progress-rail{
  display:inline-block;width:58px;height:7px;border-radius:9px;
  background:#e6ebf2;vertical-align:middle;margin-left:5px;overflow:hidden
}
.progress-fill{height:100%;border-radius:9px;background:#315dcc}
.progress-fill.hot{background:#a46a00}
.progress-fill.break{background:#11834a}
.stage-chip{
  display:inline-block;border-radius:999px;padding:4px 8px;
  background:#f1f4f8;border:1px solid #dce2ea;font-size:9px;font-weight:800
}
.confirm-chip{
  display:inline-block;border-radius:999px;padding:4px 8px;
  background:var(--blue-bg);border:1px solid var(--blue-line);
  color:#3155b8;font-size:9px;font-weight:850
}
.strength-strong{color:#0b7c43;font-weight:900}
.strength-mid{color:#a46a00;font-weight:850}
.strength-low{color:#667286;font-weight:800}
.breakout-yes{color:var(--green);font-weight:900}
.breakout-no{color:#9aa3b1;font-weight:750}
.time-cell{font-variant-numeric:tabular-nums;font-weight:800;color:#33405a}

.detail{
  background:#fff;border:1px solid var(--line);border-radius:13px;
  padding:12px 14px;margin-top:10px;box-shadow:0 2px 11px rgba(20,35,60,.035)
}
.detail-head{display:flex;justify-content:space-between;align-items:center;gap:12px}
.detail-symbol{font-size:19px;font-weight:900}
.detail-sub{font-size:10px;color:var(--muted);margin-top:2px}
.behaviour-badge{
  display:inline-block;border-radius:999px;padding:5px 10px;
  font-size:10px;font-weight:900
}
.behaviour-green{background:var(--green-bg);color:var(--green);border:1px solid var(--green-line)}
.behaviour-red{background:var(--red-bg);color:var(--red);border:1px solid var(--red-line)}
.behaviour-amber{background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber-line)}
.behaviour-slate{background:var(--slate-bg);color:var(--slate);border:1px solid #dce2eb}

.detail-card{
  background:var(--soft);border:1px solid var(--line);border-radius:9px;
  padding:8px 10px;min-height:67px
}
.detail-label{font-size:8px;letter-spacing:.09em;font-weight:850;color:#788397}
.detail-value{font-size:19px;font-weight:900;margin-top:3px}
.detail-foot{font-size:9px;color:#8a94a5;margin-top:2px}
.factor-list{
  background:#fff;border:1px solid var(--line);border-radius:9px;
  padding:8px 10px
}
.factor{
  display:flex;justify-content:space-between;gap:12px;
  padding:7px 2px;border-bottom:1px solid #edf0f4;font-size:10px
}
.factor:last-child{border-bottom:0}
.factor-support{color:var(--green);font-weight:850}
.factor-contradict{color:var(--red);font-weight:850}
.factor-neutral{color:#7b8494;font-weight:800}

.progress-box{
  background:#fbfcff;border:1px solid var(--line);border-radius:9px;padding:10px 11px
}
.progress-title{font-size:9px;letter-spacing:.09em;font-weight:850;color:#69758a}
.big-progress{font-size:25px;font-weight:900;margin-top:2px}
.progress-line{height:9px;background:#e4e9f0;border-radius:9px;overflow:hidden;margin:8px 0}
.progress-line-fill{height:100%;background:#315dcc;border-radius:9px}

.footer{
  border-top:1px solid var(--line);margin-top:12px;padding-top:8px;
  display:flex;justify-content:space-between;gap:10px;font-size:9px;color:#808a9b
}
@media(max-width:900px){
  .block-container{padding:8px}
  .top-title{font-size:19px}
  .top-meta{font-size:9px}
  .board-title{font-size:15px}
  table.sdlq{font-size:11px;min-width:980px}
  .table-wrap{overflow-x:auto}
  .priority-card{min-width:120px}
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
    """Presentation filters only. No scoring or selection logic is changed."""
    if df.empty:
        return df

    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)

    st.markdown('<div class="filter-label">PROGRESS</div>', unsafe_allow_html=True)
    progress = st.radio(
        "Progress",
        ["All", "25%+", "50%+", "70%+", "75%+", "Breakout"],
        horizontal=True,
        key=f"{key}_progress",
        label_visibility="collapsed",
    )

    st.markdown('<div class="filter-label">DECISION DIRECTION</div>', unsafe_allow_html=True)
    direction = st.radio(
        "Direction",
        ["All", "Bullish", "Bearish"],
        horizontal=True,
        key=f"{key}_direction",
        label_visibility="collapsed",
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="filter-label">STRENGTH</div>', unsafe_allow_html=True)
        strength_options = ["All"] + sorted(
            {str(x).title() for x in df.get("strength_label", pd.Series(dtype=str)).dropna()}
        )
        strength = st.radio(
            "Strength",
            strength_options,
            horizontal=True,
            key=f"{key}_strength",
            label_visibility="collapsed",
        )
    with c2:
        st.markdown('<div class="filter-label">STAGE</div>', unsafe_allow_html=True)
        stage_values = [
            str(x) for x in df.get("stage", pd.Series(dtype=str)).dropna().unique()
            if str(x).strip() and str(x).lower() != "nan"
        ]
        stage_options = ["All"] + sorted(stage_values)
        stage = st.radio(
            "Stage",
            stage_options,
            horizontal=True,
            key=f"{key}_stage",
            label_visibility="collapsed",
        )

    st.markdown("</div>", unsafe_allow_html=True)

    out = df.copy()

    if direction != "All":
        out = out[
            out.direction_label.astype(str).str.upper().eq(direction.upper())
        ]

    if strength != "All":
        out = out[
            out.strength_label.astype(str).str.upper().eq(strength.upper())
        ]

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

        rows.append(
            f"""
<tr>
<td class="row-no">{idx}</td>
<td><div class="stock-cell">{logo(row.get("symbol"))}<span>{str(row.get("symbol")).upper()}</span></div></td>
<td><span class="behaviour-badge {behaviour_class(row)}">{direction.title()} · {strength_label.title()}</span></td>
<td class="{price_class}">{pct(price)}</td>
<td>
  <span class="progress-value">{progress:.1f}%</span>
  <span class="progress-rail"><span class="progress-fill {fill_class}" style="width:{width:.0f}%"></span></span>
</td>
<td><span class="stage-chip">{stage}</span></td>
<td><span class="confirm-chip">{confirmation}</span></td>
<td class="{strength_class}">{'—' if pd.isna(strength_value) else f'{float(strength_value):.0f}'}</td>
<td class="{'breakout-yes' if breakout else 'breakout-no'}">{'YES' if breakout else '—'}</td>
<td class="time-cell">{time_text(row.get("observation_timestamp"), False)}</td>
</tr>
"""
        )

    return (
        '<div class="table-wrap"><table class="sdlq">'
        '<thead><tr>'
        '<th style="width:3%">#</th><th style="width:14%">STOCK</th>'
        '<th style="width:18%">DIRECTION / STRENGTH</th><th style="width:9%">MOMENTUM</th>'
        '<th style="width:15%">STRADDLE PROGRESS</th><th style="width:13%">STAGE</th>'
        '<th style="width:11%">CONFIRMATION</th><th style="width:7%">STRENGTH</th>'
        '<th style="width:6%">BREAKOUT</th><th style="width:7%">TIME</th>'
        '</tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></div>"
    )


def priority_strip(df, key="priority_filter"):
    if df.empty:
        return ""
    st.markdown('<div class="priority-strip"><div class="priority-caption">'
                'PRIORITY RADAR · INDEPENDENT FILTER</div>', unsafe_allow_html=True)
    p1, p2 = st.columns([1.2, 1])
    with p1:
        priority_progress = st.radio(
            "Priority progress",
            ["All", "25%+", "50%+", "70%+", "75%+", "Breakout"],
            horizontal=True,
            key=f"{key}_progress",
            label_visibility="collapsed",
        )
    with p2:
        priority_strength = st.radio(
            "Priority strength",
            ["All", "Strong", "Developing"],
            horizontal=True,
            key=f"{key}_strength",
            label_visibility="collapsed",
        )

    top = df.copy()
    pv = pd.to_numeric(top.get("progress", pd.Series(index=top.index, dtype=float)),
                       errors="coerce").fillna(-1)
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

    top = (
        top.sort_values(
            ["factual_breakout", "strength", "progress"],
            ascending=[False, False, False],
        )
        .head(5)
    )
    if top.empty:
        st.markdown('<div style="font-size:10px;opacity:.78;padding:6px 0">No priority stocks match these priority filters.</div></div>',
                    unsafe_allow_html=True)
        return
    cards = []
    for _, row in top.iterrows():
        progress = float(pd.to_numeric(row.get("progress"), errors="coerce") or 0)
        cards.append(
            f'<div class="priority-card">'
            f'<div class="priority-symbol">{logo(row.get("symbol"))} {str(row.get("symbol")).upper()}</div>'
            f'<div class="priority-meta">{str(row.get("direction_label","—")).title()} · '
            f'{str(row.get("strength_label","—")).title()} · {str(row.get("stage","—"))}</div>'
            f'<div class="priority-progress">{progress:.1f}%'
            f'{" · BREAKOUT" if bool(row.get("factual_breakout",False)) else ""}</div>'
            f'</div>'
        )
    st.markdown(
        '<div style="display:flex;gap:7px;overflow-x:auto">'
        + "".join(cards)
        + "</div></div>",
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

    a, b, c, d = st.columns(4)
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
        '<div style="font-size:9px;color:#7d8797;margin-top:5px">'
        'Selection uses the existing qualified decision record; no new scoring is performed.'
        '</div>',
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
    labels = ["QUALIFIED", "BULLISH", "BEARISH", "STRONG", "BREAKOUT"]
    cols = st.columns(5)
    for col, label, value in zip(cols, labels, values):
        col.markdown(
            f'<div class="kpi"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>'
            f'<div class="kpi-foot">As of {time_text(stamp, False)}</div></div>',
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
# SIDEBAR / NAVIGATION
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="brand-mark" style="width:44px;height:44px;border-radius:11px;'
        'background:#eef2fb;color:#19366f;display:flex;align-items:center;'
        'justify-content:center;font-weight:900">SDL</div>'
        '<div style="font-size:18px;font-weight:850;margin-top:9px">NTIS SDL</div>'
        '<div style="font-size:10px;color:#7b8494;line-height:1.5">'
        'Intraday Straddle Breakout<br>Decision Centre</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:9px;letter-spacing:.13em;font-weight:850;'
        'color:#8b93a3;margin:22px 0 7px">NAVIGATION</div>',
        unsafe_allow_html=True,
    )
    page = st.radio(
        "Navigation",
        ["Decision Board", "Replay", "Inspector", "Historical Evidence", "Settings"],
        label_visibility="collapsed",
        key="page",
    )
    st.markdown(
        '<div style="border-top:1px solid #dfe5ee;margin-top:20px;padding-top:13px;'
        'font-size:9px;color:#7b8494;line-height:1.55">'
        '<b>Preview</b><br>Port 8587<br><br>'
        '<b>Production 8504</b> untouched.<br>'
        'Decision engine remains the existing SDL implementation.</div>',
        unsafe_allow_html=True,
    )

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
    st.markdown(queue_html(visible), unsafe_allow_html=True)

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

st.markdown(
    '<div class="footer"><span>NTIS SDL · Intraday Straddle Breakout Decision Centre</span>'
    '<span>Timestamped data · Preview 8587 · Production 8504 untouched</span></div>',
    unsafe_allow_html=True,
)
