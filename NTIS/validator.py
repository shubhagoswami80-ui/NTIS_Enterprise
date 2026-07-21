"""
=========================================================
NTIS Trading Date Validator
Version : 1.0
=========================================================
"""



def validate_trading_dates(dataframes):

    print("\n")
    print("=" * 70)
    print("TRADING DATE VALIDATION")
    print("=" * 70)


    dates = {}


    for name, df in dataframes.items():

        report_date = df.attrs.get(
            "Trading Date"
        )

        dates[name] = report_date



    print("\nDetected Dates")
    print("-" * 40)


    for report, date in dates.items():

        print(
            f"{report:<15} : {date}"
        )


    unique_dates = set(
        dates.values()
    )


    print()


    if len(unique_dates) == 1:

        print("STATUS : PASS")
        print(
            "All reports belong to same trading date."
        )

        return True


    else:

        print("STATUS : FAILED")
        print(
            "Different trading dates detected."
        )

        return False