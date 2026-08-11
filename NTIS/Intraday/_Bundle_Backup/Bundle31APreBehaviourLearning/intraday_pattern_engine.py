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


    # =========================================================
    # BEHAVIOUR LEARNING ENGINE v2: CENTRALIZED BEHAVIOUR NORMALIZATION
    # =========================================================

    @staticmethod
    def normalize_price_behavior(price_chg):
        try:
            val = float(price_chg)
        except Exception:
            return "PRICE_NEUTRAL"
        if val >= 2.0:
            return "STRONG_UPTREND"
        elif val > 0.5:
            return "MILD_UPTREND"
        elif val <= -2.0:
            return "STRONG_DOWNTREND"
        elif val < -0.5:
            return "MILD_DOWNTREND"
        return "PRICE_CONSOLIDATION"

    @staticmethod
    def normalize_oi_behavior(oi_chg):
        try:
            val = float(oi_chg)
        except Exception:
            return "OI_NEUTRAL"
        if val >= 1.5:
            return "LONG_ACCUMULATION_BUILDUP"
        elif val <= -1.5:
            return "LONG_UNWINDING_OR_SHORT_COVERING"
        return "OI_STABLE"

    @staticmethod
    def normalize_volume_behavior(vol_chg):
        try:
            val = float(vol_chg)
        except Exception:
            return "VOLUME_NORMAL"
        if val >= 100.0:
            return "VOLUME_SURGE"
        elif val >= 50.0:
            return "VOLUME_EXPANSION"
        elif val <= -50.0:
            return "VOLUME_CONTRACTION"
        return "VOLUME_NORMAL"

    @staticmethod
    def normalize_pcr_behavior(pcr):
        try:
            val = float(pcr)
        except Exception:
            return "PCR_NEUTRAL"
        if val >= 1.3:
            return "BULLISH_SUPPORT"
        elif val <= 0.7:
            return "BEARISH_RESISTANCE"
        return "PCR_NEUTRAL"

    @staticmethod
    def normalize_iv_behavior(iv_val):
        try:
            val = float(iv_val)
        except Exception:
            return "VOLATILITY_NORMAL"
        if val >= 80.0:
            return "HIGH_VOLATILITY_REGIME"
        elif val <= 20.0:
            return "LOW_VOLATILITY_REGIME"
        return "VOLATILITY_NORMAL"

    @staticmethod
    def normalize_score_behavior(score):
        try:
            val = float(score)
        except Exception:
            return "SCORE_NEUTRAL"
        if val >= 75.0:
            return "HIGH_CONVICTION_BULLISH"
        elif val >= 60.0:
            return "MODERATE_BULLISH"
        elif val <= 25.0:
            return "HIGH_CONVICTION_BEARISH"
        elif val <= 40.0:
            return "MODERATE_BEARISH"
        return "SCORE_NEUTRAL"

    def normalize_row_behaviors(self, row):
        return {
            "Price_Behavior": self.normalize_price_behavior(row.get("Price Chg %", row.get("Price_Chg_%"))),
            "OI_Behavior": self.normalize_oi_behavior(row.get("OI Chg %", row.get("OI_Chg_%"))),
            "Volume_Behavior": self.normalize_volume_behavior(row.get("Volume Chg %", row.get("Volume_Chg_%"))),
            "PCR_Behavior": self.normalize_pcr_behavior(row.get("PCR", row.get("Put_Call_Ratio"))),
            "IV_Behavior": self.normalize_iv_behavior(row.get("IVR", row.get("IV_Rank", row.get("IV")))),
            "Score_Behavior": self.normalize_score_behavior(row.get("NTIS Score", row.get("NTIS_Score")))
        }


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





    def build_pattern_dna(self, row):
        """
        Bundle 01 foundation:
        Generates a deterministic Pattern DNA string for downstream
        Pattern Library and Historical Evidence modules.
        """
        fields=[
            ("PAT", row.get("Pattern","")),
            ("SCR", row.get("NTIS Score","")),
            ("P", row.get("Price Chg %","")),
            ("OI", row.get("OI Chg %","")),
            ("VOL", row.get("Volume Chg %","")),
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