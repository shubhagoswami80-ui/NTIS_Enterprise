
import streamlit as st
from datetime import datetime

def render_status_bar():

    st.divider()

    c1,c2 = st.columns(2)

    c1.caption("Data Status: OK")
    c2.caption(
        f"Last Updated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
    )
