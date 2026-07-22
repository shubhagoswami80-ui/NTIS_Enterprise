"""
NTIS Intraday Current Report Importer
Runner

Connects:
- intraday_import_core.py
- intraday_report_parser.py
- intraday_snapshot_manager.py
- intraday_output_writer.py

Intraday pipeline only.
"""

from intraday_import_core import IntradayImportCore
from intraday_report_parser import IntradayReportParser
from intraday_snapshot_manager import SnapshotManager
from intraday_output_writer import IntradayOutputWriter


def main():

    print("=" * 70)
    print("NTIS INTRADAY CURRENT REPORT IMPORTER")
    print("=" * 70)

    core = IntradayImportCore()
    parser = IntradayReportParser()
    snapshot = SnapshotManager()
    writer = IntradayOutputWriter()

    files = core.discover_excel_files()

    print("Excel files found:", len(files))

    records = []

    for file in files:
        try:
            report_type = parser.detect_report_type(file.name)
            df = parser.load_excel(file)

            records.append({
                "File": file.name,
                "Path": str(file),
                "Report Type": report_type,
                "Rows": len(df),
                "Status": "SUCCESS"
            })

            print(f"OK : {file.name} -> {report_type}")

        except Exception as exc:
            records.append({
                "File": file.name,
                "Path": str(file),
                "Report Type": "UNKNOWN",
                "Rows": 0,
                "Status": str(exc)
            })

    snapshot.save(records, core.output)
    writer.write(records, core.output)

    print("=" * 70)
    print("IMPORT COMPLETED")
    print("Output:", core.output)
    print("=" * 70)


if __name__ == "__main__":
    main()
