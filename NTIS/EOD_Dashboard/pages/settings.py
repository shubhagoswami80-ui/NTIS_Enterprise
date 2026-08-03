"""
NTIS-EOD
Settings Page

Presentation Layer Only
"""

from __future__ import annotations

import streamlit as st

from EOD_Dashboard.config.dashboard_config import (
    APP_TITLE,
    DEFAULT_PAGE,
    TABLE_PAGE_SIZE,
    CACHE_ENABLED,
)


PAGE_TITLE = "NTIS SETTINGS"


def show_settings() -> None:
    """
    Render dashboard settings page.

    Configuration display only.
    No runtime configuration changes.
    """

    st.header(PAGE_TITLE)

    st.subheader("Dashboard Configuration")

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Application",
            APP_TITLE,
        )

        st.metric(
            "Default Page",
            DEFAULT_PAGE,
        )

    with col2:

        st.metric(
            "Table Page Size",
            TABLE_PAGE_SIZE,
        )

        st.metric(
            "Cache Enabled",
            "YES" if CACHE_ENABLED else "NO",
        )

    st.divider()

    st.info(
        "Settings are managed through NTIS-EOD configuration files."
    )


if __name__ == "__main__":
    show_settings()