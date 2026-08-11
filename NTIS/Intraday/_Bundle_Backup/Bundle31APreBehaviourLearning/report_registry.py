"""
=========================================================
NTIS Intraday - report_registry.py
Version : 1.0.0
=========================================================

Purpose:
    Register every screenshot discovered by file_manager.py.

    This module DOES NOT perform OCR.

    It simply builds a registry of all images that will
    move through the OCR pipeline.

=========================================================
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List
import pandas as pd

from file_manager import FileManager
from intraday_config import output_path


# =========================================================
# Registry Object
# =========================================================

@dataclass
class ReportRecord:

    screen: str
    image_name: str
    image_path: str
    report_type: str
    status: str


# =========================================================
# Report Registry
# =========================================================

class ReportRegistry:

    def __init__(self):

        self.fm = FileManager()

        self.records: List[ReportRecord] = []


    # -----------------------------------------------------
    # Build Registry
    # -----------------------------------------------------

    def build(self):

        images = self.fm.get_images()

        for image in images:

            try:
                screen = image.parent.name

            except Exception:
                screen = "UNKNOWN"

            self.records.append(

                ReportRecord(

                    screen=screen,

                    image_name=image.name,

                    image_path=str(image),

                    report_type="UNKNOWN",

                    status="PENDING"

                )

            )


    # -----------------------------------------------------
    # DataFrame
    # -----------------------------------------------------

    def dataframe(self):

        return pd.DataFrame(

            [

                {

                    "Screen": r.screen,

                    "Image": r.image_name,

                    "Image Path": r.image_path,

                    "Report Type": r.report_type,

                    "Status": r.status

                }

                for r in self.records

            ]

        )


    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    def save(self):

        df = self.dataframe()

        outfile = output_path() / "report_registry.csv"

        df.to_csv(

            outfile,

            index=False

        )

        return outfile


    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    def summary(self):

        df = self.dataframe()

        print()

        print("=" * 70)

        print("NTIS REPORT REGISTRY")

        print("=" * 70)

        print(df)

        print()

        print("Total Images :", len(df))

        print()

        outfile = self.save()

        print("Registry Saved :")

        print(outfile)

        print("=" * 70)


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    registry = ReportRegistry()

    registry.build()

    registry.summary()