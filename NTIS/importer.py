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
    REPORT_FOLDERS
)


from utils import (
    get_latest_file,
    extract_report_date,
    format_date
)


from validator import validate_trading_dates



# ==========================================================
# Read Latest Report
# ==========================================================

def read_latest_report(report_key):


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

    latest_file = get_latest_file(folder)



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

def load_market_reports():


    dataframes = {}



    for report in REPORT_FOLDERS.keys():


        df = read_latest_report(report)



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



    if validation:


        print("\nNTIS STATUS : READY")
        print("Data is safe for analysis.")



    else:


        print("\nNTIS STATUS : STOPPED")
        print("Please correct report dates before analysis.")




    return dataframes





if __name__ == "__main__":

    main()