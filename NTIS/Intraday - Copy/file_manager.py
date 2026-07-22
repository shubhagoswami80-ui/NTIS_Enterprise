"""
=========================================================
NTIS Intraday - file_manager.py
Version : 1.1.0
=========================================================
"""

from pathlib import Path
from typing import List
import logging

from intraday_config import (
    SCREENSHOT_ROOT,
    processing_datetime,
    month_folder,
    trading_day_folder,
)

SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tif",
    ".tiff",
}


class FileManager:
    def __init__(self):

        self.dt = processing_datetime()

        self.month_path = SCREENSHOT_ROOT / month_folder(self.dt)

        self.day_path = self.month_path / trading_day_folder(self.dt)

    def validate(self):

        if not self.month_path.exists():
            raise FileNotFoundError(
                f"\nMonth folder not found\n{self.month_path}"
            )

        if not self.day_path.exists():
            raise FileNotFoundError(
                f"\nTrading Day folder not found\n{self.day_path}"
            )

    def get_images(self) -> List[Path]:

        self.validate()

        images = []

        print("\nSearching recursively from:")
        print(self.day_path)
        print()

        for file in self.day_path.rglob("*"):

            if file.is_file():
                print(file)

            if (
                file.is_file()
                and file.suffix.lower() in SUPPORTED_EXTENSIONS
            ):
                images.append(file)

        images.sort(
            key=lambda x: (
                str(x.parent).lower(),
                x.name.lower()
            )
        )

        logging.info("Images Found : %s", len(images))

        return images

    def summary(self):

        images = self.get_images()

        print("\n" + "=" * 60)
        print("NTIS Intraday File Manager")
        print("Version         : 1.1.0")
        print("=" * 60)

        print("SCREENSHOT ROOT :", SCREENSHOT_ROOT)
        print("MONTH FOLDER    :", self.month_path)
        print("TRADING DAY     :", self.day_path)
        print("TOTAL IMAGES    :", len(images))

        print("-" * 60)

        for i, img in enumerate(images, 1):

            print(
                f"{i:03d}. "
                f"{img.relative_to(self.day_path)}"
            )

        print("=" * 60)


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    fm = FileManager()

    fm.summary()