"""
=========================================================
NTIS Intraday OCR Engine
Version : 1.0.0

Purpose
    Load images from Image Loader
    Perform OCR
    Save OCR text files

Output
    Intraday/
        Output/
            YYYY/
                Month/
                    YYYY-MM-DD/
                        OCR/
                            *.txt
=========================================================
"""

from pathlib import Path
import logging
import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
from image_loader import ImageLoader
from intraday_config import output_path


class OCREngine:

    def __init__(self):

        self.loader = ImageLoader()

        self.output_dir = output_path() / "OCR"

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    def extract_text(self):

        total = 0

        for item in self.loader.load_images():

            image = item["image"]

            text = pytesseract.image_to_string(
                image,
                lang="eng"
            )

            outfile = (
                self.output_dir /
                f"{Path(item['image_name']).stem}.txt"
            )

            outfile.write_text(
                text,
                encoding="utf-8"
            )

            total += 1

            yield {
                "screen": item["screen"],
                "image": item["image_name"],
                "text_file": outfile,
                "characters": len(text)
            }

        logging.info("OCR Completed : %s Images", total)


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s"
    )

    engine = OCREngine()

    print("=" * 70)
    print("NTIS OCR ENGINE")
    print("=" * 70)

    count = 0

    for result in engine.extract_text():

        count += 1

        print(
            f"[{count:03d}] "
            f"{result['screen']}  "
            f"{result['image']}  "
            f"{result['characters']} chars"
        )

    print()
    print("=" * 70)
    print("OCR Files Created :", count)
    print("Output Folder")
    print(engine.output_dir)
    print("=" * 70)