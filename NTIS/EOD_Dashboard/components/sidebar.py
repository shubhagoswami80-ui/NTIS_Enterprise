
import streamlit as st

def render_sidebar():

    with st.sidebar:
        st.title("NTIS EOD")

        return st.radio(
            "Navigation",
            [
                "Dashboard",
                "Market Overview",
                "BUY Opportunities",
                "SELL Opportunities",
                "Probability Ranking",
                "OI Intelligence",
                "Support Resistance",
                "Pattern Intelligence",
                "Historical Replay",
                "Settings"
            ]
        )
