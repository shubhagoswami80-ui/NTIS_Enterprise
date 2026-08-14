from __future__ import annotations

import streamlit as st

from derivative_signal.dashboard import render

st.set_page_config(
    page_title="NTIS SDL — Decision Signals",
    page_icon="📊",
    layout="wide",
)

render()
