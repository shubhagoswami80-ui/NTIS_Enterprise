# ---------------------------------------------------------------------
# Bundle 01 – Step 3
# Replacement: Intraday/intraday_trade_memory_connector.py
#
# Purpose:
#     Persist Pattern_DNA / Pattern_ID into NTIS learning memory.
#
# Existing behaviour is unchanged.
# ---------------------------------------------------------------------


def process_trade_memory():

    trade_file = get_latest_trade_file()

    print(
        "Reading Trade File:",
        trade_file
    )

    df = pd.read_csv(
        trade_file
    )

    # -------------------------------------------------------------
    # Ensure downstream intelligence columns exist
    # -------------------------------------------------------------

    for col in (
        "Pattern",
        "Pattern_DNA",
        "Pattern_ID",
    ):
        if col not in df.columns:
            df[col] = ""

    for _, row in df.iterrows():

        event = {

            "Date":
                datetime.today().strftime("%Y-%m-%d"),

            "Snapshot_Time":
                datetime.today().strftime("%H:%M"),

            "Symbol":
                get_value(
                    row,
                    ["Symbol"]
                ),

            "Direction":
                get_value(
                    row,
                    [
                        "Final Signal",
                        "Validation Signal",
                        "Trade Bias"
                    ]
                ),

            # -------------------------------------------------
            # Pattern Intelligence
            # -------------------------------------------------

            "Pattern":
                get_value(
                    row,
                    ["Pattern"]
                ),

            "Pattern_DNA":
                get_value(
                    row,
                    ["Pattern_DNA"]
                ),

            "Pattern_ID":
                get_value(
                    row,
                    ["Pattern_ID"]
                ),

            # -------------------------------------------------

            "NTIS_Score":
                get_value(
                    row,
                    [
                        "NTIS Score",
                        "NTIS Intraday Score"
                    ]
                ),

            "Probability":
                get_value(
                    row,
                    [
                        "Probability",
                        "Intraday Probability %",
                        "BUY Probability %"
                    ]
                ),

            "Confidence":
                get_value(
                    row,
                    ["Confidence"]
                ),

            "Entry_Price":
                get_value(
                    row,
                    [
                        "Entry Price",
                        "Entry Close"
                    ]
                ),

            "Trade_Reason":
                get_value(
                    row,
                    [
                        "Reason",
                        "Trade Reason"
                    ]
                ),

            "Outcome":
                "PENDING"

        }

        save_memory_event(
            event
        )


if __name__ == "__main__":

    process_trade_memory()