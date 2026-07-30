import streamlit as st


def select_date(dates):
    if not dates:
        return None

    return st.selectbox("Select EOD Date", dates)
