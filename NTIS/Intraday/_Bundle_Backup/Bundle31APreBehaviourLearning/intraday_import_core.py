from pathlib import Path
from datetime import datetime
import logging

try:
    from intraday_config import SCREENSHOT_ROOT
    from intraday_path_config import get_today_output

except Exception:

    SCREENSHOT_ROOT = Path(
        r"D:\My-data\Share_P&L\Ichart Data\Screenshot"
    )

    def get_today_output():

        now = datetime.now()

        return (
            Path(r"E:\NSE_Daily_Analysis\Intraday\Output")
            / str(now.year)
            / now.strftime("%B")
            / now.strftime("%Y-%m-%d")
        )


logging.basicConfig(
    level=logging.INFO
)

LOGGER = logging.getLogger(
    "NTIS_INTRADAY"
)


class IntradayImportCore:

    def __init__(self):

        now = datetime.now()

        self.source = (
            SCREENSHOT_ROOT
            / (
                now.strftime('%B').lower()
                +
                now.strftime('%y')
            )
            /
            now.strftime('%Y-%m-%d')
        )


        # Dynamic NTIS Intraday output structure
        #
        # Output
        #   └── YYYY
        #        └── Month
        #             └── Trading Date

        self.output = get_today_output()


        self.output.mkdir(
            parents=True,
            exist_ok=True
        )


    def discover_excel_files(self):

        return [
            f
            for f in self.source.rglob('*')
            if f.suffix.lower()
            in [
                '.xls',
                '.xlsx'
            ]
        ]