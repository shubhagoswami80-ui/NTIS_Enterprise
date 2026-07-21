"""
HMME-15 Data Validator
"""
from pathlib import Path
import pandas as pd

class HMMEDataValidator:

    def validate_file(self, file_path):
        return Path(file_path).exists()

    def validate_dataframe(self, df):
        return isinstance(df, pd.DataFrame) and not df.empty
