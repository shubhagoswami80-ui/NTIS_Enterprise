"""
NTIS EOD Dashboard Sidebar Component

Presentation Layer Only
"""

from __future__ import annotations

import streamlit as st


MENU_ITEMS = (
    "Dashboard",
    "Market Overview",
    "BUY Opportunities",
    "SELL Opportunities",
    "Probability Ranking",
    "OI Intelligence",
    "Support Intelligence",
    "Resistance Intelligence",
    "Pattern Intelligence",
    "Historical Replay",
    "Settings",
)

REFRESH_INTERVALS = (
    "30 sec",
    "1 min",
    "5 min",
    "15 min",
)


def render_sidebar() -> dict:
    """
    Render dashboard sidebar.

    Returns
    -------
    dict
        {
            "page": str,
            "auto_refresh": bool,
            "refresh_interval": str
        }

    Notes
    -----
    UI only.
    No business logic should be implemented here.
    """

    with st.sidebar:

        st.title("NTIS EOD")

        st.divider()

        selected_page = st.radio(
            label="Navigation",
            options=MENU_ITEMS,
            index=0,
        )

        st.divider()

        auto_refresh = st.checkbox(
            label="Auto Refresh",
            value=False,
        )

        refresh_interval = st.selectbox(
            label="Refresh Interval",
            options=REFRESH_INTERVALS,
            index=2,
            disabled=not auto_refresh,
        )

        st.divider()

        st.caption("Dashboard Status")
        st.success("Connected")

    return {
        "page": selected_page,
        "auto_refresh": auto_refresh,
        "refresh_interval": refresh_interval,
    }