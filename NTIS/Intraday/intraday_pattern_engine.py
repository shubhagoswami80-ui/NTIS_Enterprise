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
from intraday_config import (
    PRICE_BEHAVIOUR_BANDS,
    OI_BEHAVIOUR_BANDS,
    VOLUME_BEHAVIOUR_BANDS,
    PCR_BEHAVIOUR_BANDS,
    IV_BEHAVIOUR_BANDS,
    SCORE_BEHAVIOUR_BANDS,
    NORMALIZATION_VERSION,
    PDNA_VERSION,
    PDNA_FIELD_ORDER,
)


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
    def normalize_price(price_chg):
        try:
            val = float(price_chg)
        except Exception:
            return "PRICE_NEUTRAL"
        if val >= PRICE_BEHAVIOUR_BANDS["STRONG_UP"]:
            return "PRICE_STRONG_UP"
        elif val > PRICE_BEHAVIOUR_BANDS["UP"]:
            return "PRICE_UP"
        elif val <= PRICE_BEHAVIOUR_BANDS["STRONG_DOWN"]:
            return "PRICE_STRONG_DOWN"
        elif val < PRICE_BEHAVIOUR_BANDS["DOWN"]:
            return "PRICE_DOWN"
        return "PRICE_NEUTRAL"

    @staticmethod
    def normalize_oi(oi_chg):
        try:
            val = float(oi_chg)
        except Exception:
            return "OI_NEUTRAL"
        if val >= OI_BEHAVIOUR_BANDS["STRONG_ACCUMULATION"]:
            return "OI_ACCUMULATION"
        elif val <= OI_BEHAVIOUR_BANDS["STRONG_LIQUIDATION"]:
            return "OI_LIQUIDATION"
        return "OI_NEUTRAL"

    @staticmethod
    def normalize_volume(vol_chg):
        try:
            val = float(vol_chg)
        except Exception:
            return "VOLUME_NORMAL"
        if val >= VOLUME_BEHAVIOUR_BANDS["SURGE"]:
            return "VOLUME_SURGE"
        elif val >= VOLUME_BEHAVIOUR_BANDS["EXPANSION"]:
            return "VOLUME_EXPANSION"
        elif val <= VOLUME_BEHAVIOUR_BANDS["CONTRACTION"]:
            return "VOLUME_CONTRACTION"
        return "VOLUME_NORMAL"

    @staticmethod
    def normalize_pcr(pcr):
        try:
            val = float(pcr)
        except Exception:
            return "PCR_NEUTRAL"
        if val >= PCR_BEHAVIOUR_BANDS["BULLISH_SUPPORT"]:
            return "PCR_BULLISH_SUPPORT"
        elif val <= PCR_BEHAVIOUR_BANDS["BEARISH_RESISTANCE"]:
            return "PCR_BEARISH_RESISTANCE"
        return "PCR_NEUTRAL"

    @staticmethod
    def normalize_iv(iv_val):
        try:
            val = float(iv_val)
        except Exception:
            return "IV_NORMAL"
        if val >= IV_BEHAVIOUR_BANDS["HIGH_REGIME"]:
            return "IV_HIGH_REGIME"
        elif val <= IV_BEHAVIOUR_BANDS["LOW_REGIME"]:
            return "IV_LOW_REGIME"
        return "IV_NORMAL"

    @staticmethod
    def normalize_score(score):
        try:
            val = float(score)
        except Exception:
            return "SCORE_NEUTRAL"
        if val >= SCORE_BEHAVIOUR_BANDS["STRONG_BULLISH"]:
            return "SCORE_STRONG_BULLISH"
        elif val >= SCORE_BEHAVIOUR_BANDS["MODERATE_BULLISH"]:
            return "SCORE_MODERATE_BULLISH"
        elif val <= SCORE_BEHAVIOUR_BANDS["STRONG_BEARISH"]:
            return "SCORE_STRONG_BEARISH"
        elif val <= SCORE_BEHAVIOUR_BANDS["MODERATE_BEARISH"]:
            return "SCORE_MODERATE_BEARISH"
        return "SCORE_NEUTRAL"

    def normalize_row(self, row):
        return {
            "Price_Behavior": self.normalize_price(row.get("Price Chg %", row.get("Price_Chg_%"))),
            "OI_Behavior": self.normalize_oi(row.get("OI Chg %", row.get("OI_Chg_%"))),
            "Volume_Behavior": self.normalize_volume(row.get("Volume Chg %", row.get("Volume_Chg_%"))),
            "PCR_Behavior": self.normalize_pcr(row.get("PCR", row.get("Put_Call_Ratio"))),
            "IV_Behavior": self.normalize_iv(row.get("IVR", row.get("IV_Rank", row.get("IV")))),
            "Score_Behavior": self.normalize_score(row.get("NTIS Score", row.get("NTIS_Score")))
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





    @staticmethod
    def normalize_pattern(pattern):
        if pd.isna(pattern):
            return "UNKNOWN"
        val = str(pattern).strip().upper()
        return val if val else "UNKNOWN"

    @staticmethod
    def normalize_direction(direction):
        if pd.isna(direction):
            return "UNKNOWN"
        val = str(direction).strip().upper()
        return val if val else "UNKNOWN"

    def build_pattern_dna(self, row):
        """
        Bundle 31B.1: Canonical PDNA Hardening Generator
        Generates deterministic canonical PDNA string using normalize_row, normalize_pattern,
        normalize_direction, and PDNA_FIELD_ORDER configured centrally.
        """
        behaviors = self.normalize_row(row) if hasattr(self, "normalize_row") else {}
        
        field_map = {
            "NORMALIZATION": str(NORMALIZATION_VERSION),
            "PDNA": str(PDNA_VERSION),
            "PRICE": str(behaviors.get("Price_Behavior", "")).strip() or "UNKNOWN",
            "OI": str(behaviors.get("OI_Behavior", "")).strip() or "UNKNOWN",
            "VOLUME": str(behaviors.get("Volume_Behavior", "")).strip() or "UNKNOWN",
            "PCR": str(behaviors.get("PCR_Behavior", "")).strip() or "UNKNOWN",
            "IV": str(behaviors.get("IV_Behavior", "")).strip() or "UNKNOWN",
            "SCORE": str(behaviors.get("Score_Behavior", "")).strip() or "UNKNOWN",
            "PATTERN": self.normalize_pattern(row.get("Pattern")),
            "DIRECTION": self.normalize_direction(row.get("Direction")),
        }

        return "|".join(f"{key}:{field_map[key]}" for key in PDNA_FIELD_ORDER)


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