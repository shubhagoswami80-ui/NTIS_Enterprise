from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from config import EVENT_CSV, STATE_JSON
from pipeline import (
    discover_historical_snapshots,
    process_latest_snapshot_for_today,
)
from storage import load_events, load_state
from approaching_breakout import load_latest_approaching_breakouts


st.set_page_config(
    page_title="SDL — Straddle Breakout",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Visual system
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .stApp { background: #f7f8fc; }

    .block-container {
        max-width: 1240px;
        padding-top: 1.15rem;
        padding-bottom: 1rem;
    }

    .sdl-header {
        background: linear-gradient(105deg, #0d1830 0%, #17264b 62%, #243a72 100%);
        color: white;
        padding: 17px 20px 15px 20px;
        border-radius: 11px;
        margin-bottom: 11px;
        box-shadow: 0 8px 24px rgba(20, 34, 72, .12);
    }

    .sdl-header-title {
        font-size: 23px;
        font-weight: 750;
        line-height: 1.25;
        margin: 0;
    }

    .sdl-header-subtitle {
        font-size: 12px;
        opacity: .88;
        margin-top: 3px;
    }

    .section-card {
        background: white;
        border: 1px solid #e7eaf2;
        border-radius: 10px;
        padding: 12px;
        margin: 9px 0;
        box-shadow: 0 4px 16px rgba(20, 34, 72, .055);
    }

    .section-title {
        color: #17233f;
        font-size: 17px;
        font-weight: 720;
        margin-bottom: 8px;
    }

    .metric-card {
        background: #fbfcff;
        border: 1px solid #e8ebf3;
        border-radius: 9px;
        padding: 11px 12px;
        min-height: 76px;
    }

    .metric-label {
        color: #6d7588;
        font-size: 9px;
        font-weight: 750;
        letter-spacing: .06em;
        text-transform: uppercase;
    }

    .metric-value {
        color: #17233f;
        font-size: 20px;
        font-weight: 760;
        margin-top: 4px;
    }

    .metric-detail {
        color: #7b8394;
        font-size: 10px;
        margin-top: 2px;
    }

    .up-card {
        background: #f1fbf6;
        border-color: #b9ead2;
    }

    .down-card {
        background: #fff4f4;
        border-color: #f1c4c4;
    }

    .gravity-legend {
        display: flex;
        gap: 7px;
        flex-wrap: wrap;
        margin: 5px 0 10px 0;
        font-size: 11px;
    }

    .gravity-pill {
        padding: 4px 8px;
        border-radius: 999px;
        font-weight: 700;
        border: 1px solid rgba(0,0,0,.08);
    }

    .gravity-vstrong { background: #b7e4c7; color: #12552d; }
    .gravity-strong { background: #d9f0df; color: #1f6335; }
    .gravity-moderate { background: #fff1b8; color: #705800; }
    .gravity-caution { background: #ffd8a8; color: #7a3d00; }
    .gravity-neutral { background: #e9edf3; color: #596273; }

    .muted {
        color: #747d90;
        font-size: 11px;
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #5844d8, #6c4ee6);
        border: 0;
        border-radius: 10px;
        font-weight: 700;
        min-height: 40px;
    }

    div.stButton > button {
        border-radius: 10px;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #e6e9f1;
        border-radius: 8px;
        overflow: hidden;
    }

    .decision-note { color:#5f687a; font-size:11px; margin:2px 0 8px 0; }

    .footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #747d90;
        font-size: 11px;
        margin-top: 18px;
        padding-top: 10px;
        border-top: 1px solid #e6e9f1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _events() -> pd.DataFrame:
    events = load_events(EVENT_CSV)
    if events is None:
        return pd.DataFrame()
    return events.copy()


def _normalise_trading_date(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


def _today_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty or "trading_date" not in events.columns:
        return pd.DataFrame()

    today = pd.Timestamp.now().date().isoformat()
    dates = events["trading_date"].map(_normalise_trading_date)
    return events.loc[dates == today].copy()


def _latest_workbook() -> tuple[Path | None, str | None]:
    today = pd.Timestamp.now().date().isoformat()

    try:
        files = list(discover_historical_snapshots(today))
    except Exception:
        return None, None

    valid_files = []
    for item in files:
        path = Path(item)
        try:
            if path.is_file():
                valid_files.append(path)
        except OSError:
            continue

    if not valid_files:
        return None, None

    latest = max(valid_files, key=lambda p: p.stat().st_mtime)
    modified = pd.Timestamp.fromtimestamp(latest.stat().st_mtime).strftime(
        "%d %b %Y, %H:%M:%S"
    )
    return latest, modified


def _last_processed(events: pd.DataFrame) -> str:
    # The authoritative latest processed observation is stored by the
    # pipeline in state. Event history is only a fallback because a valid
    # snapshot may process successfully without creating a new breakout.
    try:
        state = load_state(STATE_JSON)
        state_ts = state.get("last_observation_timestamp")
        parsed_state_ts = pd.to_datetime(state_ts, errors="coerce")
        if pd.notna(parsed_state_ts):
            return parsed_state_ts.strftime("%d %b %Y, %H:%M:%S")
    except Exception:
        pass

    if events.empty or "observation_timestamp" not in events.columns:
        return "—"

    values = pd.to_datetime(
        events["observation_timestamp"], errors="coerce"
    ).dropna()

    if values.empty:
        return "—"

    return values.max().strftime("%d %b %Y, %H:%M:%S")


def _display_events(df: pd.DataFrame, historical: bool = False) -> pd.DataFrame:
    mapping = [
        ("observation_timestamp", "Observation Time"),
        ("symbol", "Symbol"),
        ("direction", "Direction"),
        ("open_price", "Open Price"),
        ("current_price", "Current Price"),
        ("opening_straddle_premium", "Opening Straddle"),
        ("expected_1x_price", "Expected 1× Price"),
        ("breakout_distance", "Breakout Distance"),
    ]

    if historical:
        mapping.append(("strategy_version", "Strategy Version"))

    available = [(source, label) for source, label in mapping if source in df.columns]
    if not available:
        return pd.DataFrame()

    result = df[[source for source, _ in available]].copy()
    result.columns = [label for _, label in available]
    return result


def _rank01(series: pd.Series) -> pd.Series:
    """Cross-sectional 0..1 intensity rank; NaN remains neutral."""
    values = pd.to_numeric(series, errors="coerce")
    if values.notna().sum() <= 1:
        return pd.Series(
            np.where(values.notna(), 0.5, np.nan),
            index=series.index,
            dtype=float,
        )

    ranks = values.abs().rank(method="average", pct=True)
    return ranks.clip(0.0, 1.0)


def _gravity_band(score: float) -> str:
    if pd.isna(score):
        return "NEUTRAL"
    if score >= 80:
        return "VERY STRONG"
    if score >= 65:
        return "STRONG"
    if score >= 50:
        return "MODERATE"
    return "CAUTION"


def _gravity_style(value):
    if value == "VERY STRONG":
        return "background-color:#b7e4c7;color:#12552d;font-weight:700;"
    if value == "STRONG":
        return "background-color:#d9f0df;color:#1f6335;font-weight:700;"
    if value == "MODERATE":
        return "background-color:#fff1b8;color:#705800;font-weight:700;"
    if value == "CAUTION":
        return "background-color:#ffd8a8;color:#7a3d00;font-weight:700;"
    return "background-color:#e9edf3;color:#596273;font-weight:700;"


def _load_current_source_features(latest: Path | None) -> pd.DataFrame:
    """
    Dashboard-only read of the latest source workbook.

    This does NOT modify pipeline/state and does NOT change the frozen base.
    The source workbook is used only to enrich the visual gravity display.
    """
    if latest is None or not latest.exists():
        return pd.DataFrame()

    try:
        raw = pd.read_excel(latest)
    except Exception:
        return pd.DataFrame()

    if "Symbol" not in raw.columns:
        return pd.DataFrame()

    raw["Symbol"] = raw["Symbol"].astype(str).str.strip().str.upper()

    wanted = [
        "Symbol",
        "Price Chg %",
        "IV Chg %",
        "OI Chg %",
        "PCR Chg %",
        "Tot CE OI Chg %",
        "Tot PE OI Chg %",
        "Tot PE-CE OI Chg",
    ]

    available = [c for c in wanted if c in raw.columns]
    result = raw[available].copy()

    for col in available:
        if col != "Symbol":
            result[col] = pd.to_numeric(result[col], errors="coerce")

    return result.drop_duplicates("Symbol", keep="last")


def _build_gravity_table(approaching: pd.DataFrame, latest: Path | None):
    if approaching.empty:
        return pd.DataFrame()

    base = approaching.copy()
    if "symbol" not in base.columns:
        return pd.DataFrame()

    base["symbol"] = base["symbol"].astype(str).str.strip().str.upper()

    source = _load_current_source_features(latest)
    if not source.empty:
        base = base.merge(source, left_on="symbol", right_on="Symbol", how="left")
        base = base.drop(columns=["Symbol"], errors="ignore")

    # Evidence intensity components.
    progress = pd.to_numeric(
        base.get("approach_progress_pct", pd.Series(index=base.index)),
        errors="coerce",
    ).clip(lower=50, upper=100)
    progress_score = ((progress - 50.0) / 50.0).clip(0, 1)

    price_score = _rank01(base.get("Price Chg %", pd.Series(index=base.index)))
    oi_score = _rank01(base.get("OI Chg %", pd.Series(index=base.index)))
    iv_score = _rank01(base.get("IV Chg %", pd.Series(index=base.index)))
    pcr_score = _rank01(base.get("PCR Chg %", pd.Series(index=base.index)))
    oi_imbalance_score = _rank01(
        base.get("Tot PE-CE OI Chg", pd.Series(index=base.index))
    )

    # Current UI score is deliberately a VISUAL EVIDENCE-GRAVITY score.
    # It is not a probability and is not a trading rule.
    score = (
        progress_score.fillna(0.5) * 45.0
        + price_score.fillna(0.5) * 15.0
        + oi_score.fillna(0.5) * 12.0
        + iv_score.fillna(0.5) * 8.0
        + pcr_score.fillna(0.5) * 8.0
        + oi_imbalance_score.fillna(0.5) * 12.0
    )

    base["gravity_score"] = score.round(1)
    base["gravity"] = base["gravity_score"].map(_gravity_band)

    # Directional price alignment is shown separately.
    direction = base.get("direction", pd.Series(index=base.index)).astype(str).str.upper()
    price_chg = pd.to_numeric(base.get("Price Chg %", pd.Series(index=base.index)), errors="coerce")

    alignment = np.where(
        (direction == "UP") & (price_chg > 0),
        "✓",
        np.where(
            (direction == "DOWN") & (price_chg < 0),
            "✓",
            np.where(price_chg.isna(), "—", "×"),
        ),
    )
    base["price_alignment"] = alignment

    display = pd.DataFrame(
        {
            "Time": base.get("observation_timestamp", ""),
            "Symbol": base.get("symbol", ""),
            "Direction": base.get("direction", ""),
            "Progress %": pd.to_numeric(
                base.get("approach_progress_pct"), errors="coerce"
            ).round(1),
            "Price Chg %": pd.to_numeric(
                base.get("Price Chg %"), errors="coerce"
            ).round(2),
            "OI Chg %": pd.to_numeric(
                base.get("OI Chg %"), errors="coerce"
            ).round(2),
            "IV Chg %": pd.to_numeric(
                base.get("IV Chg %"), errors="coerce"
            ).round(2),
            "PCR Chg %": pd.to_numeric(
                base.get("PCR Chg %"), errors="coerce"
            ).round(2),
            "CE OI Chg %": pd.to_numeric(
                base.get("Tot CE OI Chg %"), errors="coerce"
            ).round(2),
            "PE OI Chg %": pd.to_numeric(
                base.get("Tot PE OI Chg %"), errors="coerce"
            ).round(2),
            "PE-CE OI Chg": pd.to_numeric(
                base.get("Tot PE-CE OI Chg"), errors="coerce"
            ),
            "Price Align": base["price_alignment"],
            "Gravity": base["gravity"],
            "Gravity Score": base["gravity_score"],
        }
    )

    # Sort using the actual display column name. The prior version sorted
    # on the internal `gravity_score` name after that column had been
    # replaced by the user-facing `Gravity Score` column, causing the
    # KeyError shown in the 14-Aug dashboard PDF.
    return display.sort_values(
        ["Gravity Score", "Progress %", "Symbol"],
        ascending=[False, False, True],
    ).reset_index(drop=True)



# ---------------------------------------------------------------------------
# Decision-support helpers
# ---------------------------------------------------------------------------

def _safe_num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def _direction_price_alignment(direction: pd.Series, price: pd.Series) -> pd.Series:
    d = direction.astype(str).str.upper()
    p = pd.to_numeric(price, errors="coerce")
    return pd.Series(
        np.where(
            (d == "UP") & (p > 0), "✓",
            np.where((d == "DOWN") & (p < 0), "✓",
                     np.where(p.isna(), "—", "×")),
        ),
        index=direction.index,
    )


def _evidence_score(base: pd.DataFrame) -> pd.Series:
    """UI triage score only; not a probability and not a trading rule."""
    progress = _safe_num(base, "approach_progress_pct").clip(50, 100)
    progress_component = ((progress - 50.0) / 50.0).clip(0, 1) * 45.0

    price = _safe_num(base, "Price Chg %")
    oi = _safe_num(base, "OI Chg %")
    iv = _safe_num(base, "IV Chg %")
    pcr = _safe_num(base, "PCR Chg %")
    pe_ce = _safe_num(base, "Tot PE-CE OI Chg")

    def pct_rank(s):
        if s.notna().sum() <= 1:
            return pd.Series(np.where(s.notna(), 0.5, np.nan), index=s.index, dtype=float)
        return s.abs().rank(method="average", pct=True).clip(0, 1)

    direction = base.get("direction", pd.Series("", index=base.index)).astype(str).str.upper()
    price_align = _direction_price_alignment(direction, price)
    price_component = np.where(price_align == "✓", 15.0, np.where(price_align == "—", 7.5, 0.0))

    # These components measure evidence activity/intensity. They are deliberately
    # not treated as directional truth and are shown as supporting evidence only.
    oi_component = pct_rank(oi).fillna(0.5) * 12.0
    iv_component = pct_rank(iv).fillna(0.5) * 8.0
    pcr_component = pct_rank(pcr).fillna(0.5) * 8.0
    oi_imb_component = pct_rank(pe_ce).fillna(0.5) * 12.0

    return pd.Series(
        progress_component + price_component + oi_component + iv_component + pcr_component + oi_imb_component,
        index=base.index,
    ).round(1)


def _priority_band(score: float) -> str:
    if pd.isna(score):
        return "NEUTRAL"
    if score >= 80:
        return "VERY STRONG"
    if score >= 65:
        return "STRONG"
    if score >= 50:
        return "MODERATE"
    return "CAUTION"


def _decision_label(progress: float, score: float, alignment: str) -> str:
    if pd.isna(progress):
        return "INSUFFICIENT DATA"
    if progress >= 100:
        return "BREAKOUT / BREAKDOWN"
    if score >= 80 and progress >= 75 and alignment == "✓":
        return "HIGH PRIORITY"
    if score >= 65 and progress >= 65:
        return "WATCH CLOSELY"
    if score >= 50:
        return "WATCH"
    return "WAIT"


def _build_decision_table(approaching: pd.DataFrame, latest: Path | None) -> pd.DataFrame:
    if approaching.empty or "symbol" not in approaching.columns:
        return pd.DataFrame()

    base = approaching.copy()
    base["symbol"] = base["symbol"].astype(str).str.strip().str.upper()

    # One latest 50%-record per symbol is expected from the authoritative
    # persistence layer. Defensive de-duplication keeps the dashboard concise.
    if "observation_timestamp" in base.columns:
        base["_ts"] = pd.to_datetime(base["observation_timestamp"], errors="coerce")
        base = base.sort_values(["symbol", "_ts"]).drop_duplicates("symbol", keep="last")

    source = _load_current_source_features(latest)
    if not source.empty:
        base = base.merge(source, left_on="symbol", right_on="Symbol", how="left")
        base = base.drop(columns=["Symbol"], errors="ignore")

    base["evidence_score"] = _evidence_score(base)
    base["priority"] = base["evidence_score"].map(_priority_band)

    progress = _safe_num(base, "approach_progress_pct").round(1)
    direction = base.get("direction", pd.Series("", index=base.index)).astype(str).str.upper()
    price = _safe_num(base, "Price Chg %")
    alignment = _direction_price_alignment(direction, price)
    base["price_alignment"] = alignment

    decision = [
        _decision_label(p, s, a)
        for p, s, a in zip(progress, base["evidence_score"], alignment)
    ]
    base["decision"] = decision

    # Compact, decision-oriented display. Raw CE/PE/OI/PCR columns remain
    # available in source files and historical evidence; they are not repeated
    # in the primary decision table.
    display = pd.DataFrame({
        "Rank": range(1, len(base) + 1),
        "Symbol": base["symbol"],
        "Direction": direction,
        "50% Progress": progress,
        "To 100%": (100.0 - progress).clip(lower=0).round(1),
        "Priority": base["priority"],
        "Decision": base["decision"],
        "Price": alignment,
        "Price Chg %": price.round(2),
        "OI Chg %": _safe_num(base, "OI Chg %").round(2),
        "IV Chg %": _safe_num(base, "IV Chg %").round(2),
        "Evidence Score": base["evidence_score"],
        "Time": base.get("observation_timestamp", ""),
    })

    return display.sort_values(
        ["Evidence Score", "50% Progress", "Symbol"],
        ascending=[False, False, True],
    ).reset_index(drop=True).assign(Rank=lambda x: range(1, len(x) + 1))


def _priority_style(value):
    styles = {
        "VERY STRONG": "background-color:#b7e4c7;color:#12552d;font-weight:700;",
        "STRONG": "background-color:#d9f0df;color:#1f6335;font-weight:700;",
        "MODERATE": "background-color:#fff1b8;color:#705800;font-weight:700;",
        "CAUTION": "background-color:#ffd8a8;color:#7a3d00;font-weight:700;",
        "NEUTRAL": "background-color:#e9edf3;color:#596273;font-weight:700;",
    }
    return styles.get(value, "")


def _decision_style(value):
    if value in {"BREAKOUT / BREAKDOWN", "HIGH PRIORITY"}:
        return "background-color:#b7e4c7;color:#12552d;font-weight:700;"
    if value == "WATCH CLOSELY":
        return "background-color:#fff1b8;color:#705800;font-weight:700;"
    if value == "WATCH":
        return "background-color:#e9edf3;color:#3f4a5d;font-weight:700;"
    return "color:#6b7280;"

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="sdl-header">
        <div class="sdl-header-title">SDL — Straddle Breakout</div>
        <div class="sdl-header-subtitle">
            Phase-1 breakout monitor • 50% reach evidence • decision-support ranking
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Processing action
# ---------------------------------------------------------------------------

action_col, info_col = st.columns([1, 2.2])
with action_col:
    process_clicked = st.button("▶  Process Latest Snapshot", type="primary", width="stretch")
with info_col:
    st.markdown(
        '<div class="muted" style="padding-top:11px;">'
        "Reads the newest Daywise workbook for today and leaves the frozen Phase-1 base unchanged."
        "</div>",
        unsafe_allow_html=True,
    )

if process_clicked:
    try:
        latest_processed, new_events, _, note = process_latest_snapshot_for_today()
        if latest_processed is None:
            st.warning(note)
        else:
            st.success(f"Processed: {Path(latest_processed).name}")
            st.caption(note)
            st.rerun()
    except Exception as exc:
        st.error(f"Processing failed: {exc}")

# ---------------------------------------------------------------------------
# Snapshot status
# ---------------------------------------------------------------------------

events = _events()
today_events = _today_events(events)
latest, file_modified = _latest_workbook()

up_count = int((today_events["direction"] == "UP").sum()) if not today_events.empty and "direction" in today_events.columns else 0
down_count = int((today_events["direction"] == "DOWN").sum()) if not today_events.empty and "direction" in today_events.columns else 0

approaching_path = Path(EVENT_CSV).parent / "approaching_breakouts.csv"
approaching = load_latest_approaching_breakouts(approaching_path)
if approaching is None:
    approaching = pd.DataFrame()

today = pd.Timestamp.now().date().isoformat()
if not approaching.empty and "trading_date" in approaching.columns:
    today_approaching = approaching.loc[
        approaching["trading_date"].map(_normalise_trading_date) == today
    ].copy()
else:
    today_approaching = pd.DataFrame()

latest_name = latest.name if latest else "Not found"
last_processed = _last_processed(events)

decision_table = _build_decision_table(today_approaching, latest)

counts = {
    "VERY STRONG": int((decision_table["Priority"] == "VERY STRONG").sum()) if not decision_table.empty else 0,
    "STRONG": int((decision_table["Priority"] == "STRONG").sum()) if not decision_table.empty else 0,
    "MODERATE": int((decision_table["Priority"] == "MODERATE").sum()) if not decision_table.empty else 0,
    "CAUTION": int((decision_table["Priority"] == "CAUTION").sum()) if not decision_table.empty else 0,
}

st.markdown('<div class="section-card"><div class="section-title">◷ Snapshot Status</div>', unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Breakouts Today", up_count + down_count)
with c2:
    st.metric("50% Candidates", len(decision_table))
with c3:
    st.metric("Very Strong", counts["VERY STRONG"])
with c4:
    st.metric("Strong", counts["STRONG"])
with c5:
    st.metric("Last Processed", last_processed)
st.caption(f"Latest source: {latest_name} • modified {file_modified or '—'}")
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Decision center
# ---------------------------------------------------------------------------

st.markdown('<div class="section-card"><div class="section-title">◆ Today — Decision Center</div>', unsafe_allow_html=True)
st.caption(
    "Use the 100% section for confirmed Phase-1 breakouts. Use the 50%-99% tabs to rank approaching candidates. "
    "Priority is an evidence-triage score, NOT a probability and does not change the frozen breakout rule."
)

# Confirmed 100% events remain separate from approaching candidates.
st.markdown("**100% Breakout / Breakdown — Confirmed**")
if today_events.empty:
    st.info("No confirmed 100% straddle breakout/breakdown today.")
else:
    breakout_display = _display_events(today_events)
    st.dataframe(breakout_display, width="stretch", hide_index=True)

st.markdown("**50%–99% — Approaching Candidates**")
if decision_table.empty:
    st.info("No persisted 50% approaching candidates for today.")
else:
    labels = [
        f"ALL ({len(decision_table)})",
        f"VERY STRONG ({counts['VERY STRONG']})",
        f"STRONG ({counts['STRONG']})",
        f"MODERATE ({counts['MODERATE']})",
        f"CAUTION ({counts['CAUTION']})",
    ]
    tabs = st.tabs(labels)
    groups = [
        decision_table,
        decision_table[decision_table["Priority"] == "VERY STRONG"],
        decision_table[decision_table["Priority"] == "STRONG"],
        decision_table[decision_table["Priority"] == "MODERATE"],
        decision_table[decision_table["Priority"] == "CAUTION"],
    ]
    for tab, group in zip(tabs, groups):
        with tab:
            if group.empty:
                st.info("No candidates in this band.")
            else:
                styled = group.style.map(_priority_style, subset=["Priority"]).map(_decision_style, subset=["Decision"])
                st.dataframe(styled, width="stretch", hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Historical evidence — kept out of the main decision table
# ---------------------------------------------------------------------------

with st.expander("▣ Historical Evidence", expanded=False):
    if events.empty and approaching.empty:
        st.info("No historical evidence recorded yet.")
    else:
        tab_50, tab_breakouts = st.tabs(["50% Reached History", "Breakout History"])
        with tab_50:
            if approaching.empty or "trading_date" not in approaching.columns:
                st.info("No 50% history available.")
            else:
                dates_50 = sorted(approaching["trading_date"].map(_normalise_trading_date).dropna().unique(), reverse=True)
                selected_50 = st.selectbox("Trading date", dates_50, key="history_50_date")
                hist_50 = approaching.loc[approaching["trading_date"].map(_normalise_trading_date) == selected_50].copy()
                st.dataframe(hist_50, width="stretch", hide_index=True)
                st.download_button(
                    "⇩ Export 50% CSV",
                    data=hist_50.to_csv(index=False).encode("utf-8"),
                    file_name=f"sdl_approaching_{selected_50}.csv",
                    mime="text/csv",
                )
        with tab_breakouts:
            if events.empty or "trading_date" not in events.columns:
                st.info("No breakout history available.")
            else:
                dates = sorted(events["trading_date"].map(_normalise_trading_date).dropna().unique(), reverse=True)
                selected_b = st.selectbox("Trading date", dates, key="history_breakout_date")
                hist_b = events.loc[events["trading_date"].map(_normalise_trading_date) == selected_b].copy()
                st.dataframe(_display_events(hist_b, historical=True), width="stretch", hide_index=True)
                st.download_button(
                    "⇩ Export breakout CSV",
                    data=hist_b.to_csv(index=False).encode("utf-8"),
                    file_name=f"sdl_breakouts_{selected_b}.csv",
                    mime="text/csv",
                )

st.markdown(
    '<div class="footer"><span>SDL Phase-1 • Frozen breakout logic preserved</span>'
    '<span>Decision Center = dashboard evidence layer only</span></div>',
    unsafe_allow_html=True,
)
