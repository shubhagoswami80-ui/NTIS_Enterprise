"""
NTIS-EOD
Pattern Intelligence Page

Presentation Layer Only

Includes:

    - Pattern Intelligence View
    - Shared Filters
    - Pattern Analytics
    - Intelligence Table

Source:
    patterns dataset

No calculations.
No pattern logic changes.
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
    render_confidence_distribution,
)

from EOD_Dashboard.components.intelligence_table import (
    render_intelligence_table,
)


PAGE_TITLE = "NTIS PATTERN INTELLIGENCE"


DISPLAY_COLUMNS = (
    "Rank",
    "Symbol",
    "Pattern",
    "Pattern Type",
    "Pattern Score",
    "Pattern Reason",
    "NTIS Score",
    "Probability",
    "Confidence",
    "Signal",
)


def show_pattern_intelligence() -> None:
    """
    Render pattern intelligence page.
    """

    st.header(
        PAGE_TITLE
    )

    dataframe = load_dataset(
        "patterns"
    )

    if dataframe is None or dataframe.empty:
        st.warning(
            "Pattern dataset not available."
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
        "patterns"
    ) or {}


    st.subheader(
        "Pattern Analytics"
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


    render_intelligence_table(
        dataframe=filtered_dataframe,
        title="Pattern Intelligence",
        preferred_columns=DISPLAY_COLUMNS,
        updated=dataset_info.get(
            "updated"
        ),
        filename="pattern_intelligence.csv",
    )


if __name__ == "__main__":
    show_pattern_intelligence()