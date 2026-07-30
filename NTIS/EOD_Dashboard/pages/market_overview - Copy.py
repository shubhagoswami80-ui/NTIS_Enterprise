import streamlit as st

from EOD_Dashboard.data.data_loader import load_dataset, get_dataset_info
from EOD_Dashboard.components.dashboard_cards import show_cards


def map_signal(value):
    value = str(value).upper()

    if value == "BULLISH":
        return "BUY"
    if value == "BEARISH":
        return "SELL"

    return "HOLD"


def show_market_overview():

    st.header("NTIS EOD MARKET OVERVIEW")

    df = load_dataset("ranking")

    if df is None or df.empty:
        st.warning("Ranking dataset not available")
        return

    if "Signal" in df.columns:
        df["Trade View"] = df["Signal"].apply(map_signal)

    show_cards(df)

    info = get_dataset_info("ranking")
    if info.get("available"):
        st.caption(f"Data Updated: {info.get('updated')}")

    st.subheader("BUY Opportunities")

    buy_df = df[df["Trade View"] == "BUY"]

    buy_cols = [
        "Rank",
        "Symbol",
        "CMP",
        "NTIS Score",
        "Support Strike",
        "Resistance Strike"
    ]

    buy_cols = [c for c in buy_cols if c in buy_df.columns]

    st.dataframe(
        buy_df[buy_cols].head(15),
        use_container_width=True,
        hide_index=True
    )

    st.subheader("SELL Opportunities")

    sell_df = df[df["Trade View"] == "SELL"]

    sell_cols = [
        "Rank",
        "Symbol",
        "CMP",
        "NTIS Score",
        "Support Strike",
        "Resistance Strike"
    ]

    sell_cols = [c for c in sell_cols if c in sell_df.columns]

    if sell_df.empty:
        st.info("No SELL opportunities available")

    else:
        st.dataframe(
            sell_df[sell_cols].head(15),
            use_container_width=True,
            hide_index=True
        )


if __name__ == "__main__":
    show_market_overview()
