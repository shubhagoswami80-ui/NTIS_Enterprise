"""
NTIS-EOD
SELL Intelligence Page

Integrated Decision View

Presentation Layer Only

Includes:

    - Ranking Intelligence
    - Probability Intelligence
    - Pattern Intelligence
    - OI Intelligence
    - Support / Resistance Intelligence
    - Outcome Evidence
    - Shared Filters
    - Intelligence Charts

No calculations.
No engine changes.
"""

from __future__ import annotations

import streamlit as st

from EOD_Dashboard.data.intelligence_builder import (
    build_intelligence_view,
    filter_sell_candidates,
)

from EOD_Dashboard.components.intelligence_filters import (
    render_intelligence_filters,
)

from EOD_Dashboard.components.intelligence_charts import (
    render_signal_distribution,
    render_confidence_distribution,
    render_ntis_score_distribution,
    render_probability_distribution,
)

from EOD_Dashboard.components.intelligence_table import (
    render_intelligence_table,
)


PAGE_TITLE = "NTIS SELL INTELLIGENCE"


DISPLAY_COLUMNS = (
    "Rank",
    "Symbol",
    "CMP",
    "NTIS Score",
    "Signal",
    "SELL Probability %",
    "Probability",
    "Confidence",
    "Pattern",
    "Pattern Reason",
    "OI Score",
    "OI Chg %",
    "Support Strike",
    "Resistance Strike",
    "Actual Return %",
    "Outcome",
)


def show_sell_intelligence() -> None:
    """
    Render integrated SELL intelligence view.
    """

    st.header(
        PAGE_TITLE
    )

    intelligence = build_intelligence_view()

    if intelligence.empty:
        st.warning(
            "Intelligence dataset not available."
        )
        return


    sell_dataframe = filter_sell_candidates(
        intelligence
    )

    if sell_dataframe.empty:
        st.info(
            "No SELL intelligence candidates available."
        )
        return


    filtered_dataframe = render_intelligence_filters(
        sell_dataframe
    )


    if filtered_dataframe.empty:
        st.info(
            "No records match selected filters."
        )
        return


    st.subheader(
        "SELL Intelligence Analytics"
    )


    chart_col1, chart_col2 = st.columns(2)


    with chart_col1:

        render_signal_distribution(
            filtered_dataframe
        )


    with chart_col2:

        render_confidence_distribution(
            filtered_dataframe
        )


    render_ntis_score_distribution(
        filtered_dataframe
    )


    render_probability_distribution(
        filtered_dataframe
    )


    render_intelligence_table(
        dataframe=filtered_dataframe,
        title="SELL Intelligence",
        preferred_columns=DISPLAY_COLUMNS,
        filename="sell_intelligence.csv",
    )


if __name__ == "__main__":
    show_sell_intelligence()