"""
NTIS-Intraday Dashboard
Professional Operational Cockpit UI.
"""

from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from dashboard.dashboard_loader import load_dashboard_data
from dashboard.dashboard_sidebar import build_sidebar_filters
from config_loader import OUTPUT_ROOT, LEARNING_ROOT
from intraday_dashboard_health_panel import health_status

st.set_page_config(
    page_title="NTIS Intraday Operational Cockpit",
    page_icon="📈",
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

# Top Header / Navigation
st.title("🛡️ NTIS Intraday Operational Cockpit")
st.caption(f"Active Session Date: {snapshot_date} | Pipeline Status: {status.get('status', 'UNKNOWN')}")

# Navigation Tabs matching required categories
tabs = st.tabs([
    "📊 Executive & Opportunities",
    "🔄 Replay & Backtest",
    "🧠 Historical Intelligence",
    "📈 Learning & Calibration",
    "⚙️ Governance & Data Health"
])

# ----------------------------------------------------------------------
# TAB 1: EXECUTIVE & OPPORTUNITIES
# ----------------------------------------------------------------------
with tabs[0]:
    filtered_trade_df = build_sidebar_filters(trade_df)

    buy_count = sell_count = watch_count = 0
    if not trade_df.empty and "Validation Signal" in trade_df.columns:
        buy_count = int(trade_df["Validation Signal"].eq("VALID BUY").sum())
        sell_count = int(trade_df["Validation Signal"].eq("VALID SELL").sum())
        watch_count = int(trade_df["Validation Signal"].eq("WATCH").sum())

    # Professional KPI Cards
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{len(trade_df)}</div><div class="metric-label">Total Signals</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #4ade80;">{buy_count}</div><div class="metric-label">Valid Buy</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #f87171;">{sell_count}</div><div class="metric-label">Valid Sell</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #fbbf24;">{watch_count}</div><div class="metric-label">Watch</div></div>', unsafe_allow_html=True)
    with k5:
        avg_prob = round(trade_df["Intraday Probability %"].mean(), 1) if not trade_df.empty and "Intraday Probability %" in trade_df.columns else 0.0
        st.markdown(f'<div class="metric-card"><div class="metric-value">{avg_prob}%</div><div class="metric-label">Avg Probability</div></div>', unsafe_allow_html=True)

    st.markdown("### 📋 Trade Opportunities Table")
    display_cols = [
        c for c in [
            "Symbol",
            "Pattern",
            "Intraday Probability %",
            "Confidence",
            "Validation Signal",
            "Entry Price",
            "Stop Loss",
            "Target",
        ] if c in filtered_trade_df.columns
    ]

    st.dataframe(
        filtered_trade_df[display_cols],
        use_container_width=True,
        height=400,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 📊 Probability Ranking")
        if not prob_df.empty and "Symbol" in prob_df.columns and "Intraday Probability %" in prob_df.columns:
            st.bar_chart(prob_df.set_index("Symbol")["Intraday Probability %"].head(10))
        else:
            st.info("No probability analysis data available.")

    with col_b:
        st.markdown("### ⚡ Signal Evolution")
        if not evolution_df.empty:
            st.dataframe(evolution_df.head(10), use_container_width=True, height=250)
        else:
            st.info("No signal evolution data available.")

# ----------------------------------------------------------------------
# TAB 2: REPLAY & BACKTEST
# ----------------------------------------------------------------------
with tabs[1]:
    st.subheader("🔄 Historical Replay & Backtest Results")
    backtest_file = base_path / "intraday_backtest_results.csv" if base_path else None
    if backtest_file and backtest_file.exists():
        bt_df = pd.read_csv(backtest_file)
        st.success(f"Loaded Backtest Results from {backtest_file.name}")
        
        bt_cols = [c for c in ["Symbol", "Pattern", "Outcome", "Return %", "Exit Price", "Outcome Reason"] if c in bt_df.columns]
        st.dataframe(bt_df[bt_cols], use_container_width=True, height=400)
    else:
        st.info("No backtest results found for the selected snapshot date. Run replay engine to generate outcomes.")

# ----------------------------------------------------------------------
# TAB 3: HISTORICAL INTELLIGENCE
# ----------------------------------------------------------------------
with tabs[2]:
    st.subheader("🧠 Historical Intelligence & Pattern Statistics")
    stat_file = LEARNING_ROOT.parent / "Intelligence" / "pattern_statistics.csv"
    if stat_file.exists():
        stat_df = pd.read_csv(stat_file)
        st.success("Loaded Pattern Statistics Repository")
        st.dataframe(stat_df, use_container_width=True, height=450)
    else:
        st.info("Pattern statistics repository not found. Run pattern statistics engine.")

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

