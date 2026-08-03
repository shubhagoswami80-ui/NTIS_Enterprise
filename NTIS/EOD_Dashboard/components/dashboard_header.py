"""
NTIS EOD Dashboard Header Component
"""

from datetime import datetime

import streamlit as st


def render_header(
    title: str = "NTIS Enterprise Dashboard",
    subtitle: str = "End of Day Intelligence Platform",
) -> None:
    """
    Render the application header.

    Presentation only.
    No business logic should be added here.
    """

    refresh_time = datetime.now().strftime("%H:%M:%S")

    st.title(title)
    st.caption(subtitle)

    col_mode, col_env, col_refresh = st.columns(3)

    with col_mode:
        st.metric(
            label="Mode",
            value="EOD",
        )

    with col_env:
        st.metric(
            label="Environment",
            value="Production",
        )

    with col_refresh:
        st.metric(
            label="Last Refresh",
            value=refresh_time,
        )

    st.divider()