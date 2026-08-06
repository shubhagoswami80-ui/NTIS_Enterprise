from pathlib import Path

import pandas as pd

from similarity_core_clean.integration.pattern_fingerprint_engine import PatternFingerprintEngine


class EODSimilarityBridge:

    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir or "E:/NSE_Daily_Analysis/Output")
        self.input_file = self.output_dir / "ntis_pattern_analysis.csv"
        self.engine = PatternFingerprintEngine()

    def _load_pattern_analysis(self):
        if not self.input_file.exists():
            return None

        try:
            return pd.read_csv(self.input_file)
        except Exception:
            return None

    def _build_market_state(self, row):
        symbol = row.get("Symbol")
        date_value = row.get("Date")
        if symbol is None or date_value is None:
            return None

        return {
            "symbol": str(symbol).strip(),
            "date": str(date_value).strip(),
            "close": row.get("CMP"),
            "volume": row.get("Volume"),
            "trend": row.get("Price Chg %"),
            "volatility": row.get("IVR"),
            "confidence": row.get("NTIS Score"),
            "pattern_classification": row.get("Pattern"),
        }

    def build_fingerprint_payloads(self):
        df = self._load_pattern_analysis()
        if df is None:
            return []

        payloads = []

        for _, row in df.iterrows():
            market_state = self._build_market_state(row)
            if not market_state:
                continue

            fingerprint = self.engine.build_fingerprint(market_state)
            if fingerprint.get("status") != "FINGERPRINT_READY":
                continue

            payloads.append({
                "pattern_classification": fingerprint.get("pattern_classification"),
                "pattern_dna": fingerprint.get("pattern_dna"),
                "business_pattern_id": fingerprint.get("business_pattern_id"),
                "fingerprint_version": fingerprint.get("fingerprint_version"),
                "normalized_features": fingerprint.get("normalized_features"),
            })

        return payloads
