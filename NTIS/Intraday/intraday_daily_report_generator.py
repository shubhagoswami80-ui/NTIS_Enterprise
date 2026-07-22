"""
=========================================================
NTIS Intraday Daily Report Generator
Version : 1.0

Purpose:
    Create trader-friendly daily intraday report.

Input:
    intraday_trade_candidates.csv

Output:
    intraday_daily_trade_report.xlsx

Independent Intraday Module
=========================================================
"""

from pathlib import Path
import pandas as pd


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\2026-07-22\intraday_trade_candidates.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\2026-07-22\intraday_daily_trade_report.xlsx"
)


class IntradayDailyReportGenerator:


    def run(self):

        df = pd.read_csv(INPUT_FILE)


        buy = df[
            df["Validation Signal"] == "VALID BUY"
        ].copy()


        sell = df[
            df["Validation Signal"] == "VALID SELL"
        ].copy()


        watch = df[
            df["Validation Signal"] == "WATCH"
        ].copy()


        summary = pd.DataFrame(
            {
                "Metric": [
                    "Total Stocks",
                    "BUY Candidates",
                    "SELL Candidates",
                    "Watchlist"
                ],
                "Value": [
                    len(df),
                    len(buy),
                    len(sell),
                    len(watch)
                ]
            }
        )


        columns = [
            "Symbol",
            "Pattern",
            "Intraday Probability %",
            "Confidence",
            "Validation Signal",
            "Risk Level",
            "Entry Price",
            "Stop Loss",
            "Target"
        ]


        with pd.ExcelWriter(
            OUTPUT_FILE,
            engine="openpyxl"
        ) as writer:

            summary.to_excel(
                writer,
                sheet_name="Summary",
                index=False
            )

            buy[
                [c for c in columns if c in buy.columns]
            ].to_excel(
                writer,
                sheet_name="BUY Candidates",
                index=False
            )

            sell[
                [c for c in columns if c in sell.columns]
            ].to_excel(
                writer,
                sheet_name="SELL Candidates",
                index=False
            )

            watch[
                [c for c in columns if c in watch.columns]
            ].to_excel(
                writer,
                sheet_name="Watchlist",
                index=False
            )


        return OUTPUT_FILE


if __name__ == "__main__":

    result = IntradayDailyReportGenerator().run()

    print("=" * 60)
    print("INTRADAY DAILY REPORT CREATED")
    print(result)
    print("=" * 60)
