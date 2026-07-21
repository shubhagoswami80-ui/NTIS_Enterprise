"""
HMME-19 Feature Engineering
"""

import pandas as pd


class FeatureEngineering:

    def build_features(self, data):
        df = data.copy()

        if isinstance(df, pd.DataFrame):
            df.columns = [c.strip() for c in df.columns]

        return df
