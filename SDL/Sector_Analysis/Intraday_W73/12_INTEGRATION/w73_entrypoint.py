from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
DASH=ROOT/"11_DASHBOARD"
def render_intraday_w73_page():
    import streamlit as st
    st.info("W73 integration entry point is available. The standalone dashboard remains the authoritative live UI.")
    st.caption("Import only this function from an existing dashboard; do not import W73 internals.")
