"""
NTIS EOD Dashboard Status Bar

Presentation Layer Only
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st


def render_status_bar(output_path: str | Path | None = None) -> None:
    """
    Render dashboard status bar.

    Parameters
    ----------
    output_path : str | Path | None
        Optional output file used to display the latest data status.

    Notes
    -----
    UI component only.
    No business logic should be implemented here.
    """

    st.divider()

    col_status, col_source, col_time = st.columns((2, 3, 2))

    if output_path is None:
        current = datetime.now()

        col_status.success("Dashboard Ready")
        col_source.caption(
            f"Session : {current.strftime('%d-%m-%Y')}"
        )
        col_time.caption(
            current.strftime("%H:%M:%S")
        )
        return

    path = Path(output_path)

    if path.exists():

        last_updated = datetime.fromtimestamp(
            path.stat().st_mtime
        ).strftime("%d-%m-%Y %H:%M:%S")

        col_status.success("Data : READY")
        col_source.caption(
            f"Source : {path.name}"
        )
        col_time.caption(
            f"Updated : {last_updated}"
        )

    else:

        col_status.error("Data : Missing")
        col_source.caption(str(path))
        col_time.caption("Waiting")