"""
NTIS EOD Dashboard Styles
"""

import streamlit as st


def apply_dashboard_style():
    st.markdown(
        """
        <style>

        .main > div {
            padding-top: 0.6rem;
            padding-bottom: 1rem;
        }

        section[data-testid="stSidebar"]{
            width:280px;
        }

        div[data-testid="metric-container"]{
            border:1px solid rgba(120,120,120,.18);
            border-radius:10px;
            padding:12px;
        }

        div[data-testid="metric-container"] label{
            font-weight:600;
        }

        .stDataFrame{
            border-radius:8px;
        }

        .block-container{
            max-width:98%;
        }

        footer{
            visibility:hidden;
        }

        #MainMenu{
            visibility:hidden;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )