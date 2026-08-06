import streamlit as st

from EOD_Dashboard.data.historical_loader import (
    get_available_dates,
    load_snapshot,
)

from EOD_Dashboard.data.intelligence_builder import (
    build_historical_from_runtime,
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

    _render_runtime_historical_panel()

    for dataset_name, dataframe in snapshot.items():

        _show_dataframe(
            dataset_name.replace("_", " ").title(),
            dataframe,
        )


def _render_runtime_historical_panel():
    """
    Render the Historical Intelligence runtime payload exposed
    by `build_historical_from_runtime()`.

    This UI is read-only and displays raw runtime objects.
    """

    try:
        payload = build_historical_from_runtime()
    except Exception:
        payload = None

    st.subheader("Runtime Historical Intelligence Summary")

    if not payload:
        st.info("No runtime historical intelligence available.")
        return

    # Top-level status metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Replay Status", payload.get("replay_status") or "N/A")

    with col2:
        st.metric("Calibration Status", payload.get("calibration_status") or "N/A")

    with col3:
        st.metric("Learning Status", payload.get("learning_status") or "N/A")

    # Repository summary (raw)
    st.markdown("**Repository Summary**")
    st.write(payload.get("repository_summary"))

    # Historical intelligence (raw)
    st.markdown("**Historical Intelligence**")
    st.write(payload.get("historical_intelligence"))

    # Historical evidence and service summary (raw)
    st.markdown("**Historical Evidence**")
    st.write(payload.get("historical_evidence"))

    st.markdown("**Historical Service Summary**")
    st.write(payload.get("historical_service_summary"))

    st.markdown("**Candidate Ranking**")
    st.write(payload.get("candidate_ranking"))




if __name__ == "__main__":
    show_historical_analysis()