"""
NTIS Intraday Outcome Engine v2.0

Calculates historical signal outcomes using EOD OHLC.
"""

import pandas as pd


def calculate_outcomes(intraday_df, eod_df):

    eod_required = [
        "Symbol",
        "High",
        "Low",
        "Close"
    ]

    for col in eod_required:
        if col not in eod_df.columns:
            raise KeyError(
                f"EOD column missing: {col}"
            )

    merged = intraday_df.merge(
        eod_df[eod_required],
        on="Symbol",
        how="left"
    )

    results = []

    for _, row in merged.iterrows():

        outcome = "NO_DATA"
        exit_price = None

        if pd.notna(row.get("High")):

            bias = str(
                row.get("Final Bias", "")
            ).upper()

            if bias == "BUY":

                if row["High"] >= row["Target"]:
                    outcome = "TARGET HIT"
                    exit_price = row["Target"]

                elif row["Low"] <= row["Stop Loss"]:
                    outcome = "STOP LOSS HIT"
                    exit_price = row["Stop Loss"]

                else:
                    outcome = "EOD EXIT"
                    exit_price = row["Close"]


            elif bias == "SELL":

                if row["Low"] <= row["Target"]:
                    outcome = "TARGET HIT"
                    exit_price = row["Target"]

                elif row["High"] >= row["Stop Loss"]:
                    outcome = "STOP LOSS HIT"
                    exit_price = row["Stop Loss"]

                else:
                    outcome = "EOD EXIT"
                    exit_price = row["Close"]


        record = row.to_dict()

        record["Outcome"] = outcome
        record["Exit Price"] = exit_price

        if exit_price and row["Entry Price"]:
            record["Points"] = (
                exit_price - row["Entry Price"]
                if str(row["Final Bias"]).upper() == "BUY"
                else row["Entry Price"] - exit_price
            )

            record["Return %"] = (
                record["Points"] /
                row["Entry Price"]
            ) * 100

        else:
            record["Points"] = 0
            record["Return %"] = 0

        results.append(record)

    return pd.DataFrame(results)
