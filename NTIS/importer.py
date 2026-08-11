"""
=========================================================
NTIS Importer
Version : 3.1

Purpose:
- Read latest NSE report from all folders
- Handle different Excel formats
- Store trading dates
- Validate report dates
=========================================================
"""


import pandas as pd


from config import (
    DAILY_REPORTS,
    OUTPUT,
    REPORT_FOLDERS
)


from utils import (
    get_latest_file,
    extract_report_date,
    format_date
)


from validator import validate_trading_dates


def find_latest_common_trading_date():

    common_dates = None

    for report_key in REPORT_FOLDERS.keys():

        folder = DAILY_REPORTS / REPORT_FOLDERS[report_key]

        if not folder.exists():

            return None

        dates = {
            extract_report_date(file.name)
            for file in folder.glob("*.xlsx")
            if extract_report_date(file.name) is not None
        }

        if not dates:

            return None

        if common_dates is None:

            common_dates = dates

        else:

            common_dates &= dates

        if not common_dates:

            return None

    return max(common_dates) if common_dates else None


# ==========================================================
# Read Latest Report
# ==========================================================

def read_latest_report(report_key, trading_date=None):


    folder = DAILY_REPORTS / REPORT_FOLDERS[report_key]


    print("\n" + "=" * 70)
    print(f"Reading : {report_key}")
    print("=" * 70)



    if not folder.exists():

        print("Folder not found")
        return None



    files = list(
        folder.glob("*.xlsx")
    )



    if not files:

        print("No Excel files found")
        return None



    # -----------------------------------------
    # Select latest report by date
    # -----------------------------------------

    if trading_date is None:

        latest_file = get_latest_file(folder)

    else:

        matching_files = [
            file
            for file in files
            if extract_report_date(file.name) == trading_date
        ]

        if not matching_files:

            print(
                f"No report found for trading date : {format_date(trading_date)}"
            )
            return None

        latest_file = sorted(matching_files, key=lambda item: item.name)[-1]


    report_date = extract_report_date(
        latest_file.name
    )



    print(f"Folder       : {folder}")
    print(f"Files Found  : {len(files)}")
    print(f"Latest File  : {latest_file.name}")
    print(f"Trading Date : {format_date(report_date)}")




    # -----------------------------------------
    # Read Excel
    # -----------------------------------------

    if report_key == "ivr_ivp":


        df = pd.read_excel(
            latest_file,
            header=1
        )


    else:


        df = pd.read_excel(
            latest_file
        )




    # -----------------------------------------
    # Attach metadata
    # -----------------------------------------

    df.attrs["Trading Date"] = format_date(report_date)



    print(f"Rows         : {df.shape[0]}")
    print(f"Columns      : {df.shape[1]}")



    print("\nColumn Names")
    print("-" * 40)


    for col in df.columns:

        print(col)



    print("\nFirst 5 Records")
    print("-" * 40)


    print(df.head())



    return df





# ==========================================================
# Main Loader
# ==========================================================

def load_market_reports(trading_date=None):


    dataframes = {}


    if trading_date is None:

        trading_date = find_latest_common_trading_date()

        if trading_date is not None:

            print(
                f"Using latest common trading date : {format_date(trading_date)}"
            )

        else:

            print(
                "No common trading date found across all reports. "
                "Loading latest available files per report."
            )

    date_file = OUTPUT / "current_trading_date.txt"

    if trading_date is not None:

        OUTPUT.mkdir(parents=True, exist_ok=True)
        date_file.write_text(
            trading_date.strftime("%Y-%m-%d"),
            encoding="utf-8"
        )

    elif date_file.exists():

        date_file.unlink()


    for report in REPORT_FOLDERS.keys():


        df = read_latest_report(report, trading_date=trading_date)



        if df is not None:

            dataframes[report] = df




    return dataframes





# ==========================================================
# Main
# ==========================================================

def main():


    print("=" * 70)
    print("NTIS IMPORTER")
    print("=" * 70)



    dataframes = load_market_reports()




    print("\n")
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)



    for report, df in dataframes.items():


        print(
            f"{report:<15} : "
            f"{len(df)} rows | "
            f"Date : {df.attrs.get('Trading Date')}"
        )




    print("\nAll reports loaded successfully.")




    # -----------------------------------------
    # Date Validation
    # -----------------------------------------

    validation = validate_trading_dates(
        dataframes
    )



    if not validation:

        print("\nNTIS STATUS : STOPPED")
        print("Please correct report dates before analysis.")

        raise RuntimeError(
              "Trading date validation failed. "
              "All EOD reports must belong to the same trading date."
        )

    print("\nNTIS STATUS : READY")
    print("Data is safe for analysis.")



    return dataframes





if __name__ == "__main__":

    main()