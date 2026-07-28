"""
HMME V1.7 Master Dataset Builder

Purpose:
Combine NTIS EOD source reports into one master dataset.

Sources:
01_Price_OI
02_Volume_OI_Spikes
03_Support_OI
04_Resistance_OI
05_IVR_IVP

This version creates the foundation only.
Advanced feature engineering remains separate.
"""

from pathlib import Path
import pandas as pd


class HMMEMasterDatasetBuilderV17:

    def __init__(self, base_path):
        self.base_path = Path(base_path)

    def load_price_oi(self, folder):

        files = list(Path(folder).glob("*.xlsx"))

        frames = []

        for f in files:
            df = pd.read_excel(f)

            if "Symbol" in df.columns:
                frames.append(df)

        if not frames:
            return pd.DataFrame()

        return pd.concat(
            frames,
            ignore_index=True
        )

    def build(self, folders):

        price_df = self.load_price_oi(
            folders.get("price_oi")
        )

        if price_df.empty:
            return pd.DataFrame()

        master = price_df.copy()

        # Future merge points:
        # Volume
        # Support
        # Resistance
        # IVR_IVP

        return master
