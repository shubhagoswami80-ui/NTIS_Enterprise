"""
NTIS Intraday EOD Context Reader v1.5

Purpose:
    Read previous available EOD Price/OI report
    for Intraday Learning and Replay.

Rules:
    - Read only
    - No EOD modification
    - No hardcoded paths
    - Path controlled by config_loader.py
"""

from datetime import datetime
import re

import pandas as pd

from config_loader import (
    EOD_ROOT,
    PRICE_OI_PATTERN
)


# ============================================================
# FIND PREVIOUS EOD REPORT
# ============================================================

def extract_report_date(filename):

    match = re.search(
        r"Report_(\d{4}-\d{2}-\d{2})",
        filename
    )

    if match:

        return datetime.strptime(
            match.group(1),
            "%Y-%m-%d"
        ).date()

    return None



def find_previous_eod_report(trading_date):

    if isinstance(trading_date, str):

        trading_date = datetime.strptime(
            trading_date,
            "%Y-%m-%d"
        ).date()


    reports = []


    for file in EOD_ROOT.rglob(
        PRICE_OI_PATTERN
    ):

        report_date = extract_report_date(
            file.name
        )


        if report_date and report_date < trading_date:

            reports.append(
                (
                    report_date,
                    file
                )
            )


    if not reports:

        raise FileNotFoundError(
            "No previous EOD report found"
        )


    reports.sort(
        key=lambda x: x[0],
        reverse=True
    )


    return reports[0][1]



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


    df = pd.read_excel(
        report
    )


    mapping = {

        "Symbol":
            "Symbol",

        "Open":
            "Previous_Open",

        "High":
            "Previous_High",

        "Low":
            "Previous_Low",

        "Close":
            "Previous_Close",

        "OI":
            "Previous_OI",

        "OI Chg (%)":
            "Previous_OI_Chg_%",

        "PCR":
            "Previous_PCR",

        "IV":
            "Previous_IV",

        "BuildUp":
            "Previous_BuildUp"

    }


    output = pd.DataFrame()


    for source, target in mapping.items():

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
        "2026-07-24"
    )


    print()

    print(
        context.head()
    )