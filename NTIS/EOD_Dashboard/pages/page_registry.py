"""
NTIS-EOD
Dashboard Page Registry

Central navigation registry.

Presentation routing layer only.
"""

from __future__ import annotations


from EOD_Dashboard.pages.market_overview import (
    show_market_overview,
)

from EOD_Dashboard.pages.historical_analysis import (
    show_historical_analysis,
)

from EOD_Dashboard.pages.historical_replay import (
    show_historical_replay,
)

from EOD_Dashboard.pages.buy_opportunities import (
    show_buy_opportunities,
)

from EOD_Dashboard.pages.sell_opportunities import (
    show_sell_opportunities,
)

from EOD_Dashboard.pages.probability_ranking import (
    show_probability_ranking,
)

from EOD_Dashboard.pages.oi_intelligence import (
    show_oi_intelligence,
)

from EOD_Dashboard.pages.support_intelligence import (
    show_support_intelligence,
)

from EOD_Dashboard.pages.resistance_intelligence import (
    show_resistance_intelligence,
)

from EOD_Dashboard.pages.pattern_intelligence import (
    show_pattern_intelligence,
)

from EOD_Dashboard.pages.buy_intelligence import (
    show_buy_intelligence,
)

from EOD_Dashboard.pages.sell_intelligence import (
    show_sell_intelligence,
)

from EOD_Dashboard.pages.settings import (
    show_settings,
)


PAGES = {

    # Core Dashboard

    "Dashboard": show_market_overview,

    "Market Overview": show_market_overview,


    # Individual Intelligence Views

    "BUY Opportunities": show_buy_opportunities,

    "SELL Opportunities": show_sell_opportunities,

    "Probability Ranking": show_probability_ranking,

    "OI Intelligence": show_oi_intelligence,

    "Support Intelligence": show_support_intelligence,

    "Resistance Intelligence": show_resistance_intelligence,

    "Pattern Intelligence": show_pattern_intelligence,


    # Integrated Intelligence Views

    "BUY Intelligence": show_buy_intelligence,

    "SELL Intelligence": show_sell_intelligence,


    # Historical

    "Historical Replay": show_historical_replay,


    # Legacy Historical View

    "Historical Analysis": show_historical_analysis,


    # Configuration

    "Settings": show_settings,

}


def available_pages() -> list[str]:
    """
    Return all registered dashboard pages.
    """

    return list(PAGES.keys())


def get_page(page_name: str):
    """
    Return page handler.
    """

    return PAGES.get(
        page_name
    )


def page_exists(page_name: str) -> bool:
    """
    Check whether page exists.
    """

    return page_name in PAGES


def register_page(
    name: str,
    handler,
) -> None:
    """
    Register additional page dynamically.
    """

    if callable(handler):
        PAGES[name] = handler


def unregister_page(
    name: str,
) -> None:
    """
    Remove page safely.
    """

    PAGES.pop(
        name,
        None,
    )