"""
NTIS-EOD
Support Intelligence Page

Presentation Layer Only

Includes:

    - Support Intelligence View
    - Shared Filters
    - Support Analytics
    - Intelligence Table

Source:
    ranking dataset

No calculations.
No support logic changes.
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
    render_signal_distribution,
    render_ntis_score_distribution,
)

from EOD_Dashboard.components.intelligence_table import (
    render_intelligence_table,
)


PAGE_TITLE = "NTIS SUPPORT INTELLIGENCE"


DISPLAY_COLUMNS = (
    "Rank",
    "Symbol",
    "CMP",
    "Support",
    "Support Strength",
    "Near Support",
    "Support Resistance Score",
    "NTIS Score",
    "Signal",
)


def show_support_intelligence() -> None:
    """
    Render support intelligence page.
    """

    st.header(
        PAGE_TITLE
    )

    dataframe = load_dataset(
        "ranking"
    )

    if dataframe is None or dataframe.empty:
        st.warning(
            "Ranking dataset not available."
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
        "ranking"
    ) or {}


    st.subheader(
        "Support Analytics"
    )


    chart_col1, chart_col2 = st.columns(2)


    with chart_col1:

        render_signal_distribution(
            filtered_dataframe
        )


    with chart_col2:

        render_ntis_score_distribution(
            filtered_dataframe
        )


    render_intelligence_table(
        dataframe=filtered_dataframe,
        title="Support Intelligence",
        preferred_columns=DISPLAY_COLUMNS,
        updated=dataset_info.get(
            "updated"
        ),
        filename="support_intelligence.csv",
    )


if __name__ == "__main__":
    show_support_intelligence()