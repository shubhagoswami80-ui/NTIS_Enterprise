"""
=========================================================
NTIS Intraday - image_loader.py
Version : 1.0.0
=========================================================

Purpose
-------
Loads images from report_registry.csv in processing order.

This module DOES NOT perform OCR.

It only:

1. Reads report_registry.csv
2. Opens every image
3. Validates image
4. Returns image object
5. Ready for OCR Engine

=========================================================
"""

from pathlib import Path

import cv2
import pandas as pd

from intraday_config import output_path


# =========================================================
# Image Loader
# =========================================================

class ImageLoader:

    def __init__(self):

        self.registry_file = output_path() / "report_registry.csv"

        if not self.registry_file.exists():

            raise FileNotFoundError(

                f"\nRegistry not found\n{self.registry_file}"

            )

        self.df = pd.read_csv(self.registry_file)

        self.total = len(self.df)


    # -----------------------------------------------------
    # Generator
    # -----------------------------------------------------

    def load_images(self):

        for index, row in self.df.iterrows():

            image_path = Path(row["Image Path"])

            if not image_path.exists():

                print(

                    f"[MISSING] {image_path}"

                )

                continue

            image = cv2.imread(str(image_path))

            if image is None:

                print(

                    f"[INVALID] {image_path}"

                )

                continue

            yield {

                "index": index + 1,

                "total": self.total,

                "screen": row["Screen"],

                "image_name": row["Image"],

                "image_path": image_path,

                "report_type": row["Report Type"],

                "status": row["Status"],

                "image": image

            }


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    loader = ImageLoader()

    print()

    print("=" * 70)

    print("NTIS IMAGE LOADER")

    print("=" * 70)

    count = 0

    for item in loader.load_images():

        count += 1

        print(

            f"[{item['index']:03d}/{item['total']}] "

            f"{item['screen']}  "

            f"{item['image_name']}"

        )

    print()

    print("Images Loaded :", count)

    print("=" * 70)