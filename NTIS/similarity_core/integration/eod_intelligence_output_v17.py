"""
EOD Intelligence Output V17

Prepares final intelligence output dataframe.
"""

import pandas as pd


class EODIntelligenceOutputV17:

    def generate(self, df):

        if df.empty:
            return df

        output_columns = [
            "Symbol",
            "Swing Bias",
            "Confidence",
            "Swing Score",
            "Swing Signal",
            "Confidence Level",
            "Swing Setup",
            "Swing Intelligence"
        ]

        available = [
            c for c in output_columns
            if c in df.columns
        ]

        return df[available].copy()
