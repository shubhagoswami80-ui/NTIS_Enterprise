"""
NTIS-EOD
OI Intelligence Page

Presentation Layer Only

Includes:

    - OI Intelligence View
    - Shared Filters
    - OI Analytics
    - Intelligence Table

Source:
    ranking dataset

No calculations.
No OI logic changes.
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


PAGE_TITLE = "NTIS OI INTELLIGENCE"


DISPLAY_COLUMNS = (
    "Rank",
    "Symbol",
    "CMP",
    "Price Chg %",
    "OI Chg %",
    "OI Score",
    "Volume Chg (%)",
    "Support Resistance Score",
    "NTIS Score",
    "Signal",
)


def show_oi_intelligence() -> None:
    """
    Render OI intelligence page.
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
        "OI Analytics"
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
        title="OI Intelligence",
        preferred_columns=DISPLAY_COLUMNS,
        updated=dataset_info.get(
            "updated"
        ),
        filename="oi_intelligence.csv",
    )


if __name__ == "__main__":
    show_oi_intelligence()