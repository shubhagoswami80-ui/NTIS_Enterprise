"""
NTIS-EOD
Intelligence Table Component

Presentation Layer Only

Shared table renderer for:

    - BUY Intelligence
    - SELL Intelligence
    - Probability Ranking
    - Pattern Intelligence
    - OI Intelligence
    - Support / Resistance Intelligence
    - Historical Replay

Rules:
    - No backend logic
    - No calculations
    - No data modification
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st


DEFAULT_ROWS = 50


def _select_columns(
    dataframe: pd.DataFrame,
    preferred_columns: Iterable[str] | None,
) -> list[str]:
    """
    Return available display columns only.
    """

    if preferred_columns is None:
        return list(dataframe.columns)

    return [
        column
        for column in preferred_columns
        if column in dataframe.columns
    ]


def _format_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Presentation formatting only.

    Does not alter source dataframe.
    """

    display_df = dataframe.copy()

    numeric_columns = display_df.select_dtypes(
        include="number"
    ).columns

    for column in numeric_columns:

        if "%" in column:
            display_df[column] = (
                display_df[column]
                .round(2)
            )

        elif column in (
            "CMP",
            "Entry Close",
            "Support Strike",
            "Resistance Strike",
        ):
            display_df[column] = (
                display_df[column]
                .round(2)
            )

    return display_df


def _render_download(
    dataframe: pd.DataFrame,
    filename: str,
) -> None:
    """
    CSV export.
    """

    csv = dataframe.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        label="Download CSV",
        data=csv,
        file_name=filename,
        mime="text/csv",
    )


def render_intelligence_table(
    *,
    dataframe: pd.DataFrame,
    title: str,
    preferred_columns: Iterable[str] | None = None,
    updated: str | None = None,
    filename: str = "ntis_export.csv",
) -> None:
    """
    Render reusable intelligence table.
    """

    if dataframe is None or dataframe.empty:

        st.info(
            "No records available."
        )

        return


    st.subheader(
        title
    )


    if updated:

        st.caption(
            f"Last Updated : {updated}"
        )


    columns = _select_columns(
        dataframe,
        preferred_columns,
    )


    display_df = _format_dataframe(
        dataframe[columns]
    )


    row_count = st.selectbox(
        "Rows to display",
        options=[
            25,
            50,
            100,
            250,
            500,
        ],
        index=1,
        key=f"{title}_rows",
    )


    st.dataframe(
        display_df.head(row_count),
        hide_index=True,
        use_container_width=True,
    )


    st.caption(
        f"Showing {min(row_count, len(display_df)):,} "
        f"of {len(display_df):,} records"
    )


    _render_download(
        display_df,
        filename,
    )