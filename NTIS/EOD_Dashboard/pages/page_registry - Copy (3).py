"""
NTIS EOD Dashboard Page Registry

Central registry for all dashboard pages.

Bundle 1
---------
Shared Intelligence Framework + Navigation
"""

from EOD_Dashboard.pages.market_overview import show_market_overview
from EOD_Dashboard.pages.historical_analysis import show_historical_analysis


# ------------------------------------------------------------
# Temporary placeholder until each page is implemented
# ------------------------------------------------------------

def _coming_soon():
    import streamlit as st

    st.info("This module will be implemented in the upcoming bundle.")


# ------------------------------------------------------------
# Central Page Registry
# ------------------------------------------------------------

PAGES = {
    # Existing Pages
    "Dashboard": show_market_overview,
    "Market Overview": show_market_overview,
    "Historical Replay": show_historical_analysis,

    # Intelligence Pages
    "BUY Opportunities": _coming_soon,
    "SELL Opportunities": _coming_soon,
    "Probability Ranking": _coming_soon,
    "OI Intelligence": _coming_soon,
    "Support Intelligence": _coming_soon,
    "Resistance Intelligence": _coming_soon,
    "Pattern Intelligence": _coming_soon,

    # Future
    "Settings": _coming_soon,
}


# ------------------------------------------------------------
# Registry Helpers
# ------------------------------------------------------------

def available_pages():
    """
    Returns all registered dashboard pages.
    """
    return list(PAGES.keys())


def get_page(page_name):
    """
    Returns the page callable.
    """
    return PAGES.get(page_name)


def page_exists(page_name):
    """
    Check whether a page is registered.
    """
    return page_name in PAGES


def register_page(name, handler):
    """
    Register a dashboard page dynamically.
    """
    if callable(handler):
        PAGES[name] = handler


def unregister_page(name):
    """
    Remove a page safely.
    """
    PAGES.pop(name, None)