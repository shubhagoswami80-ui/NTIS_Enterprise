"""
=========================================================
NTIS Intraday Pattern Engine
Version : 1.1

Purpose:
    Convert intraday scores and market behaviour
    into trading patterns.

Input:
    intraday_scored_stocks.csv

Output:
    intraday_pattern_analysis.csv

Update:
    Uses central dynamic Intraday output path.
=========================================================
"""

from pathlib import Path
import hashlib
import pandas as pd

from intraday_path_config import get_today_output


OUTPUT_FOLDER = get_today_output()


INPUT_FILE = (
    OUTPUT_FOLDER
    /
    "intraday_scored_stocks.csv"
)


OUTPUT_FILE = (
    OUTPUT_FOLDER
    /
    "intraday_pattern_analysis.csv"
)


class IntradayPatternEngine:


    def identify_pattern(self, row):

        price = row.get("Price Chg %")
        oi = row.get("OI Chg %")
        fut = str(row.get("Fut Buildup"))
        volume = row.get("Volume Chg %")


        if pd.notna(price) and pd.notna(oi):

            if price > 0 and oi > 0:
                return "Fresh Long Buildup"

            if price < 0 and oi > 0:
                return "Short Buildup"

            if price > 0 and oi < 0:
                return "Short Covering"

            if price < 0 and oi < 0:
                return "Long Unwinding"


        if pd.notna(volume) and volume > 100:
            return "Volume Expansion"


        if "long" in fut.lower():
            return "Futures Long Setup"


        if "short" in fut.lower():
            return "Futures Short Setup"


        return "Neutral"





    def _normalize_score(self, score):
        try:
            val = float(score)
        except Exception:
            return "MID"
        if val >= 70:
            return "HIGH"
        elif val < 30:
            return "LOW"
        return "MID"

    def _normalize_pct(self, val):
        try:
            v = float(val)
        except Exception:
            return "NEUTRAL"
        if v > 1.0:
            return "POS"
        elif v < -1.0:
            return "NEG"
        return "NEUTRAL"

    def build_pattern_dna(self, row):
        """
        Bundle 01 foundation:
        Generates a deterministic Pattern DNA string for downstream
        Pattern Library and Historical Evidence modules using normalized behavioural buckets.
        """
        score_bucket = self._normalize_score(row.get("NTIS Score", row.get("NTIS_Score", 0)))
        price_bucket = self._normalize_pct(row.get("Price Chg %", row.get("Price_Chg_%", 0)))
        oi_bucket = self._normalize_pct(row.get("OI Chg %", row.get("OI_Chg_%", 0)))
        vol_bucket = self._normalize_pct(row.get("Volume Chg %", row.get("Volume_Chg_%", 0)))

        fields=[
            ("PAT", row.get("Pattern","")),
            ("SCR", score_bucket),
            ("P", price_bucket),
            ("OI", oi_bucket),
            ("VOL", vol_bucket),
            ("FUT", row.get("Fut Buildup","")),
        ]
        return "|".join(f"{k}:{v}" for k,v in fields)


    def build_pattern_id(self, row):
        """Create a stable Pattern_ID from Pattern_DNA."""
        dna = str(row.get("Pattern_DNA",""))
        digest = hashlib.sha1(dna.encode("utf-8")).hexdigest()[:8].upper()
        return f"PDNA_{digest}"

    def run(self):

        df = pd.read_csv(
            INPUT_FILE
        )


        df["Pattern"] = df.apply(
            self.identify_pattern,
            axis=1
        )
        df["Pattern_DNA"] = df.apply(
            self.build_pattern_dna,
            axis=1
        )
        df["Pattern_ID"] = df.apply(
            self.build_pattern_id,
            axis=1
        )


        df.to_csv(
            OUTPUT_FILE,
            index=False
        )


        return OUTPUT_FILE



if __name__ == "__main__":


    result = (
        IntradayPatternEngine()
        .run()
    )


    print("=" * 60)
    print("INTRADAY PATTERN ANALYSIS COMPLETE")
    print(result)
    print("=" * 60)