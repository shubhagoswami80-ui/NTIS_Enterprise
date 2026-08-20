
from pathlib import Path

TARGET = Path(r"E:\NSE_Daily_Analysis\NTIS\Intraday\intraday_dashboard.py")
if not TARGET.exists():
    raise SystemExit(f"Target not found: {TARGET}")

text = TARGET.read_text(encoding="utf-8")
original = text

text = text.replace(
    "from datetime import datetime\nfrom pathlib import Path\nimport streamlit as st",
    "from datetime import datetime\nfrom pathlib import Path\nimport subprocess\nimport time\nimport streamlit as st",
    1,
)

# Replace the old metric CSS only if it is present.
old_css = "<style>\n    .metric-card {"
css_start = text.find(old_css)
css_end = text.find("</style>", css_start)
if css_start >= 0 and css_end >= 0:
    css_end += len("</style>")
    new_css = (
        "<style>\n"
        ".ntis-hero{background:linear-gradient(135deg,#101f4d,#1b2f6b,#3b2b77);"
        "padding:22px 26px;border-radius:16px;color:white;margin-bottom:14px;"
        "box-shadow:0 8px 24px rgba(15,23,42,.16)}\n"
        ".ntis-hero h1{margin:0;font-size:30px}.ntis-hero p{margin:6px 0;color:#dbe5ff}\n"
        ".status-pill{display:inline-block;padding:5px 10px;border-radius:999px;font-size:12px;"
        "font-weight:700;margin-right:6px;background:#e0e7ff;color:#3730a3}\n"
        ".metric-card{background:white;border:1px solid #e5e7eb;padding:15px;border-radius:14px;"
        "min-height:88px;box-shadow:0 3px 12px rgba(15,23,42,.06)}\n"
        ".metric-value{font-size:25px;font-weight:800}.metric-label{font-size:12px;color:#64748b;"
        "text-transform:uppercase}\n"
        ".decision-card{border:1px solid #e5e7eb;border-radius:16px;padding:18px;background:#fff;"
        "box-shadow:0 4px 16px rgba(15,23,42,.07)}\n"
        ".decision-title{font-size:21px;font-weight:800}.decision-sub{color:#64748b;font-size:13px}\n"
        ".verdict{border-left:5px solid #7c3aed;background:#faf7ff;padding:14px 16px;"
        "border-radius:10px;margin:10px 0}.small-note{color:#64748b;font-size:12px}\n"
        "</style>"
    )
    text = text[:css_start] + new_css + text[css_end:]

# Insert helpers once.
anchor = "ctx = load_dashboard_data()"
if "_exact_pattern_history" not in text and anchor in text:
    helpers = r'''
def _ntis_text(value, default="N/A"):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    value = str(value).strip()
    return default if value.lower() in {"", "nan", "none"} else value


def _run_next_snapshot():
    subprocess.Popen(
        ["python", "run_intraday_pipeline.py"],
        cwd=str(Path(__file__).resolve().parent),
    )


def _exact_pattern_history(intel_df, symbol, pattern):
    if intel_df is None or intel_df.empty or "Symbol" not in intel_df.columns:
        return pd.DataFrame()
    stock = intel_df[
        intel_df["Symbol"].astype(str).str.upper().eq(str(symbol).upper())
    ]
    if not pattern:
        return pd.DataFrame()
    for col in ("Pattern_Name", "Pattern"):
        if col in stock.columns:
            exact = stock[
                stock[col].astype(str).str.strip().str.lower().eq(
                    str(pattern).strip().lower()
                )
            ]
            if not exact.empty:
                return exact
    return pd.DataFrame()


def _predictive_label(exact_history):
    if exact_history is None or exact_history.empty:
        return "OBSERVATION ONLY", "No exact historical pattern evidence", "🟠"
    wins = pd.to_numeric(
        exact_history.get("Successful_Trades", 0), errors="coerce"
    ).fillna(0).sum()
    losses = pd.to_numeric(
        exact_history.get("Failed_Trades", 0), errors="coerce"
    ).fillna(0).sum()
    completed = wins + losses
    levels = exact_history.get(
        "Evidence_Level",
        exact_history.get("Lifecycle_State", pd.Series(["NEW"])),
    ).astype(str).str.upper()
    level = levels.iloc[0] if not levels.empty else "NEW"
    if completed > 0 and level == "MATURE":
        return "HIGH CONFIDENCE", "Mature exact-pattern outcome evidence", "🟢"
    if completed > 0 and level == "ESTABLISHED":
        return "SUPPORTED", "Outcome-confirmed exact-pattern evidence", "🟢"
    return "EARLY EVIDENCE", "Pattern observed, but outcome confirmation is insufficient", "🟠"


'''
    text = text.replace(anchor, helpers + anchor, 1)

# Replace old title/caption with cockpit controls using ordinary quoted strings.
old_header = (
    '# Top Header / Navigation\n'
    'st.title("🛡️ NTIS Intraday Intelligence Workbench")\n'
    'st.caption(f"Active Session Date: {snapshot_date} | Pipeline Status: {status.get(\'status\', \'UNKNOWN\')} | Intelligence Store: Repository Connected")\n'
)
new_header = (
    '# Executive header and snapshot controls\n'
    'st.markdown(\n'
    '    "<div class=\\"ntis-hero\\"><h1>🧠 NTIS Intraday Predictive Decision Cockpit</h1>"\n'
    '    "<p>Current behaviour → pattern intelligence → historical evidence → trade-plan readiness</p>"\n'
    '    f"<span class=\\"status-pill\\">Snapshot: {_ntis_text(snapshot_date)}</span>"\n'
    '    f"<span class=\\"status-pill\\">Pipeline: {_ntis_text(status.get(\'status\'), \'UNKNOWN\')}</span>"\n'
    '    "<span class=\\"status-pill\\">Intelligence: CONNECTED</span></div>",\n'
    '    unsafe_allow_html=True,\n'
    ')\n\n'
    'ctl1, ctl2, ctl3 = st.columns([1.2, 1.2, 2.2])\n'
    'with ctl1:\n'
    '    if st.button("↻ Refresh Current Snapshot", use_container_width=True):\n'
    '        st.rerun()\n'
    'with ctl2:\n'
    '    if st.button("▶ Process Next Snapshot", use_container_width=True):\n'
    '        _run_next_snapshot()\n'
    '        st.success("Existing intraday pipeline started.")\n'
    'with ctl3:\n'
    '    auto_run = st.toggle("Continue Automatically", value=False)\n'
    '    if auto_run:\n'
    '        st.caption("Re-checking the existing pipeline every 30 seconds.")\n'
    '        time.sleep(30)\n'
    '        st.rerun()\n'
)
if old_header in text:
    text = text.replace(old_header, new_header, 1)

# Add predictive fields before the opportunities table.
marker = '    st.markdown("### 📋 Executive Trade Opportunities Table")'
if marker in text and 'exec_df["Predictive Status"]' not in text:
    block = (
        '    predictive_status = []\n'
        '    exact_observations = []\n'
        '    completed_outcomes = []\n'
        '    for _, candidate in exec_df.iterrows():\n'
        '        exact = _exact_pattern_history(intel_df, candidate.get("Symbol", ""), candidate.get("Pattern", ""))\n'
        '        label, _, _ = _predictive_label(exact)\n'
        '        predictive_status.append(label)\n'
        '        exact_observations.append(int(pd.to_numeric(exact.get("Occurrences", 0), errors="coerce").fillna(0).sum()) if not exact.empty else 0)\n'
        '        wins = pd.to_numeric(exact.get("Successful_Trades", 0), errors="coerce").fillna(0).sum() if not exact.empty else 0\n'
        '        losses = pd.to_numeric(exact.get("Failed_Trades", 0), errors="coerce").fillna(0).sum() if not exact.empty else 0\n'
        '        completed_outcomes.append(int(wins + losses))\n'
        '    if not exec_df.empty:\n'
        '        exec_df["Predictive Status"] = predictive_status\n'
        '        exec_df["Exact Pattern Observations"] = exact_observations\n'
        '        exec_df["Completed Outcomes"] = completed_outcomes\n\n'
    )
    text = text.replace(marker, block + marker, 1)

# Add a predictive layer before the deep-dive.
deep = '    st.markdown("### 🎯 Executive Stock Decision Synthesizer & Explanation Workbench")'
if deep in text and '### 🔮 Predictive Opportunity Layer' not in text:
    layer = (
        '    st.markdown("---")\n'
        '    st.markdown("### 🔮 Predictive Opportunity Layer")\n'
        '    if not exec_df.empty and "Predictive Status" in exec_df.columns:\n'
        '        predictive_df = exec_df[exec_df["Predictive Status"].isin(["HIGH CONFIDENCE", "SUPPORTED"])].copy()\n'
        '        if predictive_df.empty:\n'
        '            st.info("No outcome-confirmed exact-pattern opportunities are available. NEW / EARLY signals remain observation-stage.")\n'
        '        else:\n'
        '            pcols = [c for c in ["Symbol","Validation Signal","Predictive Status","Intraday Probability %","Decision Score","Pattern","Exact Pattern Observations","Completed Outcomes","Entry Price","Stop Loss","Target"] if c in predictive_df.columns]\n'
        '            st.dataframe(predictive_df[pcols].head(15), use_container_width=True, hide_index=True, height=230)\n\n'
    )
    text = text.replace(deep, layer + deep, 1)

if text == original:
    raise SystemExit("No expected Git-baseline changes were found.")

TARGET.write_text(text, encoding="utf-8")
print(f"UPDATED: {TARGET}")
print("GitHub remained READ-ONLY.")
