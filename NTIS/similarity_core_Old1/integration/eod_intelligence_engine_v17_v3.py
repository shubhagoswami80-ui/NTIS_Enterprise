"""
EOD Intelligence Engine V17 V3
Dynamic date resolver integration
"""

from pathlib import Path
import pandas as pd

from .eod_date_resolver_v17 import EODDateResolverV17


class EODIntelligenceEngineV17:

    def __init__(self, data_path=None):
        self.data_path = data_path

    def latest_file(self):

        resolver = EODDateResolverV17(self.data_path)
        result = resolver.get_latest_report()

        if result:
            return result[1]

        return None

    def analyze_file(self):

        file = self.latest_file()

        if file is None:
            return pd.DataFrame()

        df = pd.read_excel(file)

        df["Price Intelligence"] = "NEUTRAL"
        df["OI Intelligence"] = "NEUTRAL"

        if "Price Chg %" in df.columns:
            df.loc[df["Price Chg %"] > 0, "Price Intelligence"] = "POSITIVE"
            df.loc[df["Price Chg %"] < 0, "Price Intelligence"] = "NEGATIVE"

        if "OI Chg %" in df.columns and "Price Chg %" in df.columns:
            df.loc[
                (df["Price Chg %"] > 0) &
                (df["OI Chg %"] > 0),
                "OI Intelligence"
            ] = "LONG_BUILDUP"

            df.loc[
                (df["Price Chg %"] < 0) &
                (df["OI Chg %"] > 0),
                "OI Intelligence"
            ] = "SHORT_BUILDUP"

        df["Swing Intelligence"] = (
            df["Price Intelligence"]
            + "_"
            + df["OI Intelligence"]
        )

        return df
