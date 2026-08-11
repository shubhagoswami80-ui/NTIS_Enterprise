"""
NTIS Persistent Pattern Intelligence Repository (PIR)
Bundle 30B - PDNA Stable Identity Matching

Update:
Pattern_ID is the stable cross-day identity.
Matching priority:
1. Symbol + Pattern_ID
2. Symbol + Pattern_DNA
3. Symbol + Pattern_Fingerprint
"""

from pathlib import Path
import hashlib
import pandas as pd

from config_loader import LEARNING_ROOT


class IntradayPatternRepository:

    def __init__(self, repo_file=None):
        self.repo_file = Path(repo_file) if repo_file else (
            LEARNING_ROOT / "intraday_pattern_repository.csv"
        )
        self.repo_df = self._load_repository()

    def _load_repository(self):
        if self.repo_file.exists():
            try:
                df = pd.read_csv(self.repo_file, dtype=str)
                if not df.empty:
                    return df
            except Exception:
                pass

        return pd.DataFrame()

    def save_repository(self):
        self.repo_file.parent.mkdir(parents=True, exist_ok=True)
        self.repo_df.to_csv(self.repo_file, index=False)
        return self.repo_file

    def generate_fingerprint(self, row):
        fields = [
            str(row.get("Direction", "")).strip().upper(),
            str(row.get("Pattern", "")).strip(),
            str(row.get("Validation Signal", row.get("Validation_Signal", ""))).strip(),
            str(row.get("Fut Buildup", row.get("Fut_Buildup", ""))).strip(),
            str(row.get("NTIS Score", row.get("NTIS_Score", 0))).strip(),
            str(row.get("Price Chg %", row.get("Price_Chg_%", 0))).strip(),
            str(row.get("OI Chg %", row.get("OI_Chg_%", 0))).strip(),
        ]
        return hashlib.sha1("|".join(fields).encode("utf-8")).hexdigest()[:12].upper()

    def get_or_create_pattern_id(self, symbol, fingerprint, sample_row, trade_date=None):
        symbol = str(symbol).strip().upper()

        pattern_id = str(sample_row.get("Pattern_ID", "")).strip()
        pattern_dna = str(sample_row.get("Pattern_DNA", "")).strip()

        match = pd.DataFrame()

        if pattern_id and "Pattern_ID" in self.repo_df.columns:
            match = self.repo_df[
                (self.repo_df["Symbol"] == symbol) &
                (self.repo_df["Pattern_ID"] == pattern_id)
            ]

        if match.empty and pattern_dna and "Pattern_DNA" in self.repo_df.columns:
            match = self.repo_df[
                (self.repo_df["Symbol"] == symbol) &
                (self.repo_df["Pattern_DNA"] == pattern_dna)
            ]

        if match.empty and "Pattern_Fingerprint" in self.repo_df.columns:
            match = self.repo_df[
                (self.repo_df["Symbol"] == symbol) &
                (self.repo_df["Pattern_Fingerprint"] == fingerprint)
            ]

        if not match.empty:
            return str(match.iloc[0]["Business_Pattern_ID"])

        existing = self.repo_df[self.repo_df.get("Symbol", pd.Series(dtype=str)) == symbol]
        seq = len(existing) + 1
        business_id = f"PAT-{symbol}-{seq:06d}"

        date_value = trade_date if trade_date else pd.Timestamp.now().strftime("%Y-%m-%d")

        new_row = {
            "Business_Pattern_ID": business_id,
            "Symbol": symbol,
            "Pattern_Fingerprint": fingerprint,
            "Pattern_DNA": pattern_dna,
            "Pattern_ID": pattern_id,
            "Pattern_Name": str(sample_row.get("Pattern", "")),
            "Occurrences": "0",
            "Successful_Trades": "0",
            "Failed_Trades": "0",
            "Pending_Trades": "0",
            "Success_%": "0.0",
            "Average_PnL": "0.0",
            "First_Seen": date_value,
            "Last_Seen": date_value,
            "Lifecycle_State": "NEW",
        }

        self.repo_df = pd.concat(
            [self.repo_df, pd.DataFrame([new_row])],
            ignore_index=True
        )

        self.save_repository()
        return business_id
