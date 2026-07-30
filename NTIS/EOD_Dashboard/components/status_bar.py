import streamlit as st
from datetime import datetime
from pathlib import Path


def render_status_bar(output_path=None):

    st.divider()

    c1, c2, c3 = st.columns([2, 3, 2])

    if output_path:

        path = Path(output_path)

        if path.exists():

            modified = datetime.fromtimestamp(
                path.stat().st_mtime
            ).strftime("%d-%m-%Y %H:%M:%S")

            c1.success("Data : READY")
            c2.caption(f"Source : {path.name}")
            c3.caption(f"Updated : {modified}")

        else:

            c1.error("Data : Missing")
            c2.caption(str(path))
            c3.caption("Waiting")

    else:

        c1.success("Dashboard Ready")
        c2.caption(
            f"Session : {datetime.now().strftime('%d-%m-%Y')}"
        )
        c3.caption(
            datetime.now().strftime("%H:%M:%S")
        )