import os
import zipfile
from datetime import datetime
import pandas as pd
from openpyxl.worksheet.datavalidation import DataValidation

LOG_FOLDER = r"D:\My-data\Share_P&L\ytdata"


def load_target_data(formatted_date):
    """Loads target date data, checking for standard CSV first, then a ZIP container."""
    csv_file = f"nse_log_{formatted_date}.csv"
    zip_file = f"nse_log_{formatted_date}.zip"

    csv_path = os.path.join(LOG_FOLDER, csv_file)
    zip_path = os.path.join(LOG_FOLDER, zip_file)

    if os.path.exists(csv_path):
        print(f"📖 Streaming data from raw uncompressed log...")
        return pd.read_csv(csv_path)
    elif os.path.exists(zip_path):
        print(f"📖 Streaming data safely from compressed ZIP file package...")
        with zipfile.ZipFile(zip_path, "r") as archive:
            with archive.open(csv_file) as f:
                return pd.read_csv(f)
    return None


def generate_excel_report():
    target_date = input(
        "\n📅 Enter target date (YYYY-MM-DD) or press ENTER for today: "
    ).strip()
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    clean_date = target_date.replace("-", "").replace("/", "")
    formatted_date = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:]}"

    raw_df = load_target_data(formatted_date)

    if raw_df is None or raw_df.empty:
        print(f"❌ Error: No matching historical files found for: {formatted_date}")
        return

    print(f"⚙ Parsing parameters and calculating metrics rules...")
    processed_df = raw_df.copy()

    # Calculate Skew Bias %
    processed_df["Bias_%"] = processed_df.apply(
        lambda row: (
            round(
                (
                    (row["ce_volume_change"] - row["pe_volume_change"])
                    / (row["ce_volume_change"] + row["pe_volume_change"])
                )
                * 100,
                2,
            )
            if (row["ce_volume_change"] + row["pe_volume_change"]) > 0
            else 0.0
        ),
        axis=1,
    )

    processed_df["Skew"] = processed_df["Bias_%"].apply(
        lambda x: "Bullish Skew" if x > 0 else ("Bearish Skew" if x < 0 else "Neutral")
    )

    def determine_signal(bias):
        abs_bias = abs(bias)
        if abs_bias >= 20:
            return "BROKE (confirmed)"
        elif abs_bias >= 15:
            return "BROKE (immediate)"
        return "Normal Straddle"

    processed_df["Event_Status"] = processed_df["Bias_%"].apply(determine_signal)

    output_filename = f"NSE_Processed_Report_{formatted_date}.xlsx"

    # ==============================================================================
    # 📊 EXCEL COMPILER & DASHBOARD INTERACTIVE DESIGN WORKSPACE
    # ==============================================================================
    with pd.ExcelWriter(output_filename, engine="openpyxl") as writer:
        processed_df.to_excel(writer, sheet_name="Processed_Data", index=False)
        raw_df.to_excel(writer, sheet_name="Raw_Logs", index=False)

        # Create a clean Interactive Control Board Sheet
        workbook = writer.book
        dashboard = workbook.create_sheet(title="Interactive_Dashboard", index=0)

        # Build Dashboard UI headers
        dashboard["A1"] = "🎯 SIGNAL STRADDLE DROP-DOWN FILTER"
        dashboard["A1"].font = pd.io.excel._openpyxl.Workbook().act_sheet_name = (
            "Arial"
        )
        dashboard["A3"] = "Select Signal Status Filter 👉"
        dashboard["B3"] = "BROKE (confirmed)"  # Default value

        dashboard["A5"] = "Timestamp"
        dashboard["B5"] = "Ticker Symbol"
        dashboard["C5"] = "Expiry"
        dashboard["D5"] = "CE Vol Change"
        dashboard["E5"] = "PE Vol Change"
        dashboard["F5"] = "Bias %"
        dashboard["G5"] = "Event Status"

        # Apply drop-down list verification arrays onto column grid cell B3
        dv = DataValidation(
            type="list",
            formula1='"BROKE (confirmed),BROKE (immediate),Normal Straddle"',
            allow_blank=True,
        )
        dashboard.add_data_validation(dv)
        dv.add(dashboard["B3"])

        # Inject Excel matrix formulas dynamically to auto-filter based on cell B3 selection
        # Displays matching records from 'Processed_Data' instantly
        for i in range(6, 150):
            dashboard[f"A{i}"] = (
                f'=IFERROR(INDEX(Processed_Data!A:A, SMALL(IF(Processed_Data!$K:$K=$B$3, ROW(Processed_Data!$K:$K)), ROW({f"A{i-5}"}))), "")'
            )
            dashboard[f"B{i}"] = (
                f'=IFERROR(INDEX(Processed_Data!B:B, SMALL(IF(Processed_Data!$K:$K=$B$3, ROW(Processed_Data!$K:$K)), ROW({f"A{i-5}"}))), "")'
            )
            dashboard[f"C{i}"] = (
                f'=IFERROR(INDEX(Processed_Data!C:C, SMALL(IF(Processed_Data!$K:$K=$B$3, ROW(Processed_Data!$K:$K)), ROW({f"A{i-5}"}))), "")'
            )
            dashboard[f"D{i}"] = (
                f'=IFERROR(INDEX(Processed_Data!E:E, SMALL(IF(Processed_Data!$K:$K=$B$3, ROW(Processed_Data!$K:$K)), ROW({f"A{i-5}"}))), "")'
            )
            dashboard[f"E{i}"] = (
                f'=IFERROR(INDEX(Processed_Data!G:G, SMALL(IF(Processed_Data!$K:$K=$B$3, ROW(Processed_Data!$K:$K)), ROW({f"A{i-5}"}))), "")'
            )
            dashboard[f"F{i}"] = (
                f'=IFERROR(INDEX(Processed_Data!L:L, SMALL(IF(Processed_Data!$K:$K=$B$3, ROW(Processed_Data!$K:$K)), ROW({f"A{i-5}"}))), "")'
            )
            dashboard[f"G{i}"] = (
                f'=IFERROR(INDEX(Processed_Data!K:K, SMALL(IF(Processed_Data!$K:$K=$B$3, ROW(Processed_Data!$K:$K)), ROW({f"A{i-5}"}))), "")'
            )

    print(f"🎉 Fully Interactive Excel Report Workbook compiled successfully!")
    print(f"👉 File location workspace: {output_filename}")


if __name__ == "__main__":
    generate_excel_report()
