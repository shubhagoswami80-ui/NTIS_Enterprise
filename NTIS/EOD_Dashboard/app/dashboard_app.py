"""
NTIS EOD Dashboard Main Application
"""

import sys
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from EOD_Dashboard.components.sidebar import render_sidebar
from EOD_Dashboard.components.status_bar import render_status_bar
from EOD_Dashboard.pages.market_overview import show_market_overview
from EOD_Dashboard.pages.historical_analysis import show_historical_analysis


def run_dashboard():

    st.set_page_config(
        page_title="NTIS EOD Intelligence Dashboard",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("NTIS EOD INTELLIGENCE DASHBOARD")

    menu = render_sidebar()

    if menu in ["Dashboard", "Market Overview"]:
        show_market_overview()

    elif menu == "Historical Replay":
        show_historical_analysis()

    else:
        st.info(f"{menu} module under development")

    render_status_bar()


if __name__ == "__main__":
    run_dashboard()
