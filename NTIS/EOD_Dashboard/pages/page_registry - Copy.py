"""
NTIS EOD Dashboard Page Registry

Controlled page list.
"""

PAGES = {
    "Market Overview": "market_overview"
}


def available_pages():
    return list(PAGES.keys())
