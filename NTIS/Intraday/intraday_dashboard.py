"""
NTIS Intraday Predictive Decision Cockpit
Phase 22A-1 — Predictive selection semantics refinement.

Design boundary:
- Existing producers remain authoritative.
- No new numeric prediction score is created.
- Exact pattern evidence is preferred over stock-level history.
- Stock history is displayed separately from outcome-confirmed evidence.
- Zero completed outcomes is rendered as "No completed outcomes", never as 0% success.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import subprocess
import sys
import time

import pandas as pd
import streamlit as st

from config_loader import OUTPUT_ROOT, LEARNING_ROOT, SCREENSHOT_ROOT
from dashboard.dashboard_loader import load_dashboard_data, build_snapshot_path, safe_read
from dashboard.dashboard_sidebar import build_sidebar_filters
from intraday_dashboard_health_panel import health_status
from intraday_intelligence_loader import IntradayIntelligenceLoader
from intraday_intelligence_query import IntradayIntelligenceQuery
from intraday_latest_snapshot_resolver import IntradayLatestSnapshotResolver


st.set_page_config(
    page_title="NTIS Intraday Predictive Decision Cockpit",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
<style>
:root {
    --navy:#0b1735; --navy2:#142653; --purple:#6d3df5;
    --ink:#172033; --muted:#667085; --line:#e6e9f0;
    --good:#14804a; --warn:#b76b00; --bad:#c43d4b; --soft:#f7f8fb;
}
.hero {background:linear-gradient(120deg,#0b1735,#142653);padding:26px 30px;border-radius:16px;color:white;margin-bottom:16px}
.hero h1 {margin:0;font-size:30px}.hero p{margin:7px 0 0;color:#cbd5e1}
.pill {display:inline-block;padding:5px 10px;border-radius:999px;background:#243766;color:#fff;font-size:12px;margin-right:6px}
.card {background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 3px 14px rgba(15,23,42,.05)}
.card .label {font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.card .value {font-size:26px;font-weight:750;color:var(--ink);margin-top:4px}
.status-high {color:#fff;background:#14804a;padding:5px 10px;border-radius:999px;font-weight:700;font-size:11px}
.status-supported {color:#fff;background:#2d6cdf;padding:5px 10px;border-radius:999px;font-weight:700;font-size:11px}
.status-early {color:#fff;background:#c47b08;padding:5px 10px;border-radius:999px;font-weight:700;font-size:11px}
.status-signal {color:#fff;background:#7b61a8;padding:5px 10px;border-radius:999px;font-weight:700;font-size:11px}
.status-watch {color:#fff;background:#667085;padding:5px 10px;border-radius:999px;font-weight:700;font-size:11px}
.decision-card {border:1px solid var(--line);border-left:5px solid var(--purple);border-radius:14px;padding:18px;background:#fff}
.section-title {font-size:19px;font-weight:750;color:var(--ink);margin:12px 0 8px}
.small {font-size:12px;color:var(--muted)}
.warning-box {background:#fff8e8;border:1px solid #f2d28b;border-radius:10px;padding:12px}
.info-box {background:#f4f1ff;border:1px solid #d9cdfc;border-radius:10px;padding:12px}
</style>
""",
    unsafe_allow_html=True,
)


def _clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(row, *names, default=""):
    for name in names:
        if name in row.index:
            value = row.get(name)
            if _clean(value) not in {"", "nan", "None"}:
                return value
    return default


def _pattern_identity(row):
    return {
        "id": _clean(_first(row, "Business_Pattern_ID", "Pattern_ID")),
        "dna": _clean(_first(row, "Pattern_Fingerprint", "Pattern_DNA")),
        "name": _clean(_first(row, "Pattern", "Pattern_Name")),
    }


def _historical_stats(records):
    if records.empty:
        return {
            "observations": 0,
            "wins": 0,
            "losses": 0,
            "completed": 0,
            "success": None,
            "avg_pnl": None,
            "evidence": "NONE",
            "first_seen": None,
            "last_seen": None,
        }

    wins = int(pd.to_numeric(records.get("Successful_Trades", 0), errors="coerce").fillna(0).sum())
    losses = int(pd.to_numeric(records.get("Failed_Trades", 0), errors="coerce").fillna(0).sum())
    occurrences = int(pd.to_numeric(records.get("Occurrences", len(records)), errors="coerce").fillna(0).sum())
    completed = wins + losses

    # Repository Success_% is authoritative when outcomes exist.
    success = (wins * 100.0 / completed) if completed else None

    avg_pnl = None
    if completed and "Average_PnL" in records.columns:
        vals = pd.to_numeric(records["Average_PnL"], errors="coerce").dropna()
        if not vals.empty:
            avg_pnl = round(float(vals.mean()), 2)

    evidence = "NONE"
    if "Evidence_Level" in records.columns and not records["Evidence_Level"].dropna().empty:
        evidence = _clean(records["Evidence_Level"].dropna().iloc[-1]).upper() or "NONE"

    first_seen = None
    last_seen = None
    if "First_Seen" in records.columns:
        vals = records["First_Seen"].dropna().astype(str)
        if not vals.empty:
            first_seen = vals.min()
    if "Last_Seen" in records.columns:
        vals = records["Last_Seen"].dropna().astype(str)
        if not vals.empty:
            last_seen = vals.max()

    return {
        "observations": occurrences,
        "wins": wins,
        "losses": losses,
        "completed": completed,
        "success": round(success, 1) if success is not None else None,
        "avg_pnl": avg_pnl,
        "evidence": evidence,
        "first_seen": first_seen,
        "last_seen": last_seen,
    }


def _exact_pattern_records(row, query):
    ident = _pattern_identity(row)
    if ident["id"]:
        records = query.by_pattern_id(ident["id"])
        if not records.empty:
            return records, "Business Pattern ID"
    if ident["dna"]:
        records = query.by_pattern_dna(ident["dna"])
        if not records.empty:
            return records, "Pattern Fingerprint"
    return pd.DataFrame(), "None"


def _classify(row, pattern_records, stock_records):
    pattern_stats = _historical_stats(pattern_records)
    stock_stats = _historical_stats(stock_records)

    probability = _num(_first(row, "Intraday Probability %", default=0))
    score = _num(_first(row, "NTIS Intraday Score", "Decision Score", default=0))
    signal = _clean(_first(row, "Validation Signal", default="WATCH")).upper()

    complete_plan = all(
        _clean(_first(row, c, default="")).upper() not in {"", "NONE", "NAN", "NA", "N/A"}
        for c in ("Entry Price", "Stop Loss", "Target")
    )

    # Predictive state is a classification, not a new numeric score.
    # Exact pattern outcomes outrank stock-level observation count.
    if pattern_stats["completed"] >= 10 and (pattern_stats["success"] or 0) >= 65:
        state = "HIGH-CONFIDENCE"
    elif pattern_stats["completed"] >= 5 and (pattern_stats["success"] or 0) >= 55:
        state = "SUPPORTED"
    elif pattern_stats["observations"] > 0 or stock_stats["observations"] > 0:
        state = "EARLY EVIDENCE"
    else:
        state = "SIGNAL ONLY"

    if signal == "WATCH":
        state = "WATCH"

    return {
        "state": state,
        "pattern_stats": pattern_stats,
        "stock_stats": stock_stats,
        "probability": probability,
        "score": score,
        "signal": signal,
        "complete_plan": complete_plan,
        "pattern_match_type": "Exact pattern match" if not pattern_records.empty else "No exact pattern match",
    }


def _prepare_executive(trade_df, query):
    if trade_df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in trade_df.iterrows():
        symbol = _clean(_first(row, "Symbol"))
        stock_records = query.by_symbol(symbol) if symbol else pd.DataFrame()
        pattern_records, match_type = _exact_pattern_records(row, query)
        decision = _classify(row, pattern_records, stock_records)

        out = row.to_dict()
        out.update({
            "_predictive_state": decision["state"],
            "_pattern_records": pattern_records,
            "_stock_records": stock_records,
            "_pattern_match_type": match_type,
            "_pattern_stats": decision["pattern_stats"],
            "_stock_stats": decision["stock_stats"],
            "_probability": decision["probability"],
            "_score": decision["score"],
            "_signal": decision["signal"],
            "_complete_plan": decision["complete_plan"],
        })
        rows.append(out)

    result = pd.DataFrame(rows)
    state_order = {
        "HIGH-CONFIDENCE": 0, "SUPPORTED": 1, "EARLY EVIDENCE": 2,
        "SIGNAL ONLY": 3, "WATCH": 4
    }
    result["_state_order"] = result["_predictive_state"].map(state_order).fillna(9)
    result["_outcome_count"] = result["_pattern_stats"].apply(lambda x: x["completed"])
    result["_evidence_rank"] = result["_pattern_stats"].apply(
        lambda x: {"MATURE": 4, "ESTABLISHED": 3, "DEVELOPING": 2, "NEW": 1, "NONE": 0}.get(x["evidence"], 0)
    )
    return result.sort_values(
        ["_state_order", "_evidence_rank", "_outcome_count", "_probability", "_score"],
        ascending=[True, False, False, False, False],
    ).reset_index(drop=True)


def _status_badge(state):
    css = {
        "HIGH-CONFIDENCE": "status-high",
        "SUPPORTED": "status-supported",
        "EARLY EVIDENCE": "status-early",
        "SIGNAL ONLY": "status-signal",
        "WATCH": "status-watch",
    }.get(state, "status-watch")
    return f'<span class="{css}">{state}</span>'


def _fmt_success(stats):
    return f'{stats["success"]:.1f}%' if stats["success"] is not None else "N/A"


def _fmt_pnl(stats):
    return f'{stats["avg_pnl"]:.2f}' if stats["avg_pnl"] is not None else "N/A"


def _snapshot_signature():
    root = Path(SCREENSHOT_ROOT)
    if not root.exists():
        return ""
    parts = []
    try:
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    s = p.stat()
                    parts.append(f"{p}|{s.st_size}|{s.st_mtime_ns}")
                except OSError:
                    continue
    except OSError:
        return ""
    return hashlib.sha1("\n".join(sorted(parts)).encode("utf-8")).hexdigest()


def _run_pipeline():
    project_root = Path(__file__).resolve().parent
    cmd = [sys.executable, str(project_root / "run_intraday_pipeline.py")]
    return subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=1800)


def _manual_controls():
    c1, c2, c3 = st.columns([1, 1, 1.7])
    refresh = c1.button("↻ Refresh Current Snapshot", use_container_width=True)
    process = c2.button("▶ Process Next Snapshot", use_container_width=True)
    auto = c3.toggle("Continue Automatically", value=st.session_state.get("ntis_auto", False), key="ntis_auto")
    if refresh:
        st.cache_data.clear()
        st.rerun()
    if process:
        with st.spinner("Running the existing NTIS Intraday pipeline..."):
            result = _run_pipeline()
        if result.returncode == 0:
            st.success("Pipeline completed successfully. Refreshing current snapshot.")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Pipeline failed. No dashboard data was fabricated or substituted.")
            st.code(result.stderr or result.stdout)
    return auto


def _automatic_cycle_once():
    if not st.session_state.get("ntis_auto", False):
        return
    current = _snapshot_signature()
    previous = st.session_state.get("ntis_last_signature")
    if previous is None:
        st.session_state.ntis_last_signature = current
        return
    if current and current != previous:
        with st.spinner("New/modified runtime snapshot detected — running existing pipeline..."):
            result = _run_pipeline()
        st.session_state.ntis_last_signature = _snapshot_signature()
        if result.returncode == 0:
            st.success("Automatic processing completed. Executive snapshot refreshed.")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Automatic pipeline execution failed.")
            st.code(result.stderr or result.stdout)


def _start_automatic_monitor():
    fragment = getattr(st, "fragment", None)
    if fragment is None:
        st.caption("Automatic mode is enabled, but this Streamlit runtime does not expose the required fragment refresh API.")
        return
    @fragment(run_every="30s")
    def _monitor():
        _automatic_cycle_once()
    _monitor()











ctx = load_dashboard_data()
status = ctx["status"]
snapshot_date = ctx["snapshot_date"]
base_path = ctx["base_path"]
trade_df = ctx["trade_df"]
prob_df = ctx["prob_df"]
evolution_df = ctx["evolution_df"]

intel_loader = IntradayIntelligenceLoader()
intel_loader.load()
intel_query = IntradayIntelligenceQuery(intel_loader)

st.markdown(
    f"""
<div class="hero">
<h1>NTIS Intraday Predictive Decision Cockpit</h1>
<p>Executive stock selection from current-session behaviour, exact pattern evidence, historical outcomes and trade-plan readiness.</p>
<div style="margin-top:12px">
<span class="pill">Snapshot: {snapshot_date or "UNAVAILABLE"}</span>
<span class="pill">Status: {status.get("status","UNKNOWN")}</span>
<span class="pill">Repository: CONNECTED</span>
</div>
</div>
""",
    unsafe_allow_html=True,
)

auto_mode = _manual_controls()
_start_automatic_monitor()

tabs = st.tabs([
    "Executive Decision",
    "Pattern Intelligence",
    "Historical Replay",
    "Learning & Calibration",
    "Governance & Health",
])

with tabs[0]:
    filtered = build_sidebar_filters(trade_df)
    exec_df = _prepare_executive(filtered, intel_query)

    high = int((exec_df["_predictive_state"] == "HIGH-CONFIDENCE").sum()) if not exec_df.empty else 0
    supported = int((exec_df["_predictive_state"] == "SUPPORTED").sum()) if not exec_df.empty else 0
    early = int((exec_df["_predictive_state"] == "EARLY EVIDENCE").sum()) if not exec_df.empty else 0
    signal_only = int((exec_df["_predictive_state"] == "SIGNAL ONLY").sum()) if not exec_df.empty else 0
    watch = int((exec_df["_predictive_state"] == "WATCH").sum()) if not exec_df.empty else 0
    buy = int(exec_df["_signal"].isin(["BUY", "VALID BUY"]).sum()) if not exec_df.empty else 0
    sell = int(exec_df["_signal"].isin(["SELL", "VALID SELL"]).sum()) if not exec_df.empty else 0

    cards = [
        ("HIGH CONFIDENCE", high, "evidence-backed"),
        ("SUPPORTED", supported, "historical support"),
        ("EARLY EVIDENCE", early, "observation only"),
        ("SIGNAL ONLY", signal_only, "no predictive history"),
        ("BUY / SELL", f"{buy} / {sell}", "validated direction"),
        ("WATCH", watch, "observe only"),
    ]
    cols = st.columns(6)
    for col, (label, value, sub) in zip(cols, cards):
        col.markdown(f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div><div class="small">{sub}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Top Predictive Opportunities</div>', unsafe_allow_html=True)
    if exec_df.empty:
        st.info("No current trade candidates available.")
    else:
        top_df = exec_df[exec_df["_predictive_state"].isin(["HIGH-CONFIDENCE", "SUPPORTED", "EARLY EVIDENCE"])].head(12).copy()
        if top_df.empty:
            st.info("No evidence-supported predictive opportunities yet. Current signals remain below the predictive-evidence threshold.")
        else:
            display = pd.DataFrame({
                "Stock": top_df["Symbol"].astype(str),
                "Action": top_df["_signal"],
                "Predictive Status": top_df["_predictive_state"],
                "Probability %": top_df["_probability"],
                "Pattern Evidence": top_df["_pattern_stats"].apply(lambda x: x["evidence"]),
                "Completed Outcomes": top_df["_pattern_stats"].apply(lambda x: x["completed"]),
                "Historical Success": top_df["_pattern_stats"].apply(_fmt_success),
                "Trade Plan": top_df["_complete_plan"].map({True: "READY", False: "INCOMPLETE"}),
            })
            st.dataframe(display, use_container_width=True, hide_index=True, height=360)

    st.markdown('<div class="section-title">Current Signals — Not Yet Predictive</div>', unsafe_allow_html=True)
    weak_df = exec_df[exec_df["_predictive_state"].isin(["SIGNAL ONLY", "WATCH"])].head(15) if not exec_df.empty else pd.DataFrame()
    if not weak_df.empty:
        st.dataframe(
            pd.DataFrame({
                "Stock": weak_df["Symbol"].astype(str),
                "Action": weak_df["_signal"],
                "Probability %": weak_df["_probability"],
                "Current Score": weak_df["_score"],
                "Exact Pattern Evidence": weak_df["_pattern_stats"].apply(lambda x: x["evidence"] if x["observations"] else "NONE"),
                "Completed Outcomes": weak_df["_pattern_stats"].apply(lambda x: x["completed"]),
                "Trade Plan": weak_df["_complete_plan"].map({True: "READY", False: "INCOMPLETE"}),
            }),
            use_container_width=True, hide_index=True, height=300
        )

    st.markdown('<div class="section-title">Decision Detail</div>', unsafe_allow_html=True)
    if not exec_df.empty:
        options = exec_df["Symbol"].astype(str).drop_duplicates().tolist()
        selected = st.selectbox("Select stock", options, key="predictive_stock")
        selected_rows = exec_df[exec_df["Symbol"].astype(str) == selected]
        if not selected_rows.empty:
            r = selected_rows.iloc[0]
            pstats = r["_pattern_stats"]
            sstats = r["_stock_stats"]
            state = r["_predictive_state"]
            symbol = str(r["Symbol"])
            pattern = _clean(_first(r, "Pattern", "Pattern_Name", default="N/A"))
            signal = r["_signal"]
            probability = r["_probability"]
            score = r["_score"]
            entry = _first(r, "Entry Price", default="N/A")
            stop = _first(r, "Stop Loss", default="N/A")
            target = _first(r, "Target", default="N/A")
            plan = "READY" if r["_complete_plan"] else "INCOMPLETE"

            st.markdown(
                f'<div class="decision-card"><div style="display:flex;justify-content:space-between;align-items:center"><h2 style="margin:0">{symbol}</h2>{_status_badge(state)}</div><div class="small">{pattern}</div></div>',
                unsafe_allow_html=True,
            )
            a,b,c,d = st.columns(4)
            a.metric("Decision", signal)
            b.metric("Probability", f"{probability:.0f}%")
            c.metric("NTIS Score", f"{score:.0f}")
            d.metric("Trade Plan", plan)

            e,f,g,h = st.columns(4)
            e.metric("Exact Pattern Observations", pstats["observations"])
            f.metric("Pattern Completed Outcomes", pstats["completed"])
            g.metric("Pattern Success", _fmt_success(pstats))
            h.metric("Pattern Avg PnL", _fmt_pnl(pstats))

            st.markdown("#### WHY")
            if pstats["observations"]:
                st.markdown(
                    f"Current **{signal}** for **{symbol}** is associated with **{pattern}**. "
                    f"Exact pattern evidence contains **{pstats['observations']} observation(s)** and "
                    f"**{pstats['completed']} completed outcome(s)**. "
                    f"The current-session probability is **{probability:.0f}%** and NTIS score is **{score:.0f}**."
                )
            else:
                st.markdown(
                    f"Current **{signal}** for **{symbol}** is driven by the current-session setup (**{pattern}**). "
                    "No exact historical pattern match is currently available."
                )

            st.markdown("#### WHY NOW")
            if pstats["completed"]:
                st.markdown(
                    f"The current snapshot combines the active signal with an exact historical pattern that has "
                    f"**{pstats['completed']} completed outcome(s)** and a historical success rate of **{_fmt_success(pstats)}**. "
                    f"Observation window: **{pstats['first_seen'] or 'N/A'} → {pstats['last_seen'] or 'N/A'}**."
                )
            elif pstats["observations"] or sstats["observations"]:
                st.markdown(
                    "The current snapshot is being surfaced because the current validation signal is active, "
                    "but historical outcome confirmation is still insufficient. This is an observation-stage opportunity, "
                    "not a mature predictive confirmation."
                )
            else:
                st.markdown(
                    "The current snapshot is being surfaced because the existing validation engine produced an active signal. "
                    "No historical confirmation is being implied."
                )

            st.markdown("#### EVIDENCE & EXECUTION")
            ec1, ec2 = st.columns(2)
            with ec1:
                if pstats["completed"] == 0:
                    st.markdown('<div class="warning-box"><b>Historical outcome status:</b> No completed outcomes. Success rate is N/A, not 0%.</div>', unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div class="info-box"><b>Pattern outcome evidence:</b> {pstats["wins"]} wins / {pstats["losses"]} losses; success {pstats["success"]:.1f}%.</div>',
                        unsafe_allow_html=True
                    )
            with ec2:
                st.markdown(
                    f'<div class="info-box"><b>Trade plan:</b> {plan}<br>Entry: {entry} &nbsp; Stop: {stop} &nbsp; Target: {target}</div>',
                    unsafe_allow_html=True
                )

            with st.expander("Stock-level historical footprint (separate from exact pattern evidence)"):
                if sstats["observations"]:
                    st.write(
                        f"{symbol} has {sstats['observations']} historical observation(s), "
                        f"{sstats['completed']} completed outcome(s), "
                        f"{sstats['wins']} wins and {sstats['losses']} losses."
                    )
                    cols = [c for c in [
                        "Business_Pattern_ID","Pattern_Name","Lifecycle_State","Occurrences",
                        "Successful_Trades","Failed_Trades","Success_%","Average_PnL",
                        "Confidence_Score","Evidence_Level","First_Seen","Last_Seen"
                    ] if c in r["_stock_records"].columns]
                    st.dataframe(r["_stock_records"][cols], use_container_width=True, hide_index=True, height=250)
                else:
                    st.info("No stock-level historical intelligence record is currently available.")

            if pstats["observations"]:
                with st.expander("Exact pattern historical evidence"):
                    cols = [c for c in [
                        "Business_Pattern_ID","Pattern_Name","Lifecycle_State","Occurrences",
                        "Successful_Trades","Failed_Trades","Success_%","Average_PnL",
                        "Confidence_Score","Evidence_Level","First_Seen","Last_Seen"
                    ] if c in r["_pattern_records"].columns]
                    st.dataframe(r["_pattern_records"][cols], use_container_width=True, hide_index=True, height=240)

    st.markdown('<div class="section-title">Secondary Context</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        st.caption("Sector Intelligence")
        if not exec_df.empty and "Sector" in exec_df.columns:
            sec = exec_df.groupby("Sector")["_probability"].mean().sort_values(ascending=False)
            if not sec.empty:
                st.bar_chart(sec)
    with c2:
        st.caption("Signal Evolution")
        if not evolution_df.empty:
            st.dataframe(evolution_df.head(10), use_container_width=True, hide_index=True, height=240)

with tabs[1]:
    st.subheader("Pattern Intelligence")
    intel_df = intel_loader.get_dataframe()
    if intel_df.empty:
        st.info("No pattern intelligence records available.")
    else:
        q1,q2 = st.columns(2)
        with q1:
            sym = st.text_input("Symbol filter", "").strip().upper()
        with q2:
            pid = st.text_input("Pattern ID / fingerprint filter", "").strip()
        view = intel_df.copy()
        if sym:
            view = view[view["Symbol"].astype(str).str.upper() == sym]
        if pid:
            view = view[
                view.get("Business_Pattern_ID", pd.Series("", index=view.index)).astype(str).str.contains(pid, case=False, na=False)
                | view.get("Pattern_Fingerprint", pd.Series("", index=view.index)).astype(str).str.contains(pid, case=False, na=False)
            ]
        cols = [c for c in [
            "Business_Pattern_ID","Symbol","Pattern_Name","Lifecycle_State","Occurrences",
            "Successful_Trades","Failed_Trades","Success_%","Average_PnL","Confidence_Score",
            "Historical_Probability","Historical_Confidence","Evidence_Level","First_Seen","Last_Seen"
        ] if c in view.columns]
        st.dataframe(view[cols], use_container_width=True, hide_index=True, height=420)

with tabs[2]:
    st.subheader("Historical Replay")
    resolver = IntradayLatestSnapshotResolver(SCREENSHOT_ROOT, OUTPUT_ROOT)
    snapshots = resolver.get_available_snapshots()
    if not snapshots:
        st.info("No historical replay snapshots available.")
    else:
        selected_day = st.selectbox("Historical trading date", snapshots, index=len(snapshots)-1, key="replay_day")
        hist_base = build_snapshot_path(selected_day)
        hist_file = hist_base / "intraday_backtest_results.csv"
        if hist_file.exists():
            hdf = pd.read_csv(hist_file)
            st.success(f"Replay loaded for {selected_day}: {len(hdf)} records.")
            st.dataframe(hdf, use_container_width=True, hide_index=True, height=420)
        else:
            st.warning(
                f"Historical source data unavailable for {selected_day}. "
                "Historical replay cannot be generated without the authoritative source data. "
                "Status: SOURCE DATA UNAVAILABLE."
            )
        st.caption("Replay execution remains a terminal operation: python run_intraday_replay.py YYYY-MM-DD")

with tabs[3]:
    st.subheader("Learning & Calibration")
    calib = base_path / "intraday_probability_calibration.csv" if base_path else None
    if calib and calib.exists():
        st.dataframe(pd.read_csv(calib), use_container_width=True, hide_index=True, height=350)
    else:
        st.info("Probability calibration data not found for current snapshot.")
    mem = LEARNING_ROOT / "intraday_learning_memory.csv"
    if mem.exists():
        st.dataframe(pd.read_csv(mem).tail(100), use_container_width=True, hide_index=True, height=300)
    else:
        st.info("Learning memory repository is empty.")

with tabs[4]:
    st.subheader("Governance & Data Health")
    health = health_status(base_path)
    hcols = st.columns(2)
    with hcols[0]:
        for k,v in health.items():
            st.write(f"**{k}:** {v}")
    with hcols[1]:
        reg = OUTPUT_ROOT / "report_registry.csv"
        if reg.exists():
            st.dataframe(pd.read_csv(reg).tail(10), use_container_width=True, hide_index=True, height=250)
        else:
            st.info("Report registry not found.")
    st.json({"snapshot": snapshot_date, "status": status, "base_path": str(base_path) if base_path else None})
