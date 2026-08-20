"""
NTIS-Intraday Dashboard
Professional Operational Cockpit & Intelligence Workbench UI.
"""

from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from dashboard.dashboard_loader import load_dashboard_data
from dashboard.dashboard_sidebar import build_sidebar_filters
from config_loader import OUTPUT_ROOT, LEARNING_ROOT, SCREENSHOT_ROOT
from intraday_dashboard_health_panel import health_status
from intraday_intelligence_loader import IntradayIntelligenceLoader
from intraday_intelligence_query import IntradayIntelligenceQuery

st.set_page_config(
    page_title="NTIS Intraday Intelligence Workbench",
    page_icon="🧠",
    layout="wide",
)

# Custom CSS for Professional Cockpit Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        padding: 16px;
        border-radius: 8px;
        color: #f8fafc;
        text-align: center;
    }
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 13px;
        color: #94a3b8;
        text-transform: uppercase;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

ctx = load_dashboard_data()
status = ctx["status"]
snapshot_date = ctx["snapshot_date"]
base_path = ctx["base_path"]

trade_df = ctx["trade_df"]
prob_df = ctx["prob_df"]
evolution_df = ctx["evolution_df"]

# Load repository intelligence via loader & query layer
intel_loader = IntradayIntelligenceLoader()
intel_loader.load()
intel_query = IntradayIntelligenceQuery(intel_loader)

# Top Header / Navigation
st.title("🛡️ NTIS Intraday Intelligence Workbench")
st.caption(f"Active Session Date: {snapshot_date} | Pipeline Status: {status.get('status', 'UNKNOWN')} | Intelligence Store: Repository Connected")

# Navigation Tabs matching required categories
tabs = st.tabs([
    "📊 Executive & Opportunities",
    "🧠 Pattern Intelligence Workbench",
    "🔄 Replay & Backtest",
    "📈 Learning & Calibration",
    "⚙️ Governance & Data Health"
])

# ----------------------------------------------------------------------
# TAB 1: EXECUTIVE & OPPORTUNITIES
# ----------------------------------------------------------------------
with tabs[0]:
    filtered_trade_df = build_sidebar_filters(trade_df)

    intel_df = intel_loader.get_dataframe()
    if not filtered_trade_df.empty:
        if "Sector" not in filtered_trade_df.columns:
            filtered_trade_df["Sector"] = filtered_trade_df.get("Sector", "GENERAL")
        if "Decision Score" not in filtered_trade_df.columns:
            filtered_trade_df["Decision Score"] = filtered_trade_df.get("NTIS Intraday Score", filtered_trade_df.get("Intraday Probability %", 50.0))
        if "Historical Win %" not in filtered_trade_df.columns:
            filtered_trade_df["Historical Win %"] = 50.0
        if "Occurrences" not in filtered_trade_df.columns:
            filtered_trade_df["Occurrences"] = 0
        if "Evidence Level" not in filtered_trade_df.columns:
            filtered_trade_df["Evidence Level"] = "🔴 New"
        if "Historical Confidence" not in filtered_trade_df.columns:
            filtered_trade_df["Historical Confidence"] = 50.0

        if not intel_df.empty:
            for idx, row in filtered_trade_df.iterrows():
                sym = str(row.get("Symbol", "")).strip().upper()
                match = intel_df[(intel_df["Symbol"].str.upper() == sym)]
                if not match.empty:
                    m_row = match.iloc[0]
                    filtered_trade_df.loc[idx, "Historical Win %"] = float(m_row.get("Success_%", m_row.get("WinRate", 50.0)))
                    filtered_trade_df.loc[idx, "Occurrences"] = int(float(m_row.get("Occurrences", 0)))
                    filtered_trade_df.loc[idx, "Historical Confidence"] = float(m_row.get("Confidence_Score", m_row.get("Historical_Confidence", 50.0)))
                    evd = str(m_row.get("Evidence_Level", "NEW")).upper()
                    if evd == "MATURE":
                        filtered_trade_df.loc[idx, "Evidence Level"] = "🟢 Mature"
                    elif evd == "ESTABLISHED":
                        filtered_trade_df.loc[idx, "Evidence Level"] = "🟢 Established"
                    elif evd == "DEVELOPING":
                        filtered_trade_df.loc[idx, "Evidence Level"] = "🟡 Developing"
                    else:
                        filtered_trade_df.loc[idx, "Evidence Level"] = "🔴 New"

    buy_count = sell_count = watch_count = 0
    if not filtered_trade_df.empty and "Validation Signal" in filtered_trade_df.columns:
        buy_count = int(filtered_trade_df["Validation Signal"].isin(["BUY", "VALID BUY"]).sum())
        sell_count = int(filtered_trade_df["Validation Signal"].isin(["SELL", "VALID SELL"]).sum())
        watch_count = int(filtered_trade_df["Validation Signal"].eq("WATCH").sum())

    avg_win = round(filtered_trade_df["Historical Win %"].mean(), 1) if not filtered_trade_df.empty else 0.0
    avg_conf = round(filtered_trade_df["Historical Confidence"].mean(), 1) if not filtered_trade_df.empty else 0.0
    avg_score = round(filtered_trade_df["Decision Score"].mean(), 1) if not filtered_trade_df.empty else 0.0
    top_sector = filtered_trade_df["Sector"].mode()[0] if not filtered_trade_df.empty and "Sector" in filtered_trade_df.columns else "GENERAL"

    # Top Summary Cards (Trader-Oriented Metrics)
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    sc1.markdown(f'<div class="metric-card"><div class="metric-value">{len(filtered_trade_df)}</div><div class="metric-label">Total Signals</div></div>', unsafe_allow_html=True)
    sc2.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #4ade80;">{buy_count}</div><div class="metric-label">BUY Signals</div></div>', unsafe_allow_html=True)
    sc3.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #f87171;">{sell_count}</div><div class="metric-label">SELL Signals</div></div>', unsafe_allow_html=True)
    sc4.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #fbbf24;">{watch_count}</div><div class="metric-label">WATCH</div></div>', unsafe_allow_html=True)
    sc5.markdown(f'<div class="metric-card"><div class="metric-value">{avg_win}%</div><div class="metric-label">Avg Historical Win %</div></div>', unsafe_allow_html=True)

    sc6, sc7, sc8, sc9 = st.columns(4)
    sc6.metric("Avg Historical Confidence", f"{avg_conf}%")
    sc7.metric("Avg Decision Score", avg_score)
    sc8.metric("Top Sector", top_sector)
    sc9.metric("Active Status", "Ready")

    # Quick Filters Bar
    st.markdown("### 🎛️ Quick Decision Filters")
    qf1, qf2, qf3, qf4 = st.columns(4)
    with qf1:
        signal_filter = st.selectbox("Signal Action", ["ALL", "BUY", "SELL", "WATCH"])
    with qf2:
        evidence_filter = st.selectbox("Evidence Tier", ["ALL", "🟢 Mature", "🟢 Established", "🟡 Developing", "🔴 New"])
    with qf3:
        sector_filter = st.selectbox("Sector", ["ALL"] + sorted([str(x) for x in filtered_trade_df["Sector"].unique() if pd.notna(x)]))
    with qf4:
        symbol_search = st.text_input("Search Symbol", "").strip().upper()

    exec_df = filtered_trade_df.copy()
    if signal_filter != "ALL":
        if signal_filter == "BUY":
            exec_df = exec_df[exec_df["Validation Signal"].astype(str).isin(["BUY", "VALID BUY"])]
        elif signal_filter == "SELL":
            exec_df = exec_df[exec_df["Validation Signal"].astype(str).isin(["SELL", "VALID SELL"])]
        else:
            exec_df = exec_df[exec_df["Validation Signal"].astype(str) == signal_filter]
    if evidence_filter != "ALL":
        exec_df = exec_df[exec_df["Evidence Level"].astype(str) == evidence_filter]
    if sector_filter != "ALL":
        exec_df = exec_df[exec_df["Sector"].astype(str) == sector_filter]
    if symbol_search:
        exec_df = exec_df[exec_df["Symbol"].astype(str).str.contains(symbol_search, case=False, na=False)]

    st.markdown("### 📋 Executive Trade Opportunities Table")
    executive_cols = [
        c for c in [
            "Symbol",
            "Sector",
            "Validation Signal",
            "Decision Score",
            "Intraday Probability %",
            "Historical Win %",
            "Occurrences",
            "Evidence Level",
            "Historical Confidence",
            "Pattern",
            "NTIS Intraday Score",
            "Entry Price",
            "Stop Loss",
            "Target",
        ] if c in exec_df.columns
    ]

    st.dataframe(
        exec_df[executive_cols],
        use_container_width=True,
        height=420,
    )

    st.markdown("---")
    st.markdown("### 🎯 Executive Stock Decision Synthesizer & Explanation Workbench")
    st.caption("Select a candidate stock from the filtered opportunities above to inspect the synthesized decision intelligence, historical evidence, pattern reliability, and decision explanation.")

    if not exec_df.empty and "Symbol" in exec_df.columns:
        cand_symbols = sorted(exec_df["Symbol"].dropna().unique().tolist())
        selected_exec_sym = st.selectbox("Select Candidate Stock for Executive Decision Deep-Dive", cand_symbols, key="exec_decision_sym_select")
        
        row_match = exec_df[exec_df["Symbol"].astype(str).str.upper() == selected_exec_sym.upper()]
        if not row_match.empty:
            r_data = row_match.iloc[0]
            
            s_sym = str(r_data.get("Symbol", selected_exec_sym))
            s_sector = str(r_data.get("Sector", "GENERAL"))
            s_signal = str(r_data.get("Validation Signal", "WATCH"))
            s_score = r_data.get("Decision Score", r_data.get("NTIS Intraday Score", 50.0))
            s_prob = r_data.get("Intraday Probability %", 50.0)
            s_win = r_data.get("Historical Win %", 50.0)
            s_occ = r_data.get("Occurrences", 0)
            s_conf = r_data.get("Historical Confidence", 50.0)
            s_evd = r_data.get("Evidence Level", "🔴 New")
            s_pattern = str(r_data.get("Pattern", "N/A"))
            s_entry = r_data.get("Entry Price", "N/A")
            s_sl = r_data.get("Stop Loss", "N/A")
            s_target = r_data.get("Target", "N/A")
            s_sup = r_data.get("Support", r_data.get("Support Level", "N/A"))
            s_res = r_data.get("Resistance", r_data.get("Resistance Level", "N/A"))
            s_rr = r_data.get("Risk / Reward", r_data.get("Risk/Reward", "N/A"))

            ed1, ed2, ed3, ed4 = st.columns(4)
            ed1.metric("Stock Symbol", s_sym, f"Sector: {s_sector}")
            ed2.metric("Validation Signal", s_signal)
            ed3.metric("Decision Score / Prob", f"{s_score} (Prob: {s_prob}%)")
            ed4.metric("Historical Win %", f"{s_win}%", f"Occurrences: {s_occ}")

            ed5, ed6, ed7, ed8 = st.columns(4)
            ed5.metric("Historical Confidence", f"{s_conf}%")
            ed6.metric("Evidence Level", s_evd)
            ed7.metric("Pattern Reference", s_pattern)
            ed8.metric("Risk / Reward", str(s_rr))

            tp1, tp2, tp3 = st.columns(3)
            tp1.metric("Entry Price", str(s_entry))
            tp2.metric("Stop Loss", str(s_sl))
            tp3.metric("Target", str(s_target))

            st.markdown("#### 🧠 NTIS Decision Explanation & Synthesis ('Why?', True 'Why Now?' & Historical Average PnL)")
            
            stock_hist_rec = intel_query.by_symbol(s_sym)
            avg_pnl_val = "N/A"
            total_matches = 0
            win_rate_sum = 0.0
            first_seen_min = "N/A"
            last_seen_max = "N/A"

            if not stock_hist_rec.empty:
                total_matches = len(stock_hist_rec)
                if "Average_PnL" in stock_hist_rec.columns:
                    pnl_vals = pd.to_numeric(stock_hist_rec["Average_PnL"], errors="coerce").dropna()
                    if not pnl_vals.empty:
                        avg_pnl_val = round(pnl_vals.mean(), 2)
                if "Success_%" in stock_hist_rec.columns:
                    succ_vals = pd.to_numeric(stock_hist_rec["Success_%"], errors="coerce").dropna()
                    if not succ_vals.empty:
                        win_rate_sum = round(succ_vals.mean(), 1)
                if "First_Seen" in stock_hist_rec.columns:
                    fs = stock_hist_rec["First_Seen"].dropna()
                    if not fs.empty:
                        first_seen_min = str(fs.min())
                if "Last_Seen" in stock_hist_rec.columns:
                    ls = stock_hist_rec["Last_Seen"].dropna()
                    if not ls.empty:
                        last_seen_max = str(ls.max())

            has_complete_plan = (
                str(s_entry).upper() not in {"N/A", "NONE", "NAN", ""} and
                str(s_sl).upper() not in {"N/A", "NONE", "NAN", ""} and
                str(s_target).upper() not in {"N/A", "NONE", "NAN", ""}
            )
            trade_status_badge = "🟢 Trade-Ready (Complete Plan)" if has_complete_plan else "🟡 Trade Plan Incomplete (Advisory Only)"

            if not stock_hist_rec.empty and int(s_occ) > 1:
                evd_upper = str(s_evd).upper()
                if "NEW" in evd_upper:
                    why_now_text = f"Current session validation signal (**{s_signal}**) and probability (**{s_prob}%**) occur with New / Insufficient historical evidence (Occurrences: **{s_occ}**). Historical observation spans from **{first_seen_min}** to **{last_seen_max}**; recurrence confirmation is preliminary and ongoing."
                elif "DEVELOPING" in evd_upper:
                    why_now_text = f"Current session validation signal (**{s_signal}**) and probability (**{s_prob}%**) align with developing historical intelligence records for **{s_sym}** (Occurrences: **{s_occ}**, Success Rate: **{s_win}%**). Observation window: **{first_seen_min}** to **{last_seen_max}**."
                else:
                    why_now_text = f"Current session validation signal (**{s_signal}**) and probability (**{s_prob}%**) align with established/mature historical intelligence records for **{s_sym}** (Evidence Tier: **{s_evd}**, Total Occurrences: **{s_occ}**, Historical Success Rate: **{s_win}%**). Historical observation window spans from **{first_seen_min}** to **{last_seen_max}**, validating recurring behavioural confirmation under current market conditions."
            else:
                why_now_text = f"Current session validation signal (**{s_signal}**) is classified under New / Insufficient evidence (Occurrences: **{s_occ}**). Historical confirmation is preliminary; timing alignment cannot be established from mature recurring evidence."

            explanation_md = f"""
> **Executive Recommendation for {s_sym}**: **{s_signal}** | **{trade_status_badge}**
> 
> - **Current Behaviour & Signal**: Today's action in **{s_sym}** yields a validation signal of **{s_signal}** with a Decision Score of **{s_score}** and Intraday Probability of **{s_prob}%**.
> - **Why? (Historical Evidence)**: Historically, this stock under comparable intelligence has demonstrated a win rate of **{s_win}%** across **{s_occ}** recorded occurrences with historical confidence of **{s_conf}%** (Evidence Level: **{s_evd}**). Associated behavioural pattern is **{s_pattern}**.
> - **Why Now? (Timing Alignment)**: {why_now_text}
> - **Market Context & Trade Plan**: Operating within sector **{s_sector}** (Support: **{s_sup}**, Resistance: **{s_res}**, Risk/Reward: **{s_rr}**). Proposed Trade Plan: Entry at **{s_entry}**, Stop Loss at **{s_sl}**, Target at **{s_target}** (**{trade_status_badge}**).
> - **Historical Average PnL**: Authoritative Average PnL from historical intelligence repository: **{avg_pnl_val if avg_pnl_val != 'N/A' else 'Historical Average PnL not available from current producer outputs'}**.
            """
            st.markdown(explanation_md)

            with st.expander(f"📂 Historical Event Footprint & Evidence Depth for {s_sym}"):
                if not stock_hist_rec.empty:
                    st.success(f"Loaded {total_matches} authoritative historical event footprint records for {s_sym}.")
                    
                    fn1, fn2, fn3, fn4 = st.columns(4)
                    fn1.metric("Event Matches", total_matches)
                    fn2.metric("Avg Success Rate", f"{win_rate_sum}%")
                    fn3.metric("Historical Avg PnL", avg_pnl_val)
                    fn4.metric("Observation Range", f"{first_seen_min} → {last_seen_max}")

                    footprint_cols = [c for c in [
                        "Business_Pattern_ID", "Pattern_Name", "Lifecycle_State",
                        "Occurrences", "Successful_Trades", "Failed_Trades", "Success_%", 
                        "Average_PnL", "Confidence_Score", "Evidence_Level", "First_Seen", "Last_Seen"
                    ] if c in stock_hist_rec.columns]
                    st.dataframe(stock_hist_rec[footprint_cols], use_container_width=True, height=240)
                else:
                    st.info(f"No authoritative historical event footprint records found in repository for {s_sym}.")
        else:
            st.info("Selected stock record not found in filtered opportunities.")
    else:
        st.info("No executive trade opportunities available for decision synthesis.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 📊 Sector Intelligence")
        if not exec_df.empty and "Sector" in exec_df.columns and "Intraday Probability %" in exec_df.columns:
            sector_perf = exec_df.groupby("Sector")["Intraday Probability %"].mean()
            st.bar_chart(sector_perf)
            st.info(f"Strongest Sector: **{sector_perf.idxmax() if not sector_perf.empty else 'N/A'}** | Weakest Sector: **{sector_perf.idxmin() if not sector_perf.empty else 'N/A'}**")
        else:
            st.info("No sector performance data available.")

    with col_b:
        st.markdown("### ⚡ Signal Evolution")
        if not evolution_df.empty:
            st.dataframe(evolution_df.head(10), use_container_width=True, height=250)
        else:
            st.info("No signal evolution data available.")

# ----------------------------------------------------------------------
# TAB 2: PATTERN INTELLIGENCE WORKBENCH (NEW)
# ----------------------------------------------------------------------
with tabs[1]:
    st.subheader("🧠 Repository Pattern Intelligence Workbench")
    
    intel_df = intel_loader.get_dataframe()
    if not intel_df.empty:
        col_search1, col_search2 = st.columns(2)
        with col_search1:
            search_sym = st.text_input("Filter by Symbol", "").strip().upper()
        with col_search2:
            search_pid = st.text_input("Filter by Business Pattern ID / Fingerprint", "").strip()

        view_df = intel_df.copy()
        if search_sym:
            view_df = view_df[view_df["Symbol"].str.upper() == search_sym]
        if search_pid:
            view_df = view_df[
                view_df["Business_Pattern_ID"].astype(str).str.contains(search_pid, case=False, na=False) |
                view_df["Pattern_Fingerprint"].astype(str).str.contains(search_pid, case=False, na=False)
            ]

        st.markdown("### 🔍 Pattern Explorer & Historical Timeline")
        display_intel_cols = [
            c for c in [
                "Business_Pattern_ID", "Symbol", "Pattern_Name", "Lifecycle_State",
                "Occurrences", "Success_%", "Average_PnL", "Confidence_Score",
                "Historical_Probability", "Historical_Confidence", "Evidence_Level",
                "First_Seen", "Last_Seen"
            ] if c in view_df.columns
        ]
        st.dataframe(view_df[display_intel_cols], use_container_width=True, height=400)

        if not view_df.empty:
            st.markdown("### 📊 Detailed Pattern Intelligence & Similar View")
            selected_pid = st.selectbox("Select Business Pattern ID for Deep Dive", view_df["Business_Pattern_ID"].unique())
            
            p_record = intel_query.by_pattern_id(selected_pid)
            if not p_record.empty:
                r_item = p_record.iloc[0]
                
                ic1, ic2, ic3, ic4 = st.columns(4)
                ic1.metric("Lifecycle State", str(r_item.get("Lifecycle_State", "UNKNOWN")))
                ic2.metric("Success Rate", f"{r_item.get('Success_%', 0)}%")
                ic3.metric("Total Occurrences", str(r_item.get("Occurrences", 0)))
                ic4.metric("Average PnL", str(r_item.get("Average_PnL", 0)))

                ic5, ic6, ic7 = st.columns(3)
                ic5.metric("Historical Probability", f"{r_item.get('Historical_Probability', 50.0)}%")
                ic6.metric("Historical Confidence", f"{r_item.get('Historical_Confidence', 50.0)}%")
                ic7.metric("Evidence Level", str(r_item.get("Evidence_Level", "NEW")))

                with st.expander("🧬 View Pattern DNA & Fingerprint"):
                    st.write(f"**Business Pattern ID:** {r_item.get('Business_Pattern_ID')}")
                    st.write(f"**Pattern Fingerprint:** {r_item.get('Pattern_Fingerprint')}")
                    st.write(f"**Pattern Name:** {r_item.get('Pattern_Name')}")
                    st.write(f"**Symbol:** {r_item.get('Symbol')}")
                    st.write(f"**Evidence Level:** {r_item.get('Evidence_Level', 'NEW')}")
                    st.write(f"**Confidence Score:** {r_item.get('Confidence_Score', 0)}")
                    st.write(f"**First Seen / Last Seen:** {r_item.get('First_Seen')} -> {r_item.get('Last_Seen')}")

                st.markdown("#### Similar Pattern Matches (Same Fingerprint / ID)")
                sim_matches = view_df[view_df["Pattern_Fingerprint"] == r_item.get("Pattern_Fingerprint")]
                st.dataframe(sim_matches, use_container_width=True, height=200)

        st.markdown("---")
        st.markdown("### 📈 Stock Intelligence History & Evidence Workbench")
        st.caption("Query stock-specific historical intelligence, signals, outcomes, probabilities, confidence, and business pattern references.")
        
        all_symbols = sorted(list(set(intel_df["Symbol"].dropna().unique().tolist() + trade_df["Symbol"].dropna().unique().tolist())))
        if all_symbols:
            selected_stock_hist = st.selectbox("Select Stock Symbol for Intelligence History", all_symbols, key="stock_hist_select")
            stock_intel_records = intel_query.by_symbol(selected_stock_hist)
            
            if not stock_intel_records.empty:
                st.success(f"Loaded Stock Intelligence History for **{selected_stock_hist}** ({len(stock_intel_records)} records found)")
                
                st1, st2, st3, st4 = st.columns(4)
                st1.metric("Selected Symbol", selected_stock_hist)
                st1.metric("Historical Patterns", len(stock_intel_records))
                
                total_occ = pd.to_numeric(stock_intel_records.get("Occurrences", 0), errors="coerce").sum()
                avg_win_rate = round(pd.to_numeric(stock_intel_records.get("Success_%", stock_intel_records.get("WinRate", 50.0)), errors="coerce").mean(), 1)
                avg_conf_score = round(pd.to_numeric(stock_intel_records.get("Confidence_Score", stock_intel_records.get("Historical_Confidence", 50.0)), errors="coerce").mean(), 1)
                
                st2.metric("Total Occurrences", int(total_occ))
                st3.metric("Avg Historical Win Rate", f"{avg_win_rate}%")
                st4.metric("Avg Historical Confidence", f"{avg_conf_score}%")
                
                st.markdown("#### 🔍 Stock-Specific Historical Signals & Evidence Table")
                stock_cols = [c for c in [
                    "Business_Pattern_ID", "Symbol", "Pattern_Name", "Lifecycle_State",
                    "Occurrences", "Success_%", "Average_PnL", "Confidence_Score",
                    "Historical_Probability", "Historical_Confidence", "Evidence_Level",
                    "First_Seen", "Last_Seen"
                ] if c in stock_intel_records.columns]
                st.dataframe(stock_intel_records[stock_cols], use_container_width=True, height=280)
                
                st.markdown("#### ⏱️ Stock Historical Timeline & Business Pattern Reference")
                timeline_cols = [c for c in [
                    "Business_Pattern_ID", "Symbol", "Pattern_Name", "First_Seen", "Last_Seen",
                    "Success_%", "Average_PnL", "Evidence_Level", "Lifecycle_State"
                ] if c in stock_intel_records.columns]
                st.dataframe(stock_intel_records[timeline_cols], use_container_width=True, height=220)
            else:
                st.info(f"No stock intelligence records found for symbol **{selected_stock_hist}** in repository.")
        else:
            st.info("No stock symbols available for intelligence query.")
    else:
        st.info("No pattern intelligence records available in the repository.")

# ----------------------------------------------------------------------
# TAB 3: HISTORICAL REPLAY BROWSER & BACKTEST WORKBENCH
# ----------------------------------------------------------------------
with tabs[2]:
    st.subheader("🗓️ Historical Trading Intelligence & Replay Browser")
    
    from intraday_latest_snapshot_resolver import IntradayLatestSnapshotResolver
    from dashboard.dashboard_loader import build_snapshot_path, safe_read
    
    resolver = IntradayLatestSnapshotResolver(SCREENSHOT_ROOT, OUTPUT_ROOT)
    all_snapshots = resolver.get_available_snapshots()
    
    if not all_snapshots:
        st.info("No historical replay snapshots available in the output repository.")
    else:
        col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
        
        if "replay_selected_idx" not in st.session_state:
            st.session_state.replay_selected_idx = len(all_snapshots) - 1
            
        with col_nav1:
            if st.button("⬅️ Previous Trading Day") and st.session_state.replay_selected_idx > 0:
                st.session_state.replay_selected_idx -= 1
        with col_nav2:
            selected_day = st.selectbox(
                "Select Historical Trading Date (Trading Calendar)",
                all_snapshots,
                index=st.session_state.replay_selected_idx
            )
            if selected_day in all_snapshots:
                st.session_state.replay_selected_idx = all_snapshots.index(selected_day)
        with col_nav3:
            if st.button("Next Trading Day ➡️") and st.session_state.replay_selected_idx < len(all_snapshots) - 1:
                st.session_state.replay_selected_idx += 1

        st.caption(f"📁 Active Historical Snapshot Date: **{selected_day}** (Read-Only Context)")
        
        hist_base = build_snapshot_path(selected_day)
        hist_backtest = hist_base / "intraday_backtest_results.csv" if hist_base else None
        
        if hist_backtest and hist_backtest.exists():
            h_df = pd.read_csv(hist_backtest)
            st.success(f"Loaded Historical Snapshot & Replay Intelligence for {selected_day} ({len(h_df)} records)")
            
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Trading Date", selected_day)
            t2.metric("Historical Signals", len(h_df))
            wins_h = len(h_df[h_df["Outcome"].astype(str).isin(["TARGET HIT", "SUCCESS", "WIN"])]) if "Outcome" in h_df.columns else 0
            win_r_h = round((wins_h / len(h_df)) * 100, 1) if len(h_df) > 0 else 0.0
            t3.metric("Replay Win Rate", f"{win_r_h}%")
            pnl_col_h = "PnL" if "PnL" in h_df.columns else ("Return %" if "Return %" in h_df.columns else None)
            avg_pnl_h = round(h_df[pnl_col_h].astype(float).mean(), 2) if pnl_col_h and len(h_df) > 0 else 0.0
            t4.metric("Avg PnL", avg_pnl_h)

            st.markdown("### 🔍 Historical Snapshot Viewer & Decision Table")
            viewer_cols = [c for c in [
                "Symbol", "Pattern", "Direction", "Validation Signal", "Intraday Probability %",
                "Historical_Probability", "Historical_Confidence", "Evidence_Level",
                "Entry_Price", "Exit_Price", "Outcome", "PnL", "Return %", "Holding_Minutes"
            ] if c in h_df.columns]
            st.dataframe(h_df[viewer_cols], use_container_width=True, height=380)

            st.markdown("### ⏱️ Historical Timeline & Audit Log")
            if "Replay_Run_Date" in h_df.columns:
                st.dataframe(h_df[["Symbol", "Replay_Run_Date", "Replay_Run_Time", "Replay_Status", "Outcome"]].drop_duplicates(), use_container_width=True, height=200)
            else:
                st.info(f"Historical timeline metadata recorded for snapshot session {selected_day}.")
        else:
            st.warning(f"Historical source data unavailable for {selected_day}. Historical replay cannot be generated without the authoritative source data. Status: SOURCE DATA UNAVAILABLE.")
    
    st.markdown("---")
    st.markdown("### 🔄 Global Replay Execution Runner")
    run_date_input = st.text_input("Run Replay for Date (YYYY-MM-DD)", value=datetime.today().strftime("%Y-%m-%d"))
    if st.button("Execute Historical Replay"):
        st.info(f"To execute replay for {run_date_input}, run: `python run_intraday_replay.py {run_date_input}` from terminal.")

# ----------------------------------------------------------------------
# TAB 4: LEARNING & CALIBRATION
# ----------------------------------------------------------------------
with tabs[3]:
    st.subheader("📈 Closed Learning Loop & Probability Calibration")
    calib_file = base_path / "intraday_probability_calibration.csv" if base_path else None
    if calib_file and calib_file.exists():
        calib_df = pd.read_csv(calib_file)
        st.success("Loaded Probability Calibration Feedback")
        st.dataframe(calib_df, use_container_width=True, height=350)
    else:
        st.info("Probability calibration data not found for current snapshot.")

    st.markdown("### 📝 Learning Memory Repository")
    mem_file = LEARNING_ROOT / "intraday_learning_memory.csv"
    if mem_file.exists():
        mem_df = pd.read_csv(mem_file)
        st.dataframe(mem_df.tail(100), use_container_width=True, height=300)
    else:
        st.info("Learning memory repository is empty.")

# ----------------------------------------------------------------------
# TAB 5: GOVERNANCE & DATA HEALTH
# ----------------------------------------------------------------------
with tabs[4]:
    st.subheader("⚙️ Governance, Data Health & Pipeline Status")
    health = health_status(base_path)
    
    hc1, hc2 = st.columns(2)
    with hc1:
        st.markdown("### 🏥 System Health Check")
        for k, v in health.items():
            color = "#4ade80" if v in {"PASS", "LIVE", "FALLBACK"} else "#f87171"
            st.markdown(f"- **{k}**: <span style='color:{color}; font-weight:bold;'>{v}</span>", unsafe_allow_html=True)

    with hc2:
        st.markdown("### 📁 Registry & Storage")
        reg_file = OUTPUT_ROOT / "report_registry.csv"
        if reg_file.exists():
            reg_df = pd.read_csv(reg_file)
            st.dataframe(reg_df.tail(10), use_container_width=True, height=250)
        else:
            st.info("Report registry not found.")

    st.markdown("---")
    st.markdown("### 🔍 Advanced Snapshot & Comparison Viewer")
    from intraday_dashboard_snapshot_viewer import snapshot_summary
    from intraday_dashboard_compare_engine import compare_snapshots
    
    if not trade_df.empty:
        summary_dict = snapshot_summary(trade_df)
        st.json(summary_dict)
    else:
        st.info("No active snapshot data for summary viewer.")


