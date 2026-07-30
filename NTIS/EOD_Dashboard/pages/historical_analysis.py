import streamlit as st

from EOD_Dashboard.data.historical_loader import (
    get_available_dates,
    load_snapshot,
)

from EOD_Dashboard.components.date_selector import (
    select_date,
)


def _show_dataframe(title, df):

    st.subheader(title)

    if df is None:
        st.info("Dataset not available")
        return

    if df.empty:
        st.info("No records found")
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def show_historical_analysis():

    st.header("NTIS HISTORICAL INTELLIGENCE")

    dates = get_available_dates()

    if not dates:
        st.warning("No historical snapshots available.")
        return

    selected_date = select_date(dates)

    if selected_date is None:
        return

    snapshot = load_snapshot(selected_date)

    if not snapshot:
        st.warning("Snapshot could not be loaded.")
        return

    st.success(f"Historical Snapshot : {selected_date}")

    for dataset_name, dataframe in snapshot.items():

        _show_dataframe(
            dataset_name.replace("_", " ").title(),
            dataframe,
        )


if __name__ == "__main__":
    show_historical_analysis()