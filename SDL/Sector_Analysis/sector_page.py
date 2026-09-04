from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd
import streamlit as st

from .sector_data_store import read_result, read_status
from .sector_news_engine import classify_news_feed
from .sector_rotation_engine import rank_stock_opportunities


def _worker_running(package_dir: Path) -> bool:
    status = read_status(package_dir)
    return str(status.get("status", "")).upper() == "RUNNING"


def _start_worker(source_root: Path, package_dir: Path) -> None:
    if _worker_running(package_dir):
        return
    worker = package_dir / "sector_worker.py"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [sys.executable, str(worker), "--source-root", str(source_root)],
        cwd=str(package_dir.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )


def _status_block(package_dir: Path) -> dict:
    status = read_status(package_dir)
    state = str(status.get("status", "")).upper()
    if state == "RUNNING":
        pct = float(status.get("progress", 0))
        st.progress(min(max(pct / 100.0, 0.0), 1.0), text=str(status.get("message", "Sector processor working…")))
        st.caption(f"BACKGROUND · {status.get('stage','WORKING')} · {status.get('files_done','—')}/{status.get('files_total','—')} files · {status.get('snapshots','—')} snapshots")
    elif state == "ERROR":
        st.error(f"Sector background processor error: {status.get('error','unknown error')}")
    return status


def _num(v):
    try:
        x = float(v)
        return x if pd.notna(x) else None
    except Exception:
        return None


def _fmt(v, suffix="", sign=False, digits=1):
    x = _num(v)
    if x is None:
        return "—"
    return f"{x:+.{digits}f}{suffix}" if sign else f"{x:.{digits}f}{suffix}"


def _delta(traj, n):
    vals = [_num(v) for v in (traj or [])]
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return None
    vals = vals[-n:]
    return vals[-1] - vals[0] if len(vals) >= 2 else None


def _direction(item):
    return str(item.get("direction", "NEUTRAL")).upper()


def _direction_label(direction):
    return {"INTO": "ROTATING IN", "OUT": "ROTATING OUT", "NEUTRAL": "NEUTRAL"}.get(str(direction).upper(), str(direction).upper())


def _bias_class(direction):
    return "into" if direction == "INTO" else "out" if direction == "OUT" else "neutral"


def _participation(item):
    states = item.get("evidence_states") or {}
    breadth = str(states.get("breadth", "NEUTRAL")).upper()
    volume = str(states.get("volume", "NEUTRAL")).upper()
    if breadth == "SUPPORTING" and volume == "SUPPORTING":
        return "BROAD · SUPPORTING"
    if breadth == "CONFLICTING" and volume == "CONFLICTING":
        return "WEAK · CONFLICTING"
    return "MIXED"


def _read_class(status):
    s = str(status or "NEUTRAL").upper()
    return "support" if s == "SUPPORTING" else "conflict" if s == "CONFLICTING" else "neutral"


def _read_icon(status):
    return {"SUPPORTING": "▲", "CONFLICTING": "▼", "FLAT": "→", "LIMITED": "?", "NEUTRAL": "—"}.get(str(status or "NEUTRAL").upper(), "—")


def _meter_html(score, status, label, detail=""):
    x = _num(score)
    stt = str(status or "NEUTRAL").upper()
    if x is None:
        return f"<div class='meter-row'><div class='meter-name'>{label}</div><div class='meter-track'><span class='meter-na'></span></div><div class='meter-read neutral'>? DATA N/A</div></div>"
    # Convert a directional signed/percent metric to a readable magnitude. This is a visual cue, not a normalized score.
    width = min(100.0, max(8.0, abs(x) * 2.0))
    cls = _read_class(stt)
    icon = _read_icon(stt)
    extra = f"<span class='meter-detail'>{detail}</span>" if detail else ""
    return f"<div class='meter-row'><div class='meter-name'>{label}</div><div class='meter-track'><span class='meter-fill {cls}' style='width:{width:.1f}%'></span></div><div class='meter-read {cls}'>{icon} {stt.replace('_',' ')} {extra}</div></div>"


def _evidence_rows(item):
    states = item.get("evidence_states") or {}
    return [
        ("RELATIVE LEADERSHIP", states.get("relative"), item.get("relative_strength"), _fmt(item.get("relative_strength"))),
        ("LEADERSHIP TRAJECTORY", states.get("leadership"), item.get("rank_slope"), _fmt(item.get("rank_slope"), sign=True)),
        ("PRICE", states.get("price"), item.get("price_delta_3"), _fmt(item.get("price_delta_3"), "%", True)),
        ("BREADTH", states.get("breadth"), item.get("breadth_delta_3"), _fmt(item.get("breadth_delta_3"), " pp", True)),
        ("VOLUME", states.get("volume"), item.get("volume_delta_3"), _fmt(item.get("volume_delta_3"), "%", True)),
        ("OI", states.get("oi"), item.get("oi_delta_3"), _fmt(item.get("oi_delta_3"), "%", True)),
        ("PERSISTENCE", states.get("persistence"), item.get("persistence"), _fmt(item.get("persistence"), "%")),
    ]


def _change_line(label, current, delta, positive_good=True, unit="%"):
    cur, d = _num(current), _num(delta)
    if cur is None or d is None:
        return f"<div class='change-row'><div class='change-label'>{label}</div><div class='change-track'><span class='na-text'>DATA NOT AVAILABLE</span></div><div class='change-value'>?</div></div>"
    start = cur - d
    good = d > 0 if positive_good else d < 0
    cls = "good" if good else "bad" if abs(d) > 0.01 else "flat"
    # Centered change meter; the bar represents change magnitude, while color represents interpretation.
    width = min(46.0, max(3.0, abs(d) / max(1.0, abs(cur) + abs(d)) * 46.0))
    side = "right" if d >= 0 else "left"
    if side == "right":
        fill = f"<span class='change-fill {cls}' style='left:50%;width:{width:.1f}%'></span>"
    else:
        fill = f"<span class='change-fill {cls}' style='left:{50-width:.1f}%;width:{width:.1f}%'></span>"
    return f"<div class='change-row'><div class='change-label'>{label}</div><div class='change-track'>{fill}<span class='change-zero'></span></div><div class='change-value'><b>{start:+.1f}{unit}</b> → <b>{cur:+.1f}{unit}</b><span class='{cls}'>{d:+.1f} pp</span></div></div>"


def _options_block(item):
    return "".join([
        _change_line("PE OI change", item.get("pe_oi_change"), item.get("pe_oi_delta_3"), True),
        _change_line("CE OI change", item.get("ce_oi_change"), item.get("ce_oi_delta_3"), False),
        _change_line("PE − CE OI change", item.get("pe_ce_oi_change"), item.get("pe_ce_oi_delta_3"), True),
    ])


def _opp_class(level):
    s = str(level or "").upper()
    if "HIGH" in s: return "opp-high"
    if "DEVELOPING" in s: return "opp-developing"
    if "EARLY" in s: return "opp-early"
    if "LOW" in s: return "opp-low"
    return "opp-na"


def _trade_side(item, horizon="INTRADAY"):
    direction = _direction(item)
    setup = str(item.get("intraday_type" if horizon == "INTRADAY" else "swing_type", "")).upper()
    if direction == "NEUTRAL": return "NO CLEAN SIDE"
    if "REVERSAL" in setup or "RECOVERY" in setup: return "LONG WATCH" if direction == "INTO" else "SHORT WATCH"
    if "BREAKDOWN" in setup or "WEAKNESS" in setup or "DETERIORATION" in setup: return "SHORT SIDE"
    if "MOMENTUM" in setup or "LEADERSHIP" in setup or direction == "INTO": return "LONG SIDE"
    return "SHORT SIDE" if direction == "OUT" else "NO CLEAN SIDE"


def _action_read(item, horizon="INTRADAY"):
    type_key = "intraday_type" if horizon == "INTRADAY" else "swing_type"
    level_key = "intraday_opportunity" if horizon == "INTRADAY" else "swing_opportunity"
    setup = str(item.get(type_key, "")).upper()
    level = str(item.get(level_key, "")).upper()
    confirmation = str(item.get("confirmation_quality", "LIMITED")).upper()
    side = _trade_side(item, horizon)
    if side == "NO CLEAN SIDE": return "NO CLEAN EDGE"
    if confirmation == "CONFLICTED": return f"{side} → WAIT FOR RESOLUTION"
    if "RELATIVE LEADER ONLY" in setup or "RELATIVE WEAKENER ONLY" in setup: return f"{side} → WAIT FOR ABSOLUTE CONFIRMATION"
    if "RECOVERY" in setup or "REVERSAL" in setup: return f"{side} → WATCH FOR CONFIRMATION"
    if "MOMENTUM" in setup or "STRUCTURAL LEADERSHIP" in setup:
        return f"{side} → PROCEED TO STOCK VALIDATION" if confirmation in {"STRONG", "MODERATE"} and "HIGH" in level else f"{side} → VALIDATE STOCKS"
    if "BREAKDOWN" in setup or "STRUCTURAL WEAKNESS" in setup or "DETERIORATION" in setup:
        return f"{side} → PROCEED TO STOCK VALIDATION" if confirmation in {"STRONG", "MODERATE"} and "HIGH" in level else f"{side} → WATCH"
    if "DEVELOPING" in level: return f"{side} → VALIDATE STOCKS"
    if "EARLY" in level: return f"{side} → WATCH"
    return f"{side} → VALIDATE"


def _opportunity_card(item, horizon):
    key = "intraday_opportunity" if horizon == "INTRADAY" else "swing_opportunity"
    type_key = "intraday_type" if horizon == "INTRADAY" else "swing_type"
    strength_key = "intraday_strength" if horizon == "INTRADAY" else "swing_strength"
    level = str(item.get(key, "—")); setup = str(item.get(type_key, "—")); strength = _num(item.get(strength_key))
    side = _trade_side(item, horizon); action = _action_read(item, horizon); cls = _opp_class(level)
    width = 0 if strength is None else min(100, max(5, strength))
    side_cls = "side-long" if "LONG" in side else "side-short" if "SHORT" in side else "side-neutral"
    return f"""<div class='op-card {side_cls}'>
      <div class='op-head'><b>{horizon}</b><span class='opp-pill {cls}'>{level}</span></div>
      <div class='side-read'>{side}</div>
      <div class='setup-type'>{setup}</div>
      <div class='op-strength'><span class='op-number'>{'—' if strength is None else f'{strength:.0f}'}</span><span>opportunity priority</span></div>
      <div class='op-track'><span class='op-fill {cls}' style='width:{width:.0f}%'></span></div>
      <div class='op-action'>{action}</div>
    </div>"""

def _decision_label(item):
    return _action_read(item, "INTRADAY")


def _queue_card(item, rank, selected):
    d = _direction(item)
    state = str(item.get("state", "")).replace("_", " ")
    traj = item.get("rank_trajectory") or []
    fast, core, structural = _delta(traj, 3), _delta(traj, 5), _delta(traj, 10)
    active = " queue-selected" if selected else ""
    key = f"sector_select_{str(item.get('sector','')).replace(' ','_')}_{rank}"
    opp = item.get("intraday_opportunity", "—")
    st.markdown(f"<div class='queue-card{active}'><div class='queue-top'><span class='queue-rank'>#{rank}</span><b>{item.get('sector','—')}</b><span class='bias {_bias_class(d)}'>{_direction_label(d)}</span></div><div class='queue-state'>{state} · <span class='opp-inline {_opp_class(opp)}'>{opp}</span></div><div class='queue-meters'><span>REL <b>{_fmt(item.get('relative_strength'))}</b></span><span>FAST <b>{_fmt(fast, sign=True)}</b></span><span>PART <b>{_participation(item)}</b></span></div></div>", unsafe_allow_html=True)
    return st.button("Open sector", key=key, use_container_width=True)


def _side_class(side: str) -> str:
    text = str(side or "").upper()
    if "LONG" in text:
        return "side-long"
    if "SHORT" in text:
        return "side-short"
    return "side-neutral"


def _stock_count(package_dir: Path, sector: str, session_date=None) -> int:
    try:
        stocks, source = _load_relevant_stocks(package_dir, sector, "", session_date)
        return len(stocks) if source == "ntis_trade_candidates.csv" else 0
    except Exception:
        return 0


def _evidence_compact(item: dict) -> str:
    states = item.get("evidence_states") or {}
    labels = [
        ("relative", "RELATIVE"),
        ("leadership", "TRAJECTORY"),
        ("price", "PRICE"),
        ("breadth", "BREADTH"),
        ("volume", "VOLUME"),
        ("oi", "OI"),
        ("persistence", "PERSISTENCE"),
    ]
    parts = []
    for key, label in labels:
        state = str(states.get(key, "NEUTRAL")).upper()
        cls = "ev-support" if state == "SUPPORTING" else "ev-conflict" if state == "CONFLICTING" else "ev-neutral"
        parts.append(f"<span class='{cls}'>{label}</span>")
    return " ".join(parts)


def _action_state(item: dict, package_dir: Path) -> tuple[str, str]:
    stocks = _stock_count(package_dir, str(item.get("sector", "")), str(item.get("observed_at", ""))[:10])
    confirmation = str(item.get("confirmation_quality", "LIMITED")).upper()
    direction = _direction(item)
    if direction == "NEUTRAL":
        return "NO CLEAN SIDE", "No clear directional sector edge."
    if confirmation == "CONFLICTED":
        return "WAIT — CONFLICTED", "Sector evidence is internally conflicting."
    if stocks > 0 and confirmation in {"STRONG", "MODERATE"}:
        return "PROCEED TO STOCK VALIDATION", f"{stocks} existing SDL stock candidate(s) require stock-level validation."
    if stocks == 0:
        return "SECTOR WATCH — NO STOCK CANDIDATE", "Sector evidence exists, but no session-aligned SDL-qualified stock is available."
    return "VALIDATE STOCKS", f"{stocks} stock candidate(s) found; confirmation is not yet strong enough to proceed."


def _sector_detail(item, rank, package_dir):
    direction = _direction(item)
    state = str(item.get("state", "—")).replace("_", " ")
    support = int(item.get("evidence_agreement") or 0)
    conflicts = int(item.get("evidence_conflicts") or 0)
    persistence = _num(item.get("persistence"))
    traj = item.get("rank_trajectory") or []
    fast, core, structural = _delta(traj, 3), _delta(traj, 5), _delta(traj, 10)
    intraday_side = _trade_side(item, "INTRADAY")
    swing_side = _trade_side(item, "SWING")
    intraday_read = _action_read(item, "INTRADAY")
    swing_read = _action_read(item, "SWING")
    action, action_note = _action_state(item, package_dir)
    gate_cls = "gate-go" if action == "PROCEED TO STOCK VALIDATION" else "gate-stop" if "WAIT" in action else "gate-watch"
    stocks, source = _load_relevant_stocks(package_dir, str(item.get("sector", "")), direction, str(item.get("observed_at", ""))[:10] or None)

    st.markdown(f"""
    <div class='detail-top'>
      <div class='detail-name'><span class='detail-rank'>#{rank}</span>{item.get('sector','—')}</div>
      <div class='detail-right'>
        <span class='bias {_bias_class(direction)}'>{_direction_label(direction)}</span>
        <span class='state-badge'>{state}</span>
      </div>
    </div>
    <div class='detail-meta'>
      <span>Evidence <b>{support}</b> support · <b>{conflicts}</b> conflict/missing</span>
      <span>Persistence <b>{_fmt(persistence,'%')}</b></span>
      <span>Sessions <b>{item.get('sessions_available','—')}</b></span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='section-kicker'>ACTION STATE</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='action-strip {gate_cls}'><b>{action}</b><span>{action_note}</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-kicker'>INTRADAY / SWING READ</div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class='read-grid'>
      <div class='read-card {_side_class(intraday_side)}'>
        <div class='read-head'>INTRADAY <span>{intraday_side}</span></div>
        <b>{str(item.get('intraday_type','—')).replace('_',' ')}</b>
        <small>{intraday_read}</small>
      </div>
      <div class='read-card {_side_class(swing_side)}'>
        <div class='read-head'>SWING <span>{swing_side}</span></div>
        <b>{str(item.get('swing_type','—')).replace('_',' ')}</b>
        <small>{swing_read}</small>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='section-kicker'>LEADERSHIP WINDOWS</div>", unsafe_allow_html=True)
    w1, w2, w3 = st.columns(3, gap="small")
    w1.metric("FAST · 3S", _fmt(fast, sign=True))
    w2.metric("CORE · 5S", _fmt(core, sign=True))
    w3.metric("STRUCT · 10S", _fmt(structural, sign=True))

    st.markdown("<div class='section-kicker'>WHY IT MATTERS · CURRENT EVIDENCE</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='evidence-tags'>{_evidence_compact(item)}</div>",
        unsafe_allow_html=True,
    )

    ev_rows = [
        ("Relative leadership", item.get("relative_strength"), (item.get("evidence_states") or {}).get("relative")),
        ("Price", item.get("price"), (item.get("evidence_states") or {}).get("price")),
        ("Breadth", item.get("breadth"), (item.get("evidence_states") or {}).get("breadth")),
        ("Volume", item.get("volume"), (item.get("evidence_states") or {}).get("volume")),
        ("OI", item.get("oi"), (item.get("evidence_states") or {}).get("oi")),
        ("Persistence", item.get("persistence"), (item.get("evidence_states") or {}).get("persistence")),
    ]
    meter_html = []
    for label, value, status in ev_rows:
        x = _num(value)
        stt = str(status or "NEUTRAL").upper()
        cls = "support" if stt == "SUPPORTING" else "conflict" if stt == "CONFLICTING" else "neutral"
        width = "8" if x is None else str(min(100, max(8, abs(x) * 2)))
        shown = "—" if x is None else _fmt(x, "%") if label not in {"Relative leadership", "Persistence"} else _fmt(x)
        meter_html.append(
            f"<div class='mrow'><span>{label}</span><div class='mtrack'><i class='mfill {cls}' style='width:{width}%'></i></div><b class='{cls}'>{shown}</b></div>"
        )
    st.markdown("<div class='meters'>" + "".join(meter_html) + "</div>", unsafe_allow_html=True)

    with st.expander("OPTIONS POSITIONING · REPORTED OI-CHANGE METRICS", expanded=False):
        st.caption("Reported change metrics only; these do not represent absolute CE/PE OI.")
        st.markdown("<div class='options-mini'>" + _options_block(item) + "</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-kicker'>STOCKS REQUIRING CLOSER ATTENTION</div>", unsafe_allow_html=True)
    if stocks:
        stock_rows = []
        for r in stocks[:8]:
            stock_rows.append({
                "Stock": r["symbol"],
                "SDL evidence": r["signal"],
                "Evidence": "—" if r["score"] is None else f"{r['score']:.1f}",
            })
        st.dataframe(pd.DataFrame(stock_rows), use_container_width=True, hide_index=True)
        st.caption("Existing SDL stock candidates only. Sector evidence never overrides stock-level qualification.")
    else:
        st.info("No session-aligned SDL trade candidate is available for this sector yet. Keep the sector in watch status.")

    _render_stock_attention(item, package_dir)

    with st.expander("NEWS / CATALYST CHECK", expanded=False):
        st.info("News remains contextual and non-blocking. No verified sector/company catalyst is inferred when the approved feed has no aligned item.")
    with st.expander("HISTORICAL CONTEXT · 10 SESSION", expanded=False):
        st.caption("Historical sector observations are preserved for later outcome processing. Replay must use only observations available at the selected time.")
    with st.expander("RAW DATA SNAPSHOT · AUDIT", expanded=False):
        raw = {
            k: item.get(k) for k in (
                "sector","attention","direction","state","relative_strength","rank_slope",
                "price","breadth","volume","oi","buildup","ce_oi_change","pe_oi_change",
                "pe_ce_oi_change","intraday_type","swing_type","intraday_strength",
                "swing_strength","confirmation_quality","observed_at","sessions_available"
            )
        }
        st.json(raw)


def _norm_text(v) -> str:
    return "".join(ch for ch in str(v or "").upper() if ch.isalnum())


def _find_col(df: pd.DataFrame, aliases: list[str]):
    norm = {_norm_text(c): c for c in df.columns}
    for a in aliases:
        if _norm_text(a) in norm:
            return norm[_norm_text(a)]
    for c in df.columns:
        nc = _norm_text(c)
        for a in aliases:
            na = _norm_text(a)
            if na and (na in nc or nc in na):
                return c
    return None


def _sector_key_variants(value) -> set[str]:
    text = str(value or "").upper()
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text)
    stop = {"SECTOR", "INDUSTRY", "THE", "AND"}
    tokens = {t for t in cleaned.split() if t and t not in stop}
    variants = {"".join(tokens), "".join(sorted(tokens))}
    return {v for v in variants if v}


def _sector_match(stock_sector, target_sector) -> bool:
    a = _norm_text(stock_sector)
    b = _norm_text(target_sector)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    at = _sector_key_variants(stock_sector)
    bt = _sector_key_variants(target_sector)
    if not at or not bt:
        return False
    # Conservative token overlap for naming differences such as
    # "Diamond, Gems & Jewellery" vs "Gems Jewellery".
    raw_a = set("".join(ch if ch.isalnum() else " " for ch in str(stock_sector).upper()).split())
    raw_b = set("".join(ch if ch.isalnum() else " " for ch in str(target_sector).upper()).split())
    raw_a -= {"SECTOR", "INDUSTRY", "THE", "AND"}
    raw_b -= {"SECTOR", "INDUSTRY", "THE", "AND"}
    overlap = len(raw_a & raw_b) / max(1, min(len(raw_a), len(raw_b)))
    return overlap >= 0.60





def _load_master_stock_map(root: Path) -> dict[str, dict]:
    """Load the approved Master Stocks taxonomy, if present.

    The file supplies Symbol -> Sector/Industry/FNO classification. It is used
    only for mapping an already-existing SDL candidate to a sector.
    """
    candidates = [
        root / "Master_Stocks_Template.xlsx",
        root / "Config" / "Master_Stocks_Template.xlsx",
        root / "NTIS" / "Master_Stocks_Template.xlsx",
        root / "NTIS" / "Intraday" / "Master_Stocks_Template.xlsx",
        root / "SDL" / "Master_Stocks_Template.xlsx",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return {}

    try:
        df = pd.read_excel(path, sheet_name="Master_Stocks")
    except Exception:
        try:
            df = pd.read_excel(path)
        except Exception:
            return {}

    if df.empty:
        return {}

    sym_col = _find_col(df, ["symbol", "stock symbol", "ticker"])
    sec_col = _find_col(df, ["sector"])
    ind_col = _find_col(df, ["industry"])
    fno_col = _find_col(df, ["fno", "f&o", "fo"])
    active_col = _find_col(df, ["active"])

    if not sym_col:
        return {}

    out = {}
    for _, r in df.iterrows():
        symbol = str(r.get(sym_col, "")).strip().upper()
        if not symbol or symbol == "NAN":
            continue
        out[symbol] = {
            "sector": str(r.get(sec_col, "")).strip() if sec_col else "",
            "industry": str(r.get(ind_col, "")).strip() if ind_col else "",
            "fno": str(r.get(fno_col, "")).strip() if fno_col else "",
            "active": str(r.get(active_col, "")).strip() if active_col else "",
        }
    return out


def _sector_taxonomy_match(label: str, master: dict) -> bool:
    """Conservative sector/industry taxonomy match.

    Exact normalized match is preferred. Token overlap/containment is used only
    when the label is sufficiently specific. No fuzzy guess is accepted.
    """
    target = _norm_text(label)
    if not target:
        return False

    vals = [master.get("sector", ""), master.get("industry", "")]
    for value in vals:
        candidate = _norm_text(value)
        if not candidate:
            continue
        if target == candidate or target in candidate or candidate in target:
            return True

        # Require all meaningful target tokens to appear in the taxonomy value.
        t = [x for x in target.split() if len(x) > 2]
        if t and all(x in candidate.split() for x in t):
            return True
    return False


def _load_relevant_stocks(package_dir: Path, sector: str, direction: str, session_date=None) -> tuple[list[dict], str]:
    """Map existing SDL intraday trade candidates to a Sector Summary sector.

    Primary stock source:
        E:/NSE_Daily_Analysis/Intraday/Output/**/intraday_trade_candidates.csv

    Sector taxonomy:
        approved Master_Stocks workbook.

    No stock signal, probability, qualification, entry, SL or target is
    recalculated here.
    """
    root = package_dir.parents[1]  # E:/NSE_Daily_Analysis
    master_map = _load_master_stock_map(root)
    if not master_map:
        return [], "MASTER STOCK TAXONOMY UNAVAILABLE"

    output_root = root / "Intraday" / "Output"
    if not output_root.exists():
        return [], ""

    target_date = str(session_date or "")[:10]
    wanted_direction = str(direction or "NEUTRAL").upper()

    def _date_subset(work: pd.DataFrame, date_col: str | None) -> pd.DataFrame:
        if not date_col or not target_date:
            return work
        parsed = pd.to_datetime(work[date_col], errors="coerce")
        day = parsed.dt.strftime("%Y-%m-%d")
        exact = work.loc[day.eq(target_date)]
        if not exact.empty:
            return exact
        valid = parsed.dropna()
        if valid.empty:
            return work.iloc[0:0]
        eligible = valid.loc[valid.dt.strftime("%Y-%m-%d") <= target_date]
        if eligible.empty:
            return work.iloc[0:0]
        latest_day = eligible.max().strftime("%Y-%m-%d")
        return work.loc[day.eq(latest_day)]

    def _read(path: Path, qualified: bool) -> list[dict]:
        try:
            df = pd.read_csv(path)
        except Exception:
            return []
        if df.empty:
            return []

        symbol_col = _find_col(df, ["symbol", "stock", "stock symbol", "ticker", "security"])
        date_col = _find_col(df, ["trading date", "trading_date", "trade_date", "session_date", "date"])
        direction_col = _find_col(df, ["validation signal", "final signal", "trade bias", "direction", "signal", "action"])
        pattern_col = _find_col(df, ["pattern", "setup", "trade pattern", "decision"])
        strength_col = _find_col(df, ["risk level", "strength", "confidence", "evidence tier", "stage"])
        prob_col = _find_col(df, ["intraday probability %", "probability %", "probability"])
        entry_col = _find_col(df, ["entry price", "entry"])
        sl_col = _find_col(df, ["stop loss", "sl"])
        target_col = _find_col(df, ["target"])
        score_col = _find_col(df, ["ntis intraday score", "ntis score", "score", "rank"])
        if not symbol_col:
            return []

        work = _date_subset(df.copy(), date_col)
        if work.empty:
            return []

        rows = []
        for _, r in work.iterrows():
            symbol = str(r.get(symbol_col, "")).strip().upper()
            taxonomy = master_map.get(symbol)
            if not symbol or not taxonomy:
                continue
            if not _sector_taxonomy_match(sector, taxonomy):
                continue

            d = str(r.get(direction_col, "")).strip() if direction_col else ""
            if wanted_direction != "NEUTRAL" and d:
                du = d.upper()
                aligned = (
                    wanted_direction == "INTO"
                    and any(x in du for x in ("VALID BUY", "BUY", "BULL", "LONG", "CALL"))
                ) or (
                    wanted_direction == "OUT"
                    and any(x in du for x in ("VALID SELL", "SELL", "BEAR", "SHORT", "PUT"))
                )
                # Direction alignment is used for ordering, not exclusion.
                direction_rank = 1 if aligned else 0
            else:
                direction_rank = 0

            def val(col):
                return r.get(col) if col else None

            rows.append({
                "symbol": symbol,
                "direction": d,
                "signal": d or "SDL STOCK CANDIDATE",
                "pattern": str(val(pattern_col) or "").strip(),
                "strength": str(val(strength_col) or "").strip(),
                "probability": _num(val(prob_col)) if prob_col else None,
                "entry_price": _num(val(entry_col)) if entry_col else None,
                "stop_loss": _num(val(sl_col)) if sl_col else None,
                "target": _num(val(target_col)) if target_col else None,
                "score": _num(val(score_col)) if score_col else None,
                "source": path.name,
                "qualified": qualified,
                "direction_rank": direction_rank,
                "sector_taxonomy": taxonomy.get("sector", ""),
                "industry_taxonomy": taxonomy.get("industry", ""),
            })
        return rows

    # Most recent candidate file for the requested session first.
    files = sorted(
        output_root.rglob("intraday_trade_candidates.csv"),
        key=lambda p: p.stat().st_ctime,
        reverse=True,
    )
    for path in files:
        rows = _read(path, True)
        if rows:
            rows.sort(key=lambda r: (
                r.get("direction_rank", 0),
                r.get("probability") is not None,
                r.get("probability") if r.get("probability") is not None else -float("inf"),
                r.get("score") if r.get("score") is not None else -float("inf"),
            ), reverse=True)
            return rows[:12], str(path.relative_to(output_root))

    return [], ""



def _has_trade_candidates(package_dir: Path, sector: str, session_date=None) -> bool:
    stocks, source = _load_relevant_stocks(package_dir, sector, "", session_date)
    return bool(stocks) and source == "ntis_trade_candidates.csv"




def _render_stock_attention(item: dict, package_dir: Path):
    sector = str(item.get("sector", ""))
    latest = str(item.get("latest_observation", item.get("observed_at", "")))[:10] or None
    stocks, source = _load_relevant_stocks(package_dir, sector, _direction(item), latest)

    st.markdown("<div class='section-kicker stock-kicker'>STOCK SETUPS · EXISTING SDL VALIDATION</div>", unsafe_allow_html=True)
    if not stocks:
        st.markdown(
            "<div class='stock-empty'><b>NO SESSION-ALIGNED SDL STOCK SETUP FOUND</b>"
            "<span>Sector evidence is not being converted into a trade candidate. "
            "The dashboard will not invent a stock setup.</span></div>",
            unsafe_allow_html=True,
        )
        return

    intraday = rank_stock_opportunities(stocks, _direction(item), "INTRADAY")
    swing = rank_stock_opportunities(stocks, _direction(item), "SWING")

    def card(r, horizon):
        signal = str(r.get("signal") or "WATCH").upper()
        side = "LONG" if "BUY" in signal or "LONG" in signal else "SHORT" if "SELL" in signal or "SHORT" in signal else "WATCH"
        p = r.get("probability")
        entry = r.get("entry_price")
        sl = r.get("stop_loss")
        target = r.get("target")
        rr = None
        if entry is not None and sl is not None and target is not None:
            risk = abs(float(entry) - float(sl))
            reward = abs(float(target) - float(entry))
            if risk > 0:
                rr = reward / risk
        def f(v):
            return "—" if v is None else f"{float(v):,.2f}"
        qual = "SDL QUALIFIED" if r.get("qualified") else "VALIDATE SDL"
        smc = str(r.get("smc_state", "NOT AVAILABLE"))
        return f"""
        <div class='trade-card'>
          <div class='trade-head'>
            <span class='trade-rank'>#{r.get('attention_rank','—')}</span>
            <b>{r.get('symbol','—')}</b>
            <span class='trade-side {side.lower()}'>{side}</span>
            <span class='trade-horizon'>{horizon}</span>
          </div>
          <div class='trade-setup'>{r.get('stock_signal', signal)} · {r.get('stock_strength', r.get('strength','—'))}</div>
          <div class='trade-levels'>
            <div><small>ENTRY</small><strong>{f(entry)}</strong></div>
            <div><small>STOP</small><strong>{f(sl)}</strong></div>
            <div><small>TARGET</small><strong>{f(target)}</strong></div>
            <div><small>R:R</small><strong>{'—' if rr is None else f'1:{rr:.2f}'}</strong></div>
          </div>
          <div class='trade-tags'>
            <span class='tag-qual'>{qual}</span>
            <span>PROB {f(p) if p is not None else '—'}</span>
            <span>SMC {smc}</span>
          </div>
          <div class='trade-next'>NEXT: {'REVIEW / VALIDATE SETUP' if r.get('qualified') else 'WAIT FOR SDL QUALIFICATION'}</div>
        </div>
        """

    tab_i, tab_s = st.tabs(["INTRADAY · ACTIONABLE SHORTLIST", "SWING · DEVELOPING SETUPS"])
    for tab, rows, horizon in ((tab_i, intraday, "INTRADAY"), (tab_s, swing, "SWING")):
        with tab:
            for r in rows[:5]:
                st.markdown(card(r, horizon), unsafe_allow_html=True)
            st.caption(
                "Entry/stop/target/probability are displayed from the existing SDL candidate output when present; "
                "Sector Analysis does not recalculate them."
            )


def _collect_stock_opportunities(intelligence: dict, package_dir: Path, horizon: str) -> list[dict]:
    """Build a trader shortlist from existing SDL stock outputs across sectors."""
    focus = list(intelligence.get("focus") or [])
    watch = list(intelligence.get("watch") or [])
    sectors = focus + [x for x in watch if x.get("sector") not in {f.get("sector") for f in focus}]
    result = []
    seen = set()

    for sector_item in sectors:
        sector = str(sector_item.get("sector", "")).strip()
        if not sector:
            continue
        direction = _direction(sector_item)
        session_date = str(
            sector_item.get("observed_at", intelligence.get("latest_observation", ""))
        )[:10] or None
        stocks, source = _load_relevant_stocks(package_dir, sector, direction, session_date)
        ranked = rank_stock_opportunities(stocks, direction, horizon)
        for stock in ranked:
            symbol = str(stock.get("symbol", "")).strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            result.append({
                "symbol": symbol,
                "sector": sector,
                "sector_direction": direction,
                "sector_state": str(sector_item.get("state", "—")).replace("_", " "),
                "sector_type": str(
                    sector_item.get("intraday_type" if horizon == "INTRADAY" else "swing_type", "—")
                ).replace("_", " "),
                "relative": _num(sector_item.get("relative_strength")),
                "fast": _delta(sector_item.get("rank_trajectory") or [], 3),
                "core": _delta(sector_item.get("rank_trajectory") or [], 5),
                "structural": _delta(sector_item.get("rank_trajectory") or [], 10),
                "evidence_support": int(sector_item.get("evidence_agreement") or 0),
                "evidence_conflict": int(sector_item.get("evidence_conflicts") or 0),
                "stock_signal": stock.get("stock_signal", stock.get("signal", "SDL CANDIDATE")),
                "stock_strength": stock.get("stock_strength", stock.get("strength", "—")),
                "stock_score": stock.get("stock_score", stock.get("score")),
                "stock_direction": stock.get("stock_direction", stock.get("direction", "—")),
                "smc_state": stock.get("smc_state", "NOT AVAILABLE"),
                "smc_detail": stock.get("smc_detail", ""),
                "qualified": bool(stock.get("qualified")),
                "source": source,
            })

    def key(row):
        # Prefer qualified SDL candidates, then stock evidence, then sector
        # agreement/relative leadership. This is an attention order, not a
        # probability or guaranteed-return ranking.
        score = _num(row.get("stock_score"))
        return (
            1 if row.get("qualified") else 0,
            1 if str(row.get("smc_state")) != "NOT AVAILABLE" else 0,
            1 if row.get("evidence_conflict", 0) == 0 else 0,
            row.get("evidence_support", 0),
            score if score is not None else -float("inf"),
            row.get("relative") if row.get("relative") is not None else -float("inf"),
        )
    result.sort(key=key, reverse=True)
    for i, row in enumerate(result, 1):
        row["rank"] = i
    return result


def _render_quick_decision(intelligence: dict, package_dir: Path):
    """Compact first-viewport decision surface."""
    intraday = _collect_stock_opportunities(intelligence, package_dir, "INTRADAY")
    swing = _collect_stock_opportunities(intelligence, package_dir, "SWING")

    st.markdown(
        "<div class='quick-title'>TODAY'S TRADE SETUP SHORTLIST</div>"
        "<div class='quick-sub'>Sector rotation is the filter. Existing SDL stock qualification is the gate. "
        "SMC is confirmation only when observable stock structure is available.</div>",
        unsafe_allow_html=True,
    )

    if not intraday and not swing:
        st.markdown(
            "<div class='quick-empty'><b>NO STOCK SETUP CONFIRMED</b>"
            "<span>No session-aligned stock candidate is currently mapped to the sector intelligence. "
            "Do not infer a stock trade from sector strength alone.</span></div>",
            unsafe_allow_html=True,
        )
        return

    ti, ts = st.tabs(["INTRADAY · WHAT CAN MOVE NOW", "SWING · WHAT CAN PERSIST"])
    for tab, rows, horizon in ((ti, intraday, "INTRADAY"), (ts, swing, "SWING")):
        with tab:
            if not rows:
                st.info(f"No {horizon.lower()} stock candidate is currently available.")
                continue
            for row in rows[:5]:
                side = "LONG" if row["sector_direction"] == "INTO" else "SHORT" if row["sector_direction"] == "OUT" else "WATCH"
                gate = "SDL QUALIFIED" if row["qualified"] else "VALIDATE SDL"
                gate_cls = "go" if row["qualified"] else "watch"
                smc = str(row["smc_state"])
                smc_short = "SMC CONFIRMED/OBSERVABLE" if smc != "NOT AVAILABLE" else "SMC NOT AVAILABLE"
                fast = _fmt(row["fast"], sign=True)
                core = _fmt(row["core"], sign=True)
                structural = _fmt(row["structural"], sign=True)
                st.markdown(
                    f"""
                    <div class='opp-card'>
                      <div class='opp-main'>
                        <div class='opp-rank'>#{row['rank']}</div>
                        <div class='opp-symbol'>{row['symbol']}</div>
                        <div class='opp-side {side.lower()}'>{side}</div>
                        <div class='opp-sector'>{row['sector']}</div>
                      </div>
                      <div class='opp-grid'>
                        <div><small>SETUP</small><b>{row['sector_type']}</b></div>
                        <div><small>SDL GATE</small><b class='{gate_cls}'>{gate}</b></div>
                        <div><small>SMC</small><b>{smc_short}</b></div>
                        <div><small>STRENGTH</small><b>{row['stock_strength']}</b></div>
                      </div>
                      <div class='opp-foot'>
                        <span>FAST {fast} · CORE {core} · 10S {structural}</span>
                        <span>{row['evidence_support']} supporting · {row['evidence_conflict']} conflict</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.caption(
                "Rank is an attention order, not a probability. Final action still requires stock-level validation."
            )




def _render(intelligence, latest_observation=None, package_dir=None):
    focus = list(intelligence.get("focus") or [])
    watch = list(intelligence.get("watch") or [])

    into = [x for x in focus if _direction(x) == "INTO"]
    out = [x for x in focus if _direction(x) == "OUT"]
    if not into and not out:
        seed = watch[:8]
        into = [x for x in seed if _direction(x) == "INTO"][:3]
        out = [x for x in seed if _direction(x) == "OUT"][:3]

    primary = into + out
    all_watch = [x for x in watch if x.get("sector") not in {y.get("sector") for y in primary}]
    selected = st.session_state.get("sector_selected")
    available = [x.get("sector") for x in primary + all_watch]
    if selected not in available and available:
        selected = available[0]
        st.session_state["sector_selected"] = selected

    st.markdown("""
    <div class='radar-head'>
      <div>
        <div class='radar-title'>SECTOR ROTATION · OPPORTUNITY CENTRE</div>
        <div class='radar-sub'>Find the best Intraday / Swing stock setups — sector context first, stock validation second</div>
      </div>
      <div class='radar-meta'>Historical observations retained · Decision Board independent</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f"<div class='source-strip'><b>LIVE</b> {latest_observation or '—'} · "
        f"<b>10S HISTORY</b> preserved · <b>FOCUS</b> {len(focus)} · "
        f"<b>WATCH</b> {len(watch)} · <b>SCANNED</b> {intelligence.get('all_count',0)}</div>",
        unsafe_allow_html=True,
    )

    # The actual trading decision surface comes first.
    _render_quick_decision(intelligence, package_dir)

    st.markdown("<div class='secondary-title'>SECTOR CONTEXT · WHY THESE STOCKS ARE HERE</div>", unsafe_allow_html=True)
    left, right = st.columns([0.31, 0.69], gap="small")

    with left:
        st.markdown("### SECTOR SETUPS")
        st.caption("Context only. Stock candidates above are the actionable shortlist.")
        q = 1
        for label, group, cls in (
            ("ROTATING INTO", into, "rotation-into"),
            ("ROTATING OUT", out, "rotation-out"),
        ):
            if not group:
                continue
            st.markdown(
                f"<div class='qsection {cls}'>{label} <span>{len(group)}</span></div>",
                unsafe_allow_html=True,
            )
            for item in group[:4]:
                active = item.get("sector") == selected
                key = f"sector_open_v46_{_norm_text(item.get('sector'))}_{q}"
                st.markdown(
                    f"<div class='qcard {'qactive' if active else ''}'>"
                    f"<div class='qname'><span>#{q}</span><b>{item.get('sector','—')}</b></div>"
                    f"<div class='qline'><span class='bias {_bias_class(_direction(item))}'>{_direction_label(_direction(item))}</span>"
                    f"<span>{str(item.get('state','—')).replace('_',' ')}</span></div>"
                    f"<div class='qmeters'><span>REL {_fmt(item.get('relative_strength'))}</span>"
                    f"<span>FAST {_fmt(_delta(item.get('rank_trajectory') or [],3), sign=True)}</span>"
                    f"<span>{int(item.get('evidence_agreement') or 0)}✓ / {int(item.get('evidence_conflicts') or 0)}✕</span></div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Open sector", key=key, use_container_width=True):
                    st.session_state["sector_selected"] = item.get("sector")
                    st.rerun()
                q += 1

        with st.expander(f"WATCH / EMERGING · {len(all_watch)}", expanded=False):
            for item in all_watch[:10]:
                key = f"watch_open_v46_{_norm_text(item.get('sector'))}"
                st.markdown(
                    f"<div class='watch-row'><b>{item.get('sector','—')}</b>"
                    f"<span>{_direction_label(_direction(item))}</span>"
                    f"<span>{str(item.get('intraday_type','—')).replace('_',' ')}</span></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Open", key=key, use_container_width=True):
                    st.session_state["sector_selected"] = item.get("sector")
                    st.rerun()

    with right:
        item = next((x for x in primary + all_watch if x.get("sector") == selected), None)
        if item:
            _sector_detail(item, 1, package_dir)
        else:
            st.info("No sector context is currently available.")

    with st.expander("ALL SECTOR EVIDENCE · AUDIT ONLY", expanded=False):
        rows = []
        for x in focus + watch:
            rows.append({
                "Sector": x.get("sector"),
                "Attention": x.get("attention"),
                "Direction": _direction_label(x.get("direction")),
                "State": str(x.get("state","—")).replace("_"," "),
                "Relative": x.get("relative_strength"),
                "FAST": _delta(x.get("rank_trajectory") or [], 3),
                "CORE": _delta(x.get("rank_trajectory") or [], 5),
                "10S": _delta(x.get("rank_trajectory") or [], 10),
                "Evidence": f"{int(x.get('evidence_agreement') or 0)} / {int(x.get('evidence_conflicts') or 0)}",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("SYSTEM / SOURCE STATUS", expanded=False):
        st.caption(
            f"{intelligence.get('all_count',0)} sectors evaluated · "
            f"{intelligence.get('ignored_count',0)} suppressed · "
            f"{intelligence.get('sessions',0)} sessions available · "
            f"Method: {intelligence.get('method','—')}"
        )


def render_sector_analysis_page(source_root: str | Path, news_provider: Callable[[], Iterable[dict]] | None = None) -> None:
    root = Path(source_root).expanduser().resolve()
    package_dir = Path(__file__).resolve().parent

    st.markdown("""
    <style>
    .stApp { font-size: 16px; }
    [data-testid="stAppViewContainer"] .main .block-container { padding-top: .55rem !important; padding-bottom: 1.5rem !important; max-width: 1500px; }
    h1,h2,h3,h4 { letter-spacing:-.025em; margin-top:.35rem !important; }
    h3 { font-size:23px !important; margin-bottom:.35rem !important; }
    .radar-head{display:flex;justify-content:space-between;align-items:end;gap:16px;padding:2px 0 7px;border-bottom:1px solid rgba(120,150,190,.18)}
    .radar-title{font-size:36px;font-weight:950;letter-spacing:-.03em;color:#f4f7fb}
    .radar-sub{font-size:14px;color:#9eafc0;margin-top:2px}
    .radar-meta{font-size:11px;color:#74879a;text-align:right}
    .source-strip{margin:6px 0 9px;padding:9px 12px;border:1px solid rgba(120,150,190,.20);border-radius:7px;background:rgba(8,22,38,.72);font-size:12px;color:#b7c7d6}
    .source-strip b{color:#dfe8f0}
    .qsection{margin:9px 0 5px;font-size:12px;font-weight:950;letter-spacing:.10em}
    .qsection span{float:right;color:#75899c}
    .qsection.rotation-into{color:#82e39f}.qsection.rotation-out{color:#f28d97}
    .qcard{padding:9px 10px;margin:5px 0;border:1px solid rgba(120,150,190,.22);border-radius:8px;background:linear-gradient(180deg,rgba(11,29,49,.96),rgba(7,18,31,.96))}
    .qactive{border-color:rgba(170,120,255,.85);box-shadow:0 0 0 1px rgba(170,120,255,.16)}
    .qname{display:flex;gap:7px;align-items:center}.qname span{color:#8fa3b7;font-size:10px}.qname b{font-size:15px;line-height:1.15}
    .qline{display:flex;justify-content:space-between;gap:5px;align-items:center;margin-top:7px;color:#b8c7d4;font-size:11px}
    .qmeters{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px;font-size:10px;color:#9eb0c1}.qmeters span{padding:3px 5px;border-radius:4px;background:rgba(255,255,255,.035)}
    .bias{display:inline-block;padding:3px 5px;border-radius:4px;font-size:8px;font-weight:950;letter-spacing:.04em}.bias.into{color:#baf5cb;background:rgba(34,150,84,.17)}.bias.out{color:#ffd0d2;background:rgba(184,58,70,.17)}.bias.neutral{color:#d3dde7;background:rgba(120,140,160,.12)}
    .state-badge{display:inline-block;padding:4px 6px;border-radius:5px;font-size:8px;font-weight:950;background:rgba(214,169,72,.12);color:#f0d58d}
    .watch-row{display:flex;justify-content:space-between;gap:7px;align-items:center;padding:7px 8px;margin:4px 0;border:1px solid rgba(120,150,190,.15);border-radius:6px;background:rgba(255,255,255,.025);font-size:9px}
    .detail-top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 11px;border:1px solid rgba(120,150,190,.23);border-radius:8px;background:linear-gradient(180deg,rgba(11,30,52,.98),rgba(6,17,31,.98))}
    .detail-name{font-size:27px;font-weight:950;color:#f5f8fb;line-height:1.1}.detail-rank{font-size:11px;color:#8ea2b5;margin-right:7px}
    .detail-right{display:flex;gap:6px;align-items:center}.detail-meta{font-size:11px;display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;margin:5px 1px 8px;color:#9aabba;font-size:11px}.detail-meta b{color:#dfe8f0}
    .section-kicker{margin:9px 0 5px;font-size:11px;font-weight:950;letter-spacing:.10em;color:#93a8bc}
    .action-strip{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 12px;border-radius:8px;font-size:12px}.action-strip b{font-size:14px}
    .gate-go{background:rgba(33,145,77,.14);border:1px solid rgba(74,196,112,.35);color:#baf4c9}.gate-watch{background:rgba(176,135,46,.12);border:1px solid rgba(220,182,87,.28);color:#f0d58e}.gate-stop{background:rgba(178,55,67,.13);border:1px solid rgba(230,99,111,.30);color:#ffc8cc}
    .read-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.read-card{padding:8px 10px;border:1px solid rgba(120,150,190,.22);border-radius:7px;background:rgba(8,22,38,.8)}.read-card.side-long{border-color:rgba(70,190,113,.34)}.read-card.side-short{border-color:rgba(218,91,103,.34)}
    .read-head{font-size:10px;letter-spacing:.08em;color:#8fa2b4}.read-head span{float:right;font-size:9px;font-weight:950}.read-card b{display:block;margin-top:5px;font-size:14px;color:#edf3f7}.read-card small{display:block;margin-top:5px;color:#b2c1ce;font-size:11px}
    .evidence-tags{display:flex;gap:4px;flex-wrap:wrap;padding:7px 8px;border:1px solid rgba(120,150,190,.18);border-radius:7px;background:rgba(8,22,38,.62)}.evidence-tags span{padding:4px 6px;border-radius:4px;font-size:10px;font-weight:950}
    .ev-support{color:#a9edba;background:rgba(42,164,88,.15)}.ev-conflict{color:#f18e97;background:rgba(190,59,70,.15)}.ev-neutral{color:#aab8c5;background:rgba(130,145,160,.10)}
    .meters{padding:7px 9px;border:1px solid rgba(120,150,190,.18);border-radius:7px;background:rgba(8,22,38,.72)}.mrow{display:grid;grid-template-columns:1.25fr 2.2fr .8fr;gap:8px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(120,150,190,.08);font-size:11px}.mrow:last-child{border-bottom:0}.mtrack{height:7px;border-radius:5px;background:rgba(255,255,255,.07);overflow:hidden}.mfill{display:block;height:100%;border-radius:5px}.mfill.support{background:#55c27b}.mfill.conflict{background:#dc6872}.mfill.neutral{background:#7f8d9c}.mrow b{text-align:right;font-size:11px}.support{color:#86e0a4}.conflict{color:#f27f88}.neutral{color:#a8b7c7}
    .options-mini .change-row{grid-template-columns:1.2fr 1.7fr 1.8fr;padding:6px 0}.options-mini .change-label{font-size:9px}.options-mini .change-value{font-size:8px}

    .stock-kicker{color:#d8e5ef;font-size:13px !important}
    .stock-summary{padding:8px 10px;margin-bottom:7px;border:1px solid rgba(120,150,190,.22);border-radius:7px;background:rgba(8,22,38,.72);font-size:12px;color:#b8c7d4}.stock-summary b{font-size:16px;color:#f2f6fa}.stock-summary span{color:#9cafc0}
    .stock-card{padding:9px 11px;margin:6px 0;border:1px solid rgba(120,150,190,.23);border-radius:8px;background:linear-gradient(180deg,rgba(11,29,49,.96),rgba(7,18,31,.96))}
    .stock-head{display:flex;align-items:center;gap:8px}.stock-head b{font-size:17px;color:#f5f8fb}.stock-rank{font-size:11px;color:#8ea2b5}.stock-side{margin-left:auto;font-size:10px;font-weight:950;color:#dce8f0}
    .stock-grid{display:grid;grid-template-columns:1.1fr 1.6fr 1fr 1.2fr;gap:7px;margin-top:7px}.stock-grid>div{padding:6px 7px;border-radius:5px;background:rgba(255,255,255,.035);border:1px solid rgba(120,150,190,.10)}.stock-grid small{display:block;font-size:8px;color:#8297aa;letter-spacing:.06em}.stock-grid strong{display:block;margin-top:2px;font-size:10px;color:#edf3f7}.smc-ok{border-color:rgba(76,193,115,.30) !important}.smc-ok strong{color:#a9edba}.smc-na strong{color:#aab8c5}
    .stock-foot{display:flex;justify-content:space-between;gap:10px;margin-top:6px;font-size:9px;color:#8fa2b4}.stock-foot span:last-child{text-align:right}

    .opportunity-strip{margin:6px 0 9px;padding:10px 12px;border:1px solid rgba(150,110,255,.30);border-radius:9px;background:linear-gradient(180deg,rgba(17,31,53,.98),rgba(8,19,34,.98));}
    .opportunity-strip.empty{border-color:rgba(214,170,74,.30);background:rgba(48,38,18,.35)}
    .opportunity-title{font-size:14px;font-weight:950;letter-spacing:.08em;color:#f1f5f9}.opportunity-sub{font-size:11px;color:#aebdcc;margin-top:2px}
    .top-stock-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:8px}.top-stock{padding:8px 9px;border:1px solid rgba(120,150,190,.22);border-radius:7px;background:rgba(255,255,255,.025)}.top-stock.go{border-color:rgba(70,190,113,.36)}.top-stock.watch{border-color:rgba(220,182,87,.32)}
    .top-stock-name{font-size:17px;font-weight:950;color:#f5f8fb}.top-stock-meta{font-size:9px;color:#9fb0bf;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.top-stock-tags{display:flex;gap:4px;margin-top:5px}.top-stock-tags span{font-size:8px;padding:3px 5px;border-radius:4px;background:rgba(255,255,255,.05);color:#c8d4df}
    .qual-ok strong{color:#9de8b1 !important}.qual-watch strong{color:#f0d58e !important}

    .radar-head{padding:0 0 5px !important}
    .radar-title{font-size:36px !important;line-height:1.08 !important}
    .radar-sub{font-size:15px !important;line-height:1.35 !important}
    .radar-meta{font-size:12px !important}
    .source-strip{font-size:11px !important;padding:7px 10px !important;margin:4px 0 7px !important}
    .quick-title{font-size:19px;font-weight:950;letter-spacing:.06em;color:#f4f7fb;margin-top:5px}
    .quick-sub{font-size:12px;color:#aebdca;margin:2px 0 7px}
    .quick-empty{padding:12px;border:1px solid rgba(220,182,87,.35);border-radius:8px;background:rgba(48,38,18,.34);display:flex;justify-content:space-between;gap:12px;align-items:center}.quick-empty b{font-size:13px;color:#f0d58e}.quick-empty span{font-size:11px;color:#c3cdd7}
    .opp-card{padding:10px 12px;margin:6px 0;border:1px solid rgba(120,150,190,.28);border-radius:9px;background:linear-gradient(180deg,rgba(12,31,52,.98),rgba(7,18,31,.98))}
    .opp-main{display:flex;align-items:center;gap:9px}.opp-rank{font-size:11px;color:#8297aa}.opp-symbol{font-size:22px;font-weight:950;color:#f5f8fb}.opp-side{margin-left:auto;padding:4px 7px;border-radius:5px;font-size:10px;font-weight:950}.opp-side.long{background:rgba(42,164,88,.16);color:#a9edba}.opp-side.short{background:rgba(190,59,70,.16);color:#f3a0a7}.opp-side.watch{background:rgba(160,140,70,.14);color:#efd58f}.opp-sector{font-size:11px;color:#a8bac9}
    .opp-grid{display:grid;grid-template-columns:1.4fr 1.35fr 1.5fr 1fr;gap:7px;margin-top:8px}.opp-grid>div{padding:7px 8px;background:rgba(255,255,255,.035);border:1px solid rgba(120,150,190,.10);border-radius:5px}.opp-grid small{display:block;font-size:9px;color:#8499ab;letter-spacing:.06em}.opp-grid b{display:block;margin-top:3px;font-size:11px;color:#edf3f7}.opp-grid .go{color:#a9edba}.opp-grid .watch{color:#efd58f}.opp-foot{display:flex;justify-content:space-between;gap:10px;margin-top:7px;font-size:10px;color:#94a7b7}.secondary-title{font-size:15px;font-weight:950;letter-spacing:.08em;color:#cdd9e3;margin:10px 0 4px;padding-top:7px;border-top:1px solid rgba(120,150,190,.18)}
    .detail-name{font-size:29px !important}.detail-meta{font-size:11px !important}.section-kicker{font-size:12px !important}

    .quick-title{font-size:22px !important;letter-spacing:.07em !important}
    .quick-sub{font-size:13px !important}
    .opp-card{border-width:1px !important;padding:11px 13px !important}
    .opp-symbol{font-size:24px !important}.opp-sector{font-size:12px !important}
    .opp-action{margin-top:7px;padding:6px 8px;border-radius:5px;background:rgba(105,72,180,.14);border:1px solid rgba(145,112,230,.22);color:#d7c9ff;font-size:10px;font-weight:950;letter-spacing:.06em}

    .trade-card{padding:10px 12px;margin:6px 0;border:1px solid rgba(120,150,190,.28);border-radius:9px;background:linear-gradient(180deg,rgba(12,31,52,.98),rgba(7,18,31,.98))}
    .trade-head{display:flex;align-items:center;gap:9px}.trade-head b{font-size:23px;color:#f5f8fb}.trade-rank{font-size:11px;color:#8195a8}.trade-side{margin-left:auto;padding:4px 8px;border-radius:5px;font-size:10px;font-weight:950}.trade-side.long{background:rgba(42,164,88,.17);color:#a9edba}.trade-side.short{background:rgba(190,59,70,.17);color:#f3a0a7}.trade-side.watch{background:rgba(160,140,70,.15);color:#efd58f}.trade-horizon{font-size:9px;color:#91a4b5}
    .trade-setup{font-size:12px;color:#b7c7d5;margin-top:4px;font-weight:800}.trade-levels{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:8px}.trade-levels>div{padding:7px 8px;border-radius:5px;background:rgba(255,255,255,.035);border:1px solid rgba(120,150,190,.11)}.trade-levels small{display:block;font-size:9px;color:#8195a8}.trade-levels strong{display:block;font-size:13px;color:#eef4f8;margin-top:2px}.trade-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}.trade-tags span{font-size:9px;padding:4px 6px;border-radius:4px;background:rgba(255,255,255,.05);color:#b9c7d3}.trade-tags .tag-qual{color:#a9edba;border:1px solid rgba(70,190,113,.25)}.trade-next{margin-top:7px;font-size:10px;font-weight:950;letter-spacing:.05em;color:#d8c7ff}
    .quick-title{font-size:23px !important}.quick-sub{font-size:13px !important}
    @media(max-width:1050px){.radar-title{font-size:29px}.detail-name{font-size:22px}.read-grid{grid-template-columns:1fr}.mrow{grid-template-columns:1.1fr 1.7fr .7fr}}
    </style>
    """, unsafe_allow_html=True)

    _start_worker(root, package_dir)
    status = _status_block(package_dir)
    result = read_result(package_dir)
    intelligence = result.get("intelligence", result) if isinstance(result, dict) else {}
    if not intelligence:
        st.info("Sector intelligence is being prepared in the background. The main SDL Decision Board remains independent.")
        if st.button("Refresh Sector Intelligence", key="sector_refresh_wait"):
            st.rerun()
        return

    latest = result.get("latest_observation", intelligence.get("latest_observation", "—"))
    if news_provider is not None:
        try:
            classify_news_feed(list(news_provider()))
        except Exception:
            pass
    _render(intelligence, latest, package_dir)

    if status.get("status") == "RUNNING":
        st.caption("Background refresh is running; the page continues to display the last completed intelligence result.")
    elif status.get("status") == "READY" and st.button("Refresh Sector Intelligence", key="sector_refresh_ready"):
        _start_worker(root, package_dir)
        st.rerun()