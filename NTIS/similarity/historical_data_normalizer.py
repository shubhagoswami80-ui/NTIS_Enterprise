"""
HMME-18 Historical Data Normalizer
"""

import pandas as pd


class HistoricalDataNormalizer:

    def normalize(self, data):
        df = data.copy()
        df.columns = [c.strip() for c in df.columns]
        return df
