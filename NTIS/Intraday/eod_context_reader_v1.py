"""
NTIS Intraday EOD Context Reader v1.0

Purpose:
    Read previous EOD Daywise Price & OI reports
    and provide historical context for Intraday Learning.

Rules:
    - Read only
    - No EOD modifications
    - Dynamic year/month handling
    - No hardcoded trading date
"""

from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

EOD_BASE = Path(r"E:\NSE_Daily_Analysis")


# ============================================================
# FIND PREVIOUS TRADING REPORT
# ============================================================

def find_previous_eod_report(trading_date):
    """
    Find previous available EOD Price/OI report.
    """

    if isinstance(trading_date, str):
        trading_date = datetime.strptime(
            trading_date,
            "%Y-%m-%d"
        )

    check_date = trading_date - timedelta(days=1)

    while True:

        year = str(check_date.year)
        month = check_date.strftime("%B")

        price_folder = (
            EOD_BASE
            / year
            / month
            / "01_Price_OI"
        )

        pattern = (
            "Daywise_Price_and_OI_Summary"
            f"*{check_date.strftime('%Y-%m-%d')}*.xlsx"
        )

        files = list(price_folder.glob(pattern))

        if files:
            return files[0]

        check_date -= timedelta(days=1)


# ============================================================
# LOAD EOD CONTEXT
# ============================================================

def load_eod_context(trading_date):

    report = find_previous_eod_report(
        trading_date
    )

    print(
        "Using EOD Context:",
        report
    )

    df = pd.read_excel(report)


    required_map = {

        "Symbol": "Symbol",

        "Close": "Previous_Close",
        "High": "Previous_High",
        "Low": "Previous_Low",

        "Volume": "Previous_Volume",

        "OI": "Previous_OI",
        "OI Chg (%)": "Previous_OI_Chg_%",

        "PCR": "Previous_PCR",

        "IV": "Previous_IV",

        "BuildUp": "Previous_BuildUp"
    }


    output = pd.DataFrame()


    for source, target in required_map.items():

        if source in df.columns:
            output[target] = df[source]

        else:
            output[target] = None


    return output



# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    context = load_eod_context(
        "2026-07-23"
    )

    print()
    print(context.head())
