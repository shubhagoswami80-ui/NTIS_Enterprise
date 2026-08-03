"""
NTIS-EOD
Probability Ranking Page

Presentation Layer Only

Includes:

    - Probability Intelligence
    - Shared Filters
    - Probability Charts
    - Intelligence Table

No calculations.
No probability modification.
No engine changes.
"""

from __future__ import annotations

import streamlit as st

from EOD_Dashboard.data.data_loader import (
    load_dataset,
    get_dataset_info,
)

from EOD_Dashboard.components.intelligence_filters import (
    render_intelligence_filters,
)

from EOD_Dashboard.components.intelligence_charts import (
    render_probability_distribution,
    render_confidence_distribution,
)

from EOD_Dashboard.components.intelligence_table import (
    render_intelligence_table,
)


PAGE_TITLE = "NTIS PROBABILITY RANKING"


DISPLAY_COLUMNS = (
    "Rank",
    "Symbol",
    "Probability",
    "BUY Probability %",
    "SELL Probability %",
    "Confidence",
    "NTIS Score",
    "Signal",
    "Pattern",
)


def show_probability_ranking() -> None:
    """
    Render probability ranking intelligence page.
    """

    st.header(
        PAGE_TITLE
    )

    dataframe = load_dataset(
        "probability"
    )

    if dataframe is None or dataframe.empty:
        st.warning(
            "Probability dataset not available."
        )
        return


    dataframe = dataframe.copy()


    filtered_dataframe = render_intelligence_filters(
        dataframe
    )


    if filtered_dataframe.empty:
        st.info(
            "No records match selected filters."
        )
        return


    dataset_info = get_dataset_info(
        "probability"
    ) or {}


    st.subheader(
        "Probability Analytics"
    )


    render_probability_distribution(
        filtered_dataframe
    )


    render_confidence_distribution(
        filtered_dataframe
    )


    render_intelligence_table(
        dataframe=filtered_dataframe,
        title="Probability Ranking",
        preferred_columns=DISPLAY_COLUMNS,
        updated=dataset_info.get(
            "updated"
        ),
        filename="probability_ranking.csv",
    )


if __name__ == "__main__":
    show_probability_ranking()