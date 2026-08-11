"""
=========================================================
NTIS Intraday Accuracy Tracker
Version : 2.0

Purpose:
    Analyse replay results and create accuracy report.

Input:
    intraday_backtest_results.csv

Output:
    intraday_accuracy_report.csv

Rules:
    - Ignore FILTERED records
    - Calculate replay accuracy
    - Prepare learning dataset
=========================================================
"""

from pathlib import Path
import pandas as pd


def create_accuracy_report(
    replay_file
):

    replay_file = Path(
        replay_file
    )


    if not replay_file.exists():

        raise FileNotFoundError(
            f"Replay file not found: {replay_file}"
        )


    df = pd.read_csv(
        replay_file
    )


    required = [
        "Outcome",
        "Pattern",
        "Return %"
    ]


    for col in required:

        if col not in df.columns:

            raise KeyError(
                f"Missing column: {col}"
            )


    # Keep only actual replayed trades

    accuracy_df = df[
        df["Outcome"].isin(
            [
                "TARGET HIT",
                "STOP LOSS HIT",
                "EOD EXIT"
            ]
        )
    ].copy()


    if accuracy_df.empty:

        raise ValueError(
            "No completed replay trades found"
        )


    accuracy_df["Win"] = (
        accuracy_df["Outcome"]
        ==
        "TARGET HIT"
    )


    total_trades = len(
        accuracy_df
    )

    target_hits = sum(
        accuracy_df["Outcome"]
        ==
        "TARGET HIT"
    )

    stop_losses = sum(
        accuracy_df["Outcome"]
        ==
        "STOP LOSS HIT"
    )

    eod_exit = sum(
        accuracy_df["Outcome"]
        ==
        "EOD EXIT"
    )


    win_percentage = (
        target_hits /
        total_trades
    ) * 100


    average_return = (
        accuracy_df["Return %"]
        .mean()
    )


    summary = pd.DataFrame(
        {
            "Metric": [
                "Total Trades",
                "Target Hits",
                "Stop Loss Hits",
                "EOD Exits",
                "Win %",
                "Average Return %"
            ],

            "Value": [
                total_trades,
                target_hits,
                stop_losses,
                eod_exit,
                round(win_percentage,2),
                round(average_return,2)
            ]
        }
    )


    pattern_accuracy = (
        accuracy_df
        .groupby("Pattern")
        .agg(
            Signals=("Pattern","count"),
            Target_Hits=(
                "Outcome",
                lambda x:
                sum(x=="TARGET HIT")
            ),
            Average_Return=(
                "Return %",
                "mean"
            )
        )
        .reset_index()
    )


    output = (
        replay_file.parent /
        "intraday_accuracy_report.csv"
    )


    accuracy_df.to_csv(
        output,
        index=False
    )


    excel_output = (
        replay_file.parent /
        "intraday_accuracy_report.xlsx"
    )


    with pd.ExcelWriter(
        excel_output,
        engine="openpyxl"
    ) as writer:

        summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False
        )

        accuracy_df.to_excel(
            writer,
            sheet_name="Trades",
            index=False
        )

        pattern_accuracy.to_excel(
            writer,
            sheet_name="Pattern Analysis",
            index=False
        )


    return output



if __name__ == "__main__":

    print(
        "Use create_accuracy_report(replay_file)"
    )