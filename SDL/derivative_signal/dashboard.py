from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

try:
    from config import INTRADAY_SOURCE_ROOT
except Exception:
    INTRADAY_SOURCE_ROOT = HERE

from multi_source_adapter import discover_sources, load_and_merge
from signal_engine import build_signal

BIAS_ORDER = [
    "STRONG BULLISH", "BULLISH", "MILD BULLISH", "DEVELOPING BULLISH",
    "CONFLICT", "NEUTRAL / NO SIGNAL",
    "DEVELOPING BEARISH", "MILD BEARISH", "BEARISH", "STRONG BEARISH",
]
EVIDENCE_ORDER = ["CONFIRMED", "PARTIAL", "DEVELOPING", "WAIT LEVEL", "CONFLICT", "INCOMPLETE", "NO SIGNAL"]


def _safe_float(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _prepare_rows(bundle):
    if bundle.rows is None or bundle.rows.empty:
        return pd.DataFrame()

    rows = bundle.rows.copy()
    opening = bundle.opening_rows
    if opening is not None and not opening.empty and "symbol" in opening.columns:
        opening = opening.set_index("symbol")

    progress = []
    for _, r in rows.iterrows():
        symbol = str(r.get("symbol", "")).strip().upper()
        cur = _safe_float(r.get("atm_straddle_price"))
        op = None
        if opening is not None and symbol in opening.index:
            op = _safe_float(opening.loc[symbol].get("atm_straddle_price"))
        if cur is not None and op not in (None, 0):
            progress.append(abs(cur - op) / abs(op) * 100.0)
        else:
            progress.append(None)
    rows["straddle_progress_pct"] = progress

    # Never let a generic Price field populate Price Chg %.
    rows["price_chg_pct"] = pd.to_numeric(rows.get("price_chg_pct"), errors="coerce")
    rows["close"] = pd.to_numeric(rows.get("close"), errors="coerce")

    results = [build_signal(r.to_dict()) for _, r in rows.iterrows()]
    return pd.DataFrame(results)


def _decision_label(bias: str) -> str:
    return {
        "STRONG BULLISH": "🟢🟢 STRONG BULLISH",
        "BULLISH": "🟢 BULLISH",
        "MILD BULLISH": "🟢 MILD BULLISH",
        "DEVELOPING BULLISH": "🟠 DEVELOPING BULLISH",
        "CONFLICT": "🟣 CONFLICT",
        "NEUTRAL / NO SIGNAL": "⚪ NO SIGNAL",
        "DEVELOPING BEARISH": "🟠 DEVELOPING BEARISH",
        "MILD BEARISH": "🔴 MILD BEARISH",
        "BEARISH": "🔴 BEARISH",
        "STRONG BEARISH": "🔴🔴 STRONG BEARISH",
    }.get(str(bias), "⚪ NO SIGNAL")


def _style_row(row):
    bias = str(row.get("Bias", ""))
    for label, category in {
        "🟢🟢 STRONG BULLISH": "STRONG BULLISH",
        "🟢 BULLISH": "BULLISH",
        "🟢 MILD BULLISH": "MILD BULLISH",
        "🟠 DEVELOPING BULLISH": "DEVELOPING BULLISH",
        "🟣 CONFLICT": "CONFLICT",
        "🟠 DEVELOPING BEARISH": "DEVELOPING BEARISH",
        "🔴 MILD BEARISH": "MILD BEARISH",
        "🔴 BEARISH": "BEARISH",
        "🔴🔴 STRONG BEARISH": "STRONG BEARISH",
        "⚪ NO SIGNAL": "NEUTRAL / NO SIGNAL",
    }.items():
        if bias == label:
            bias = category
            break
    if bias == "STRONG BULLISH": bg, fg = "#d9f5df", "#14532d"
    elif bias == "BULLISH": bg, fg = "#e8f8ea", "#166534"
    elif bias == "MILD BULLISH": bg, fg = "#f1faef", "#166534"
    elif bias == "DEVELOPING BULLISH": bg, fg = "#fff4df", "#9a6700"
    elif bias == "CONFLICT": bg, fg = "#f3e8ff", "#6b21a8"
    elif bias == "DEVELOPING BEARISH": bg, fg = "#fff4df", "#9a6700"
    elif bias == "MILD BEARISH": bg, fg = "#fff0f0", "#991b1b"
    elif bias == "BEARISH": bg, fg = "#ffe7e7", "#991b1b"
    elif bias == "STRONG BEARISH": bg, fg = "#f9dada", "#991b1b"
    else: bg, fg = "#f5f5f5", "#555"
    return [f"background-color:{bg};color:{fg};font-weight:600"] * len(row)


def _strength_text(v):
    n = max(0, min(5, int(v or 0)))
    return "●" * n + "○" * (5 - n)


def render():
    st.title("NTIS SDL — Decision Dashboard")
    st.caption("Trading-oriented multi-source decision layer. Existing SDL pipeline remains read-only and unchanged.")

    trading_date = st.date_input("Trading date", value=date.today(), key="ds_date").isoformat()
    bundle = discover_sources(INTRADAY_SOURCE_ROOT, trading_date)

    st.subheader("Source Readiness")
    cols = st.columns(6)
    roles = ["BASE", "FUTURES", "IV", "SUPPORT", "RESISTANCE", "VOLUME"]
    for col, role in zip(cols, roles):
        path = bundle.files.get(role)
        col.metric(role, "FOUND" if path else "MISSING")

    if bundle.files:
        with st.expander("Source files used", expanded=False):
            for role, path in bundle.files.items():
                st.write(f"**{role}:** `{path}`")
            if bundle.base_history:
                st.caption(f"BASE snapshots discovered: {len(bundle.base_history)} — earliest used for straddle-progress baseline.")
    if bundle.missing:
        st.warning("Missing source families: " + ", ".join(bundle.missing))
    for error in bundle.errors:
        st.error(error)

    if "ds_bundle" not in st.session_state:
        st.session_state.ds_bundle = None

    if st.button("▶ PROCESS TODAY'S DATA", type="primary", width="stretch"):
        processed = load_and_merge(bundle)
        st.session_state.ds_bundle = processed
        st.session_state.ds_result = None

    bundle = st.session_state.ds_bundle
    if bundle is None:
        st.info("Review the detected source files and press PROCESS TODAY'S DATA.")
        return
    if bundle.rows is None or bundle.rows.empty:
        st.error("No merged symbol data is available.")
        return

    result = _prepare_rows(bundle)
    if result.empty:
        st.error("Decision engine returned no records.")
        return
    st.session_state.ds_result = result

    # Summary by final bias, not raw price direction.
    counts = result["bias_category"].value_counts()
    c = st.columns(5)
    c[0].metric("Symbols", len(result))
    c[1].metric("Strong Bullish", int(counts.get("STRONG BULLISH", 0)))
    c[2].metric("Bullish", int(counts.get("BULLISH", 0) + counts.get("MILD BULLISH", 0)))
    c[3].metric("Bearish", int(counts.get("BEARISH", 0) + counts.get("MILD BEARISH", 0)))
    c[4].metric("Conflict", int(counts.get("CONFLICT", 0)))

    st.subheader("Decision Signals")
    f1, f2, f3 = st.columns([1.5, 1.2, 1.2])
    with f1:
        bias_filter = st.selectbox("Bias Category", ["ALL"] + BIAS_ORDER, key="ds_bias_filter")
    with f2:
        evidence_filter = st.selectbox("Evidence State", ["ALL"] + EVIDENCE_ORDER, key="ds_evidence_filter")
    with f3:
        direction_filter = st.selectbox("Direction", ["ALL", "BULLISH", "BEARISH", "NEUTRAL"], key="ds_direction_filter")
    show_all = st.checkbox("Show full universe", False, key="ds_show_all")

    filtered = result.copy()
    if bias_filter != "ALL":
        filtered = filtered[filtered.bias_category == bias_filter]
    if evidence_filter != "ALL":
        filtered = filtered[filtered.evidence_state == evidence_filter]
    if direction_filter != "ALL":
        filtered = filtered[filtered.direction == direction_filter]
    if not show_all:
        filtered = filtered[filtered.bias_category != "NEUTRAL / NO SIGNAL"]

    bias_rank = {b: i for i, b in enumerate(BIAS_ORDER)}
    filtered = filtered.assign(_rank=filtered.bias_category.map(bias_rank).fillna(99))
    filtered = filtered.sort_values(["_rank", "strength", "price_change_pct"], ascending=[True, False, False])

    st.caption(f"Showing {len(filtered)} of {len(result)} symbols. Filter operates on FINAL BIAS CATEGORY, not raw price direction.")

    if filtered.empty:
        st.info("No stocks match the selected filters.")
    else:
        table = pd.DataFrame({
            "Symbol": filtered.symbol,
            "Bias": filtered.bias_category.map(_decision_label),
            "Evidence": filtered.evidence_state,
            "Price %": filtered.price_change_pct.map(lambda x: "—" if pd.isna(x) else f"{x:+.2f}%"),
            "PE-CE OI": filtered.options_structure,
            "Futures": filtered.futures_buildup,
            "Fut OI %": filtered.futures_oi_change_pct.map(lambda x: "—" if pd.isna(x) else f"{x:+.2f}%"),
            "Straddle Progress %": filtered.straddle_progress_pct.map(lambda x: "—" if pd.isna(x) else f"{x:.1f}%"),
            "Straddle Stage": filtered.straddle_stage,
            "S/R": filtered.location,
            "Strength": filtered.strength.map(_strength_text),
        })
        st.dataframe(table.style.apply(_style_row, axis=1), width="stretch", hide_index=True)

    st.subheader("Decision Detail")
    options = filtered.symbol.tolist()
    if options:
        symbol = st.selectbox("Inspect stock", options, key="ds_symbol")
        row = filtered.loc[filtered.symbol == symbol].iloc[0]
        st.markdown(f"### {_decision_label(row.bias_category)}")
        st.write(f"**Direction:** {row.direction}  |  **Evidence:** {row.evidence_state}  |  **Strength:** {int(row.strength)}/5")
        for reason in row.reasons:
            st.write(f"- {reason}")
        a,b,c,d = st.columns(4)
        a.metric("CMP", f"{row.reference_price:.2f}" if pd.notna(row.reference_price) else "—")
        b.metric("Support", f"{row.support:.2f}" if pd.notna(row.support) else "—")
        c.metric("Resistance", f"{row.resistance:.2f}" if pd.notna(row.resistance) else "—")
        d.metric("Straddle Progress", f"{row.straddle_progress_pct:.1f}%" if pd.notna(row.straddle_progress_pct) else "—")
        with st.expander("Detailed evidence", expanded=False):
            st.write({
                "PE-CE value": row.pece_value,
                "PE-CE direction": row.options_direction,
                "Futures direction": row.futures_direction,
                "Futures OI %": row.futures_oi_change_pct,
                "IV change %": row.iv_change_pct,
                "IVR": row.ivr,
                "IVP": row.ivp,
                "Volume change %": row.volume_change_pct,
                "OI change %": row.oi_change_pct,
                "S/R location": row.location,
                "Level distance %": row.level_distance_pct,
                "Confirmation count": row.confirmation_count,
                "Conflict count": row.conflict_count,
            })

    st.caption("Price % comes only from the explicit Price Chg % source field. Final Bias is separate from Direction. WATCH/DEVELOPING/CONFLICT states never masquerade as confirmed trades.")


if __name__ == "__main__":
    render()
