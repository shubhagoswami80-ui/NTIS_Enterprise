import streamlit as st
from datetime import datetime


def _sort_dates(dates):
    """
    Sort newest first where possible.
    Falls back to string sorting.
    """
    try:
        return sorted(
            dates,
            key=lambda x: datetime.strptime(str(x), "%Y-%m-%d"),
            reverse=True,
        )
    except Exception:
        return sorted(
            [str(x) for x in dates],
            reverse=True,
        )


def select_date(dates):

    if not dates:
        st.warning("No EOD dates available.")
        return None

    ordered_dates = _sort_dates(dates)

    return st.selectbox(
        "Select EOD Date",
        ordered_dates,
        index=0,
        help="Latest trading day is selected by default.",
    )