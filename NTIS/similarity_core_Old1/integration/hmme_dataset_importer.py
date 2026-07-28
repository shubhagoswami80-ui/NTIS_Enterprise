from pathlib import Path
import pandas as pd


class HMMEDatasetImporter:

    def __init__(self):
        self.input_dir = Path(
            "E:/NSE_Daily_Analysis/Database"
        )

    def import_file(self, filename):

        file_path = self.input_dir / filename

        if not file_path.exists():
            return pd.DataFrame()

        if file_path.suffix.lower() in [".xlsx", ".xls"]:
            return pd.read_excel(file_path)

        return pd.read_csv(file_path)
