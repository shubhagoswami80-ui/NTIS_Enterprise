from __future__ import annotations

from pathlib import Path
from datetime import datetime
import html

import pandas as pd
import streamlit as st

import config as sdl_config
import pipeline as sdl_pipeline
from config import STATE_JSON
from pipeline import discover_historical_snapshots, process_snapshot
from prediction_engine import build_current_predictions
from source_loader import load_primary_snapshot, parse_observation_timestamp
from storage import load_state

PORT = 8587
BUNDLE_TOLERANCE_SECONDS = 60

st.set_page_config(
    page_title="NTIS SDL – Intraday Decision Centre",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# Exact-reference visual system
# -----------------------------------------------------------------------------
st.markdown(r"""
<style>
:root{
  --navy:#061333; --navy2:#10275c; --purple:#6c35d8; --purple2:#7b42ed;
  --page:#f7f8fc; --card:#ffffff; --ink:#17223d; --muted:#66718a; --line:#e2e6ef;
  --green:#16a05b; --green-bg:#e9f8ef; --green-soft:#d7f1e1;
  --red:#d72f38; --red-bg:#fdecee; --red-soft:#f8d4d7;
  --amber:#e6a117; --amber-bg:#fff6df; --gray:#8a93a5;
}
.stApp{background:var(--page);color:var(--ink)}
.block-container{max-width:1220px;padding:0 20px 86px}
header[data-testid="stHeader"]{background:transparent}
footer{display:none}

/* top reference header */
.sdl-topbar{background:linear-gradient(100deg,#06112f 0%,#07163d 58%,#152b61 100%);color:#fff;min-height:74px;
 margin:0 -20px 14px;padding:10px 24px;display:flex;align-items:center;justify-content:space-between;
 box-shadow:0 4px 16px rgba(6,19,51,.18)}
.sdl-brand-wrap{display:flex;align-items:center;gap:12px;min-width:0}
.sdl-mark{width:47px;height:47px;position:relative;display:flex;align-items:center;justify-content:center;flex:0 0 auto}
.sdl-mark:before{content:"";position:absolute;left:2px;bottom:6px;width:34px;height:25px;border-left:5px solid #9b6aff;border-bottom:5px solid #9b6aff;transform:skewY(-24deg)}
.sdl-mark:after{content:"↗";position:absolute;right:0;top:-2px;color:#ffb51b;font-size:31px;font-weight:900}
.sdl-word{font-size:29px;font-weight:900;letter-spacing:-.04em;line-height:.9}
.sdl-word-sub{font-size:8px;font-weight:800;letter-spacing:.06em;margin-top:4px;white-space:nowrap}
.sdl-divider{height:42px;width:1px;background:rgba(255,255,255,.25);margin:0 4px}
.sdl-product-title{font-size:17px;font-weight:800;line-height:1.05;white-space:nowrap}
.sdl-product-sub{font-size:9px;opacity:.86;margin-top:5px;white-space:nowrap}
.sdl-head-right{display:flex;align-items:center;gap:16px;text-align:left}
.live-status{background:#075f3b;border:1px solid #159a5c;border-radius:999px;padding:6px 12px;font-size:10px;font-weight:900;letter-spacing:.04em}
.head-time{font-size:10px;line-height:1.35;white-space:nowrap}.head-time strong{font-size:11px}.head-processing{color:#33c77b;font-size:9px}
.deploy-btn{background:#101c3a;border:1px solid #5c6680;border-radius:8px;padding:8px 15px;font-size:10px;font-weight:800}

/* compact top control cards */
.control-grid{display:grid;grid-template-columns:1.05fr 1.75fr 1fr;gap:10px;margin-bottom:10px}
.control-card{background:#fff;border:1px solid var(--line);border-radius:9px;padding:11px 12px;min-height:92px;box-shadow:0 2px 8px rgba(20,35,70,.03)}
.control-title{font-size:10px;font-weight:900;color:#18264a;letter-spacing:.03em;margin-bottom:8px}
.control-label{font-size:9px;color:#59657d;margin-bottom:4px}
.fake-input{height:35px;border:1px solid #d7dce7;border-radius:6px;background:#fff;padding:9px 10px;font-size:10px;color:#26324b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.control-row{display:grid;grid-template-columns:1fr 1fr auto;gap:9px;align-items:end}
.ref-note{font-size:8px;color:#6f788b;margin-top:6px}
.mode-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.mode-card{border:1px solid #dce1ea;border-radius:7px;padding:9px 10px;min-height:48px;background:#fff}
.mode-card.active{border-color:#45ae7a;box-shadow:inset 0 0 0 1px #b8e4ca;background:#fbfffc}
.mode-title{font-size:10px;font-weight:900}.mode-sub{font-size:8px;color:#6d7586;margin-top:3px}

/* processing banner */
.process-banner{background:var(--amber-bg);border:1px solid #f3d38a;border-radius:8px;min-height:51px;padding:8px 13px;display:flex;align-items:center;justify-content:space-between;margin-bottom:13px}
.process-left{display:flex;align-items:center;gap:11px}.spinner{width:20px;height:20px;border:3px dotted #d99616;border-radius:50%}
.process-title{font-size:11px;font-weight:900;color:#64470c}.process-sub{font-size:8px;color:#75612f;margin-top:3px}
.process-right{text-align:right;font-size:9px;font-weight:800;color:#6c5320}.process-right span{display:block;color:#d08400;font-weight:700;margin-top:2px}

/* section / table */
.priority-card{background:#fff;border:1px solid #cbd2df;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(20,35,70,.04)}
.section-head{background:linear-gradient(100deg,#061331,#173776);color:#fff;padding:10px 14px;display:flex;justify-content:space-between;align-items:center}
.section-left{display:flex;gap:9px;align-items:center}.star{font-size:20px;color:#ffd33b}.section-title{font-size:12px;font-weight:900}.section-sub{font-size:8px;opacity:.82;margin-top:3px}
.snapshot-pill{background:#322078;border-radius:999px;padding:5px 10px;font-size:8px;white-space:nowrap}
.sdl-table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:9px;background:#fff}
.sdl-table th{height:31px;text-align:left;padding:6px 8px;color:#5e687c;font-size:8px;font-weight:900;border-bottom:1px solid #dfe3eb;letter-spacing:.02em}
.sdl-table td{height:39px;padding:6px 8px;border-bottom:1px solid #e4e7ed;color:#25304a;vertical-align:middle}
.sdl-table th:nth-child(1){width:4%}.sdl-table th:nth-child(2){width:9%}.sdl-table th:nth-child(3){width:24%}.sdl-table th:nth-child(4){width:9%}.sdl-table th:nth-child(5){width:12%}.sdl-table th:nth-child(6){width:10%}.sdl-table th:nth-child(7){width:12%}.sdl-table th:nth-child(8){width:7%}.sdl-table th:nth-child(9){width:7%}.sdl-table th:nth-child(10){width:10%}
.decision-badge,.stage-badge,.confirm-badge,.strength-badge{display:inline-block;border-radius:5px;padding:4px 7px;font-weight:900;white-space:nowrap}
.bull{color:#08713a;background:var(--green-bg);border:1px solid #c6e9d4}.bear{color:#9b1e27;background:var(--red-bg);border:1px solid #f2c9cd}.wait{color:#5d687c;background:#f1f3f7;border:1px solid #dfe3ea}.dev{color:#93640a;background:#fff5dd;border:1px solid #f1dca7}
.price-up{color:#087b40;font-weight:900}.price-down{color:#d12632;font-weight:900}.next-level{color:#687188;font-weight:700}
.priority-link{text-align:center;color:#6b39d8;font-weight:900;font-size:9px;padding:10px;cursor:pointer}

/* filters */
.filter-bar{background:#fff;border:1px solid var(--line);border-radius:9px;padding:8px 10px;margin:10px 0;display:flex;align-items:center;justify-content:space-between;gap:10px}
.filter-title{font-size:9px;font-weight:900;color:#18264a;margin-bottom:6px}.filter-buttons{display:flex;gap:7px;flex-wrap:wrap}
.filter-pill{border:1px solid #d9dee8;border-radius:6px;background:#fff;padding:6px 13px;font-size:9px;color:#4c566c}.filter-pill.active{background:#7135d8;color:#fff;border-color:#7135d8;font-weight:900}
.clear-pill{border:1px solid #d9dee8;border-radius:6px;padding:6px 12px;font-size:9px;color:#4c566c;background:#fff}

/* inspector */
.inspector{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-top:4px}
.inspector-head{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #edf0f4;padding-bottom:8px}
.inspector-title{font-size:12px;font-weight:900;color:#18264a}.inspector-sub{font-size:8px;color:#6b7487;margin-top:3px}.chevron{width:35px;height:31px;background:#6f35d8;color:#fff;border-radius:7px;text-align:center;padding-top:6px;font-size:18px}
.inspector-select{margin:10px 0}.select-label{font-size:8px;color:#536079;font-weight:800;margin-bottom:4px}
.select-box{height:35px;border:1px solid #dce1e9;border-radius:6px;padding:9px 10px;font-size:10px;background:#fff}
.decision-hero{border:1px solid #8fd3aa;background:linear-gradient(90deg,#e8f8ee,#f3fbf6);border-radius:9px;padding:10px 12px;display:flex;justify-content:space-between;align-items:center}.hero-decision{font-size:15px;font-weight:950;color:#0a743b}.hero-meta{font-size:8px;color:#4b7860;margin-top:4px}.hero-icon{font-size:23px;color:#17a05c}
.metric-grid{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid #e1e5ec;border-radius:7px;overflow:hidden;margin-top:10px}.metric{padding:8px;text-align:center;border-right:1px solid #e1e5ec}.metric:last-child{border-right:0}.metric-label{font-size:7px;color:#566177;font-weight:900}.metric-value{font-size:17px;color:#18223d;font-weight:900;margin-top:5px}.metric-value.green{color:#15964f}
.inspector-grid{display:grid;grid-template-columns:1.1fr .8fr .75fr .95fr;gap:10px;margin-top:10px}.mini-card{border:1px solid #e0e4eb;border-radius:7px;padding:10px;min-height:170px}.mini-title{font-size:9px;font-weight:900;color:#1b294d;margin-bottom:10px}.progress-line{position:relative;height:35px;margin:8px 5px 10px}.progress-line:before{content:"";position:absolute;left:5%;right:5%;top:12px;height:2px;background:#d5dbe5}.dot{position:absolute;top:5px;width:15px;height:15px;border-radius:50%;background:#fff;border:2px solid #d2d8e2}.dot.done{background:#4cb878;border-color:#4cb878}.dot.current{border-color:#1b9a57;box-shadow:0 0 0 3px #e0f4e7}.p25{left:3%}.p50{left:32%}.p75{left:62%}.p100{left:91%}.progress-labels{display:flex;justify-content:space-between;font-size:7px;color:#4c566b}.next-line{font-size:9px;margin-top:9px}.next-line b{font-weight:900}.factor-row{display:flex;justify-content:space-between;font-size:8px;padding:4px 0}.factor-ok{color:#15924d;font-weight:800}.factor-neutral{color:#7b8495}.interpret{font-size:9px;color:#4e596e;line-height:1.45}.watch{border-top:1px solid #e5e8ee;margin-top:10px;padding-top:8px;font-size:8px;color:#4f596b}.watch b{color:#1a2747}

/* footer */
.footer-grid{display:grid;grid-template-columns:1fr 1fr 1fr;align-items:center;border-top:1px solid #e2e6ee;margin-top:11px;padding:12px 5px 9px;color:#566177;font-size:8px}.footer-left{font-weight:900;color:#243150}.footer-center{text-align:center}.footer-right{text-align:right}
.bottom-nav{position:fixed;z-index:999;bottom:0;left:0;right:0;height:58px;background:#061333;color:#fff;display:flex;justify-content:space-around;align-items:center;box-shadow:0 -5px 16px rgba(5,18,47,.18)}
.nav-item{text-align:center;font-size:8px;opacity:.9;min-width:100px}.nav-icon{font-size:18px;line-height:1.05}.nav-item.active{color:#8e5cff}.nav-item.active .nav-icon{font-weight:900}

/* hide Streamlit chrome that would make this look unlike reference */
div[data-testid="stToolbar"]{display:none}div[data-testid="stDecoration"]{display:none}
button[kind="secondary"]{border-radius:7px}
@media(max-width:850px){
 .block-container{padding:0 10px 76px}.sdl-topbar{margin:0 -10px 9px;padding:8px 11px;min-height:66px}
 .sdl-product-title{font-size:13px}.sdl-product-sub{font-size:7px}.sdl-divider{height:34px}.sdl-word{font-size:23px}.sdl-word-sub{font-size:6px}.sdl-mark{width:39px}.sdl-head-right{gap:7px}.head-time{display:none}.deploy-btn{display:none}
 .control-grid{grid-template-columns:1fr;gap:7px}.control-card{min-height:auto}.control-grid .control-card:nth-child(3){display:block}
 .sdl-table{font-size:8px;min-width:900px}.priority-card{overflow-x:auto}.section-head{position:relative}
 .filter-bar{align-items:flex-start;flex-direction:column}.metric-grid{grid-template-columns:repeat(5,150px);overflow-x:auto}.inspector-grid{grid-template-columns:1fr 1fr}.footer-grid{grid-template-columns:1fr;text-align:center;gap:7px}.footer-right{text-align:center}
 .nav-item{min-width:50px}
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Backend adapters: same frozen SDL engine, no duplicated decision calculations
# -----------------------------------------------------------------------------
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
        paths = [Path(p) for p in discover_historical_snapshots(trading_date)]
    except Exception:
        return []
    vals = [(p, source_ts(p)) for p in paths]
    vals = [(p, t) for p, t in vals if pd.notna(t)]
    vals.sort(key=lambda x: (x[1], str(x[0]).lower()))
    return [p for p, _ in vals]


def bundle_files(files: list[Path]) -> list[list[Path]]:
    if not files:
        return []
    out = [[files[0]]]
    for p in files[1:]:
        prev = source_ts(out[-1][-1]); cur = source_ts(p)
        if pd.notna(prev) and pd.notna(cur) and (cur - prev).total_seconds() <= BUNDLE_TOLERANCE_SECONDS:
            out[-1].append(p)
        else:
            out.append([p])
    return out


def frozen_base_from_snapshot(df: pd.DataFrame) -> dict:
    if df is None or df.empty or "Symbol" not in df.columns:
        return {}
    result = {}
    for _, r in df.drop_duplicates("Symbol").iterrows():
        symbol = str(r.get("Symbol", "")).strip().upper()
        op = pd.to_numeric(r.get("daily_open_reference"), errors="coerce")
        premium = pd.to_numeric(r.get("opening_straddle_premium"), errors="coerce")
        if symbol and pd.notna(op) and pd.notna(premium) and premium > 0:
            result[symbol] = {"open_price": float(op), "opening_straddle_premium": float(premium)}
    return result


def opening_base_from_first_file(path: Path) -> dict:
    try:
        df, _ = load_primary_snapshot(path, source_ts(path))
    except Exception:
        return {}
    if df is None or df.empty:
        return {}
    out = df.copy()
    if "Symbol" not in out.columns:
        return {}
    if "Open" in out.columns:
        out["daily_open_reference"] = pd.to_numeric(out["Open"], errors="coerce")
    if "ATM Straddle %" in out.columns:
        pct = pd.to_numeric(out["ATM Straddle %"], errors="coerce")
    else:
        pct = pd.Series(index=out.index, dtype=float)
    result = {}
    for i, r in out.iterrows():
        symbol = str(r.get("Symbol", "")).strip().upper()
        op = pd.to_numeric(r.get("daily_open_reference"), errors="coerce")
        p = pd.to_numeric(pct.loc[i], errors="coerce")
        if symbol and pd.notna(op) and pd.notna(p) and p > 0:
            result[symbol] = {"open_price": float(op), "opening_straddle_premium": float(op * p / 100.0)}
    return result


def snapshot_predictions(path: Path, ts: pd.Timestamp | None, base: dict | None = None) -> pd.DataFrame:
    try:
        raw, observed = load_primary_snapshot(path, ts)
    except Exception:
        return pd.DataFrame()
    if raw is None or raw.empty:
        return pd.DataFrame()
    raw = raw.copy()
    if "Symbol" not in raw.columns:
        return pd.DataFrame()
    if "daily_open_reference" not in raw.columns and "Open" in raw.columns:
        raw["daily_open_reference"] = pd.to_numeric(raw["Open"], errors="coerce")
    if "ATM Straddle %" in raw.columns and "opening_straddle_premium" not in raw.columns:
        # Only used when replaying a date with no persisted base.
        raw["opening_straddle_premium"] = pd.to_numeric(raw["daily_open_reference"], errors="coerce") * pd.to_numeric(raw["ATM Straddle %"], errors="coerce") / 100.0
    if base is None or not base:
        base = frozen_base_from_snapshot(raw)
    # Same frozen SDL prediction engine used by production app.
    try:
        return build_current_predictions(raw, base)
    except Exception:
        return pd.DataFrame()


def current_state_predictions(path: Path, ts: pd.Timestamp | None) -> pd.DataFrame:
    state = load_state(STATE_JSON)
    trading_date = ts.date().isoformat() if pd.notna(ts) else pd.Timestamp.now().date().isoformat()
    base = state.get("daily_opening_straddles", {}).get(trading_date, {})
    if base:
        return snapshot_predictions(path, ts, base)
    # Safe fallback for preview only; does not write state.
    files = source_files(trading_date)
    return snapshot_predictions(path, ts, opening_base_from_first_file(files[0]) if files else None)


def filtered(df: pd.DataFrame, selected: str) -> pd.DataFrame:
    if df.empty:
        return df
    if selected == "Bullish": return df[df.direction_label.eq("BULLISH")]
    if selected == "Bearish": return df[df.direction_label.eq("BEARISH")]
    if selected == "Developing": return df[df.strength_label.eq("DEVELOPING")]
    if selected == "Wait": return df[df.strength_label.str.contains("WAIT", na=False)]
    if selected == "Approaching": return df[df.progress.ge(75) & df.progress.lt(100)]
    if selected == "Breakout": return df[df.factual_breakout]
    return df


def decision_badge(row) -> tuple[str, str]:
    d = str(row.get("direction_label", ""))
    s = str(row.get("strength_label", ""))
    if "WAIT" in s: return "WAIT", "wait"
    if d == "BULLISH": return "BULLISH", "bull"
    return "BEARISH", "bear"


def next_level(progress: float) -> str:
    if progress >= 100: return "BREAKOUT"
    if progress >= 75: return "NEXT 100%"
    if progress >= 50: return "NEXT 75%"
    return "NEXT 50%"


def fmt_num(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "—"


def render_table(df: pd.DataFrame, limit: int | None = None):
    if df.empty:
        st.info("No qualified decision candidates.")
        return
    view = df.head(limit) if limit else df
    rows=[]
    for i, (_, r) in enumerate(view.iterrows(), 1):
        decision, cls = decision_badge(r)
        stage = str(r.get("stage", "—"))
        strength_label = str(r.get("strength_label", "—"))
        strength_cls = "bull" if strength_label in {"STRONG", "SUPPORTED"} else "dev" if strength_label == "DEVELOPING" else "wait"
        p = float(r.get("signed_price_move_pct", 0) or 0)
        rows.append(f'''<tr>
<td>{i}</td><td><b>{html.escape(str(r.get("symbol","")))}</b></td>
<td><span class="decision-badge {cls}">{html.escape(decision)} · {html.escape(stage)} · {html.escape(strength_label)}</span></td>
<td class="{'price-up' if p>=0 else 'price-down'}">{p:+.2f}%</td>
<td><b>{float(r.get("progress",0) or 0):.1f}%</b></td>
<td><span class="stage-badge {cls}">{html.escape(stage)}</span></td>
<td><span class="confirm-badge {strength_cls}">{html.escape(strength_label)}</span></td>
<td><span class="strength-badge {strength_cls}">{float(r.get("strength",0) or 0):.0f}</span></td>
<td>{'YES' if bool(r.get('factual_breakout',False)) else '—'}</td>
<td><span class="next-level">{next_level(float(r.get('progress',0) or 0))}</span></td>
</tr>''')
    st.markdown('''<div class="priority-card"><div style="overflow-x:auto"><table class="sdl-table"><thead><tr><th>#</th><th>SYMBOL</th><th>DECISION</th><th>PRICE MOVE</th><th>STRADDLE MOVE</th><th>STAGE</th><th>CONFIRMATION</th><th>STRENGTH</th><th>BREAKOUT</th><th>NEXT LEVEL</th></tr></thead><tbody>''' + ''.join(rows) + '</tbody></table></div></div>', unsafe_allow_html=True)


def inspector(df: pd.DataFrame):
    st.markdown('<div class="inspector">', unsafe_allow_html=True)
    st.markdown('''<div class="inspector-head"><div><div class="inspector-title">◫ &nbsp; DECISION INSPECTOR</div><div class="inspector-sub">Inspect the evidence behind a selected decision</div></div><div class="chevron">⌄</div></div>''', unsafe_allow_html=True)
    if df.empty:
        st.info("Inspector becomes available when a qualified decision is present.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    symbols=df.symbol.astype(str).tolist()
    selected=st.selectbox("Selected Stock", symbols, label_visibility="collapsed")
    row=df[df.symbol.eq(selected)].iloc[0]
    d, cls = decision_badge(row)
    direction_word = "BULLISH" if d == "BULLISH" else "BEARISH"
    progress=float(row.get("progress",0) or 0); move=float(row.get("signed_price_move_pct",0) or 0)
    current=float(row.get("current_price",0) or 0); opening=float(row.get("opening_price",0) or 0); premium=float(row.get("frozen_straddle",0) or 0)
    upper=opening+premium; lower=opening-premium
    st.markdown(f'''<div class="decision-hero"><div><div class="hero-decision {'' if cls=='bull' else ''}">{direction_word} · {html.escape(str(row.get('stage','')))} · {html.escape(str(row.get('strength_label','')))}</div><div class="hero-meta">Progress: {progress:.1f}% of frozen S · Price: {move:+.2f}% · Frozen S: ₹{premium:,.2f}</div></div><div class="hero-icon">↗</div></div>''', unsafe_allow_html=True)
    st.markdown(f'''<div class="metric-grid"><div class="metric"><div class="metric-label">OPEN</div><div class="metric-value">{fmt_num(opening)}</div></div><div class="metric"><div class="metric-label">CURRENT</div><div class="metric-value green">{fmt_num(current)}</div></div><div class="metric"><div class="metric-label">FROZEN S</div><div class="metric-value">{fmt_num(premium)}</div></div><div class="metric"><div class="metric-label">UPPER (S+S)</div><div class="metric-value">{fmt_num(upper)}</div></div><div class="metric"><div class="metric-label">LOWER (S−S)</div><div class="metric-value">{fmt_num(lower)}</div></div></div>''', unsafe_allow_html=True)

    factors=[]
    for f in row.get("factors",[]) or []:
        factors.append((str(f.name),str(f.label),str(f.state)))
    factor_html=''
    labels={"SUPPORT":"factor-ok","NEUTRAL":"factor-neutral","CONTRADICT":"factor-neutral","UNAVAILABLE":"factor-neutral"}
    for _, label, state in factors:
        shown = {"SUPPORT":"Strong Build-up","CONTRADICT":"Contradicting","NEUTRAL":"Neutral","UNAVAILABLE":"Unavailable"}.get(state,state.title())
        factor_html += f'<div class="factor-row"><span>{html.escape(label)}</span><span class="{labels.get(state,"factor-neutral")}">{html.escape(shown)}</span></div>'
    if not factor_html: factor_html='<div class="factor-row"><span>Confirmation factors</span><span class="factor-neutral">Not available</span></div>'

    pos=min(100,max(0,progress));
    st.markdown(f'''<div class="inspector-grid"><div class="mini-card"><div class="mini-title">STRADDLE PROGRESSION</div><div class="progress-line"><span class="dot done p25"></span><span class="dot {"current" if 25<=pos<50 else "done" if pos>=50 else ""} p50"></span><span class="dot {"current" if 50<=pos<75 else "done" if pos>=75 else ""} p75"></span><span class="dot {"current" if pos>=75 else ""} p100"></span></div><div class="progress-labels"><span>25%</span><span>50%<br><b>{progress:.1f}%</b></span><span>75%</span><span>100%</span></div><div class="next-line"><b>Next Level:</b> {next_level(progress)}</div><div class="next-line"><b>Approach Price:</b> ₹{fmt_num(upper if direction_word=='BULLISH' else lower)}</div><div class="next-line"><b>Breakout Level (100%):</b> ₹{fmt_num(upper if direction_word=='BULLISH' else lower)}</div></div><div class="mini-card"><div class="mini-title">PRICE MOVEMENT</div><div class="next-line">Current Move</div><div style="font-size:15px;font-weight:900;color:{'#15964f' if move>=0 else '#d12632'};margin:4px 0 9px">{move:+.2f}%</div><div class="next-line">Day Range</div><div class="progress-line"><span class="dot current" style="left:{min(95,max(5,50 + move*5))}%"></span></div><div class="progress-labels"><span>₹{fmt_num(lower)}</span><span>₹{fmt_num(upper)}</span></div><div class="next-line">Position in Range <b style="float:right">{min(100,max(0,50+move*5)):.1f}%</b></div></div><div class="mini-card"><div class="mini-title">CONFIRMATION FACTORS</div>{factor_html}</div><div class="mini-card"><div class="mini-title">INTERPRETATION</div><div class="interpret">✓ &nbsp; Price is {"above" if move>=0 else "below"} the opening reference with {str(row.get('strength_label','')).lower()} confirmation from the available evidence. Straddle is at {progress:.1f}% progression. Upside bias remains {"positive" if direction_word=='BULLISH' else "negative"} for the next decision level.</div><div class="watch"><b>Watch Next</b><span style="float:right">{next_level(progress)}</span><br><b>Key Level</b><span style="float:right">₹{fmt_num(upper if direction_word=='BULLISH' else lower)}</span></div></div></div>''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Admin source setting: present for admin, not part of normal decision flow
# -----------------------------------------------------------------------------
if "sdl_source_root" not in st.session_state:
    st.session_state["sdl_source_root"] = str(getattr(sdl_config, "INTRADAY_SOURCE_ROOT", ""))

with st.expander("⚙  Admin Settings", expanded=False):
    st.caption("Administrator-only. Change the source data folder without changing SDL decision logic or runtime log location.")
    new_root = st.text_input("Source data folder", value=st.session_state["sdl_source_root"], label_visibility="collapsed")
    if st.button("Save source folder", type="secondary"):
        root=Path(new_root).expanduser().resolve()
        st.session_state["sdl_source_root"]=str(root)
        sdl_config.INTRADAY_SOURCE_ROOT=root
        sdl_pipeline.INTRADAY_SOURCE_ROOT=root
        st.success("Source folder updated for this dashboard session.")

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
now=pd.Timestamp.now()
today=now.date().isoformat()
files=source_files(today)
bundles=bundle_files(files)
live_path=max(files,key=source_ts) if files else None
live_ts=source_ts(live_path) if live_path else pd.NaT

st.markdown(f'''<div class="sdl-topbar"><div class="sdl-brand-wrap"><div class="sdl-mark"></div><div><div class="sdl-word">SDL</div><div class="sdl-word-sub">STRADDLE BREAKOUT DECISION</div></div><div class="sdl-divider"></div><div><div class="sdl-product-title">NTIS SDL – Intraday Decision Centre</div><div class="sdl-product-sub">Live Decision Queue &amp; Historical Replay</div></div></div><div class="sdl-head-right"><div class="live-status">● LIVE</div><div class="head-time"><strong>As of {now.strftime('%I:%M:%S %p')}</strong><br>{now.strftime('%d-%b-%Y')}<br><span class="head-processing">◌ Processing automatically</span></div><div class="deploy-btn">Deploy</div><div style="font-size:19px">⋮</div></div></div>''', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Controls: reference layout
# -----------------------------------------------------------------------------
replay_mode = st.session_state.get("preview_mode", "LIVE")
selected_date = st.session_state.get("preview_date", today)

# Use native controls but style/contain them inside exact reference cards.
c1,c2,c3=st.columns([1.05,1.75,1.0], gap="small")
with c1:
    st.markdown('<div class="control-card"><div class="control-title">SOURCE DATA</div><div class="control-label">Active Source Folder</div>',unsafe_allow_html=True)
    st.text_input("source",value=st.session_state["sdl_source_root"],key="source_top",label_visibility="collapsed")
    st.markdown('<div class="ref-note">Change source in Settings ⚙</div></div>',unsafe_allow_html=True)
with c2:
    st.markdown('<div class="control-card"><div class="control-title">HISTORICAL REPLAY</div>',unsafe_allow_html=True)
    dcol,tcol,bcol=st.columns([1,1,0.72])
    with dcol:
        day=st.date_input("Select Trading Day",value=pd.Timestamp(selected_date).date(),label_visibility="visible")
    day_files=source_files(str(day))
    day_times=[source_ts(p) for p in day_files]
    with tcol:
        time_options=[t.strftime('%H:%M:%S') for t in day_times if pd.notna(t)]
        choice=st.selectbox("Select Snapshot Time",time_options or ["No snapshots"],label_visibility="visible")
    with bcol:
        st.write("")
        if st.button("Load Replay",type="primary",use_container_width=True):
            st.session_state["preview_mode"]="REPLAY"
            st.session_state["preview_replay_day"]=str(day)
            st.session_state["preview_replay_time"]=choice
            st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)
with c3:
    st.markdown('<div class="control-card"><div class="control-title">DISPLAY MODE</div>',unsafe_allow_html=True)
    mode=st.radio("mode",["LIVE","REPLAY"],index=0 if replay_mode=="LIVE" else 1,horizontal=True,label_visibility="collapsed")
    if mode != replay_mode:
        st.session_state["preview_mode"]=mode
        if mode=="LIVE": st.session_state.pop("preview_replay_time",None)
        st.rerun()
    st.markdown(f'<div class="mode-grid"><div class="mode-card {"active" if mode=="LIVE" else ""}"><div class="mode-title">🟢 LIVE</div><div class="mode-sub">Current State</div></div><div class="mode-card {"active" if mode=="REPLAY" else ""}"><div class="mode-title">○ REPLAY</div><div class="mode-sub">Historical Snapshot</div></div></div></div>',unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Automatic evidence processing: preserve previous state and process one bundle
# at a time so the UI remains responsive.
# -----------------------------------------------------------------------------
state=load_state(STATE_JSON)
last_ts=pd.to_datetime(state.get("last_observation_timestamp"),errors="coerce")
pending=[]
for b in bundles:
    ts=source_ts(b[-1])
    if pd.notna(ts) and (pd.isna(last_ts) or ts>last_ts):
        pending.append((ts,b))
if pending and st.session_state.get("preview_auto",True):
    process_ts, process_group = pending[0]
    # Do not process again if the production state already moved while this page reran.
    if st.session_state.get("preview_processing") != process_ts.isoformat():
        st.session_state["preview_processing"] = process_ts.isoformat()
        try:
            process_snapshot(process_group[-1], process_ts)
        except Exception:
            pass
        st.session_state.pop("preview_processing",None)
        st.rerun()

# Determine display snapshot.
if mode=="REPLAY" and st.session_state.get("preview_replay_time"):
    replay_day=st.session_state.get("preview_replay_day",today)
    replay_files=source_files(replay_day)
    target_time=st.session_state["preview_replay_time"]
    replay_path=next((p for p in replay_files if source_ts(p).strftime('%H:%M:%S')==target_time),None)
    display_path=replay_path
    display_ts=source_ts(replay_path) if replay_path else pd.NaT
    display_df=current_state_predictions(display_path,display_ts) if display_path else pd.DataFrame()
else:
    display_path=live_path; display_ts=live_ts
    display_df=current_state_predictions(display_path,display_ts) if display_path else pd.DataFrame()

# Processing banner always communicates the state of the system without adding another decision table.
last_update=display_ts.strftime('%I:%M:%S %p') if pd.notna(display_ts) else '—'
processing_text = 'Processing evidence bundle…' if pending else 'Evidence processing is up to date.'
st.markdown(f'''<div class="process-banner"><div class="process-left"><div class="spinner"></div><div><div class="process-title">{processing_text}</div><div class="process-sub">Please wait while we prepare the latest market evidence and decisions.</div></div></div><div class="process-right">Last updated: {last_update}<span>{"This will update automatically" if mode=="LIVE" else "Historical snapshot — replay only"}</span></div></div>''',unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# TOP PRIORITY NOW
# -----------------------------------------------------------------------------
priority=display_df.sort_values(["factual_breakout","strength","progress"],ascending=[False,False,False]) if not display_df.empty else display_df
st.markdown(f'''<div class="priority-card"><div class="section-head"><div class="section-left"><div class="star">★</div><div><div class="section-title">TOP PRIORITY NOW</div><div class="section-sub">Highest opportunity – right now</div></div></div><div class="snapshot-pill">Snapshot: {display_ts.strftime('%d-%b-%Y %I:%M:%S %p') if pd.notna(display_ts) else '—'}</div></div></div>''',unsafe_allow_html=True)
render_table(priority,5)
if not priority.empty:
    st.markdown('<div class="priority-link">View full Live Decision Queue &nbsp;›</div>',unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Full queue filter
# -----------------------------------------------------------------------------
if "preview_filter" not in st.session_state: st.session_state["preview_filter"]="All"
fc=st.container()
with fc:
    st.markdown('<div class="filter-bar"><div><div class="filter-title">FILTER BY DECISION STATE <span style="font-weight:500;color:#7a8293">(Replay / Live Queue)</span></div></div></div>',unsafe_allow_html=True)
    f=st.radio("decision filter",["All","Bullish","Bearish","Developing","Wait","Approaching","Breakout"],index=["All","Bullish","Bearish","Developing","Wait","Approaching","Breakout"].index(st.session_state["preview_filter"]),horizontal=True,label_visibility="collapsed")
    if f != st.session_state["preview_filter"]:
        st.session_state["preview_filter"]=f
    filtered_df=filtered(display_df,f)

# Keep full queue available, but below the compact priority presentation.
with st.expander("View full Live Decision Queue", expanded=False):
    render_table(filtered_df)

# -----------------------------------------------------------------------------
# Decision Inspector
# -----------------------------------------------------------------------------
inspector(filtered_df if not filtered_df.empty else display_df)

# -----------------------------------------------------------------------------
# Footer + mobile navigation
# -----------------------------------------------------------------------------
st.markdown('''<div class="footer-grid"><div class="footer-left">⚙ SETTINGS<br><span style="font-weight:500;color:#727b8c">Configure source data folder</span></div><div class="footer-center">© 2026 NTIS SDL – Straddle Breakout Decision<br>All rights reserved</div><div class="footer-right">Data updates automatically<br>when new evidence is available &nbsp; ◉</div></div>''',unsafe_allow_html=True)
st.markdown('''<div class="bottom-nav"><div class="nav-item active"><div class="nav-icon">⌂</div>Live Queue</div><div class="nav-item"><div class="nav-icon">☆</div>Top Priority</div><div class="nav-item"><div class="nav-icon">◔</div>Replay</div><div class="nav-item"><div class="nav-icon">⌕</div>Inspector</div><div class="nav-item"><div class="nav-icon">⚙</div>Settings</div></div>''',unsafe_allow_html=True)
