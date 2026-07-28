
import streamlit as st

from EOD_Dashboard.data.historical_loader import (
    get_available_dates,
    load_snapshot
)


def show_historical_analysis():

    st.header("NTIS HISTORICAL INTELLIGENCE")

    dates = get_available_dates()

    if not dates:
        st.warning("No historical data available")
        return

    selected = st.selectbox(
        "Select EOD Date",
        dates
    )

    snapshot = load_snapshot(selected)

    st.success(f"Historical Snapshot: {selected}")

    for name, df in snapshot.items():

        st.subheader(name.replace("_", " ").title())

        if df is not None:
            st.dataframe(
                df.head(10),
                use_container_width=True
            )


if __name__ == "__main__":
    show_historical_analysis()
