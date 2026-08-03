"""
NTIS-EOD
Historical Replay Page

Integrated Historical Intelligence View

Presentation Layer Only

Includes:

    - Historical Snapshot Loading
    - Replay Dataset Display
    - Shared Filters
    - Outcome Analytics

No calculations.
No historical engine changes.
"""

from __future__ import annotations

import streamlit as st

from EOD_Dashboard.data.historical_loader import (
    get_available_dates,
    load_snapshot,
)

from EOD_Dashboard.components.date_selector import (
    select_date,
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


PAGE_TITLE = "NTIS HISTORICAL REPLAY"


def _render_snapshot_dataset(
    dataset_name,
    dataframe,
) -> None:
    """
    Render historical snapshot dataset.
    """

    if dataframe is None:
        st.info(
            f"{dataset_name} dataset unavailable."
        )
        return

    if dataframe.empty:
        st.info(
            f"No records available for {dataset_name}."
        )
        return


    filtered_dataframe = render_intelligence_filters(
        dataframe
    )


    if filtered_dataframe.empty:
        st.info(
            "No records match selected filters."
        )
        return


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
        title=dataset_name.replace(
            "_",
            " ",
        ).title(),
        filename=f"{dataset_name}_replay.csv",
    )


def show_historical_replay() -> None:
    """
    Render historical replay intelligence.
    """

    st.header(
        PAGE_TITLE
    )


    dates = get_available_dates()

    if not dates:
        st.warning(
            "No historical snapshots available."
        )
        return


    selected_date = select_date(
        dates
    )


    if selected_date is None:
        return


    snapshot = load_snapshot(
        selected_date
    )


    if not snapshot:
        st.warning(
            "Historical snapshot could not be loaded."
        )
        return


    st.success(
        f"Historical Snapshot : {selected_date}"
    )


    for dataset_name, dataframe in snapshot.items():

        _render_snapshot_dataset(
            dataset_name,
            dataframe,
        )


if __name__ == "__main__":
    show_historical_replay()