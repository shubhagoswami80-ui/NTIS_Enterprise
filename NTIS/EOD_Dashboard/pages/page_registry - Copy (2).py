"""
NTIS EOD Dashboard Page Registry

Central registry for all dashboard pages.
"""

from EOD_Dashboard.pages.market_overview import show_market_overview
from EOD_Dashboard.pages.historical_analysis import show_historical_analysis


PAGES = {
    "Dashboard": show_market_overview,
    "Market Overview": show_market_overview,
    "Historical Replay": show_historical_analysis,
}


def available_pages():
    """
    Returns the navigation menu.
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
    Register future dashboard pages without
    modifying dashboard_app.py.
    """
    if callable(handler):
        PAGES[name] = handler


def unregister_page(name):
    """
    Remove a page safely.
    """
    PAGES.pop(name, None)