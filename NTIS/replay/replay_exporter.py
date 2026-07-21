"""
=========================================================
NTIS Replay Exporter
Version : 1.0
Purpose :
    Export Replay Results to various formats
=========================================================
"""

from pathlib import Path

import pandas as pd


class ReplayExporter:

    @staticmethod
    def to_csv(df, output_file):

        output_file = Path(output_file)
        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        df.to_csv(
            output_file,
            index=False
        )

    @staticmethod
    def to_excel(df, output_file, sheet_name="Replay"):

        output_file = Path(output_file)
        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with pd.ExcelWriter(output_file) as writer:
            df.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False
            )

    @staticmethod
    def summary_to_excel(summary, output_file):

        output_file = Path(output_file)
        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        pd.DataFrame([summary]).to_excel(
            output_file,
            index=False
        )