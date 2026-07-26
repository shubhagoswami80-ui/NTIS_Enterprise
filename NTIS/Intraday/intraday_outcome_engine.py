"""
=========================================================
NTIS Intraday Outcome Engine
Version : 2.1

Purpose:
    Calculate historical intraday trade outcomes.

Input:
    Intraday validated trade candidates
    EOD OHLC data

Output:
    Replay outcome dataframe

Rules:
    - BUY/SELL aware calculation
    - Positive reward / negative risk handling
    - Keeps outcome explanation
=========================================================
"""

import pandas as pd



def calculate_outcomes(
    intraday_df,
    eod_df
):

    required_eod = [
        "Symbol",
        "High",
        "Low",
        "Close"
    ]


    for col in required_eod:

        if col not in eod_df.columns:

            raise KeyError(
                f"EOD column missing: {col}"
            )


    merged = intraday_df.merge(
        eod_df[required_eod],
        on="Symbol",
        how="left"
    )


    results = []


    for _, row in merged.iterrows():

        record = row.to_dict()


        outcome = "NO DATA"
        reason = "EOD OHLC data unavailable"
        exit_price = None
        points = 0
        return_pct = 0


        if pd.notna(row.get("High")):

            bias = str(
                row.get("Final Bias", "")
            ).upper()


            entry = row.get(
                "Entry Price"
            )

            stop_loss = row.get(
                "Stop Loss"
            )

            target = row.get(
                "Target"
            )


            if pd.isna(entry) or pd.isna(stop_loss) or pd.isna(target):

                outcome = "INVALID"
                reason = (
                    "Missing trade parameters"
                )


            elif bias == "BUY":


                if row["High"] >= target:

                    outcome = "TARGET HIT"
                    reason = (
                        "Target reached during replay range"
                    )

                    exit_price = target


                elif row["Low"] <= stop_loss:

                    outcome = "STOP LOSS HIT"
                    reason = (
                        "Stop loss breached during replay range"
                    )

                    exit_price = stop_loss


                else:

                    outcome = "EOD EXIT"
                    reason = (
                        "Neither target nor stop reached; exited at close"
                    )

                    exit_price = row["Close"]


                if exit_price is not None:

                    points = (
                        exit_price - entry
                    )


            elif bias == "SELL":


                if row["Low"] <= target:

                    outcome = "TARGET HIT"
                    reason = (
                        "Target reached during replay range"
                    )

                    exit_price = target


                elif row["High"] >= stop_loss:

                    outcome = "STOP LOSS HIT"
                    reason = (
                        "Stop loss breached during replay range"
                    )

                    exit_price = stop_loss


                else:

                    outcome = "EOD EXIT"
                    reason = (
                        "Neither target nor stop reached; exited at close"
                    )

                    exit_price = row["Close"]


                if exit_price is not None:

                    points = (
                        entry - exit_price
                    )


            if entry and points:

                return_pct = (
                    points /
                    entry
                ) * 100


        record["Outcome"] = outcome
        record["Outcome Reason"] = reason
        record["Exit Price"] = exit_price
        record["Points"] = points
        record["Return %"] = return_pct


        results.append(record)


    return pd.DataFrame(results)