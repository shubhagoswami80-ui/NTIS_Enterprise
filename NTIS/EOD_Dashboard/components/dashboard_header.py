"""
NTIS EOD Dashboard Header Component
"""

from datetime import datetime

import streamlit as st


def render_header(
    title="NTIS Enterprise Dashboard",
    subtitle="End of Day Intelligence Platform",
):

    st.title(title)

    st.caption(subtitle)

    c1, c2, c3 = st.columns([2, 2, 2])

    c1.metric(
        "Mode",
        "EOD",
    )

    c2.metric(
        "Environment",
        "Production",
    )

    c3.metric(
        "Last Refresh",
        datetime.now().strftime("%H:%M:%S"),
    )

    st.divider()