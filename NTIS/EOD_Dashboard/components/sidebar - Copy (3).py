import streamlit as st


MENU_ITEMS = [
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
]


def render_sidebar():
    """
    Render the NTIS Dashboard sidebar.

    Returns
    -------
    dict
        {
            "page": str,
            "auto_refresh": bool,
            "refresh_interval": str
        }
    """

    with st.sidebar:

        st.title("NTIS EOD")

        st.divider()

        page = st.radio(
            "Navigation",
            MENU_ITEMS,
            index=0,
        )

        st.divider()

        auto_refresh = st.checkbox(
            "Auto Refresh",
            value=False,
        )

        refresh_interval = st.selectbox(
            "Refresh Interval",
            [
                "30 sec",
                "1 min",
                "5 min",
                "15 min",
            ],
            index=2,
            disabled=not auto_refresh,
        )

        st.divider()

        st.caption("Dashboard Status")
        st.success("Connected")

        return {
            "page": page,
            "auto_refresh": auto_refresh,
            "refresh_interval": refresh_interval,
        }