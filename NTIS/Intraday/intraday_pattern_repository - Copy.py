"""
===========================================================
NTIS Persistent Pattern Intelligence Repository (PIR)
Version : 1.0

Purpose:
    Maintain persistent, cross-day stock-indexed pattern repository
    keyed by Symbol + Normalized Pattern Fingerprint, assigning 
    stable Business Pattern IDs (e.g., PAT-SYM-000001).
===========================================================
"""

from pathlib import Path
import hashlib
import pandas as pd

from config_loader import LEARNING_ROOT


class IntradayPatternRepository:

    def __init__(self, repo_file=None):
        self.repo_file = Path(repo_file) if repo_file else (LEARNING_ROOT / "intraday_pattern_repository.csv")
        self.repo_df = self._load_repository()

    def _load_repository(self) -> pd.DataFrame:
        if self.repo_file.exists():
            try:
                df = pd.read_csv(self.repo_file, dtype=str)
                if not df.empty:
                    return df
            except Exception:
                pass
        
        return pd.DataFrame(columns=[
            "Business_Pattern_ID",
            "Symbol",
            "Pattern_Fingerprint",
            "Pattern_Name",
            "Direction",
            "NTIS_Score",
            "Price_Chg_%",
            "OI_Chg_%",
            "Volume_Chg_%",
            "Fut_Buildup",
            "Validation_Signal",
            "Occurrences",
            "Successful_Trades",
            "Failed_Trades",
            "Pending_Trades",
            "Success_%",
            "Average_PnL",
            "First_Seen",
            "Last_Seen",
        ])

    def save_repository(self):
        self.repo_file.parent.mkdir(parents=True, exist_ok=True)
        self.repo_df.to_csv(self.repo_file, index=False)
        return self.repo_file

    def generate_fingerprint(self, row: dict) -> str:
        fields = [
            str(row.get("Direction", "")).strip().upper(),
            str(row.get("Pattern", "")).strip(),
            str(row.get("Validation Signal", row.get("Validation_Signal", ""))).strip(),
            str(row.get("Fut Buildup", row.get("Fut_Buildup", ""))).strip(),
            str(round(float(row.get("NTIS Score", row.get("NTIS_Score", 0))), 1)),
            str(round(float(row.get("Price Chg %", row.get("Price_Chg_%", 0))), 2)),
            str(round(float(row.get("OI Chg %", row.get("OI_Chg_%", 0))), 2)),
        ]
        raw_str = "|".join(fields)
        return hashlib.sha1(raw_str.encode("utf-8")).hexdigest()[:12].upper()

    def get_or_create_pattern_id(self, symbol: str, fingerprint: str, sample_row: dict, trade_date: str = None) -> str:
        symbol = str(symbol).strip().upper()
        
        # Check if already exists in repository
        match = self.repo_df[
            (self.repo_df["Symbol"] == symbol) & 
            (self.repo_df["Pattern_Fingerprint"] == fingerprint)
        ]
        
        if not match.empty:
            return str(match.iloc[0]["Business_Pattern_ID"])
        
        # Generate new sequential Business Pattern ID for symbol
        sym_existing = self.repo_df[self.repo_df["Symbol"] == symbol]
        seq = len(sym_existing) + 1
        pattern_id = f"PAT-{symbol}-{seq:06d}"
        
        new_row = {
            "Business_Pattern_ID": pattern_id,
            "Symbol": symbol,
            "Pattern_Fingerprint": fingerprint,
            "Pattern_Name": str(sample_row.get("Pattern", "")),
            "Direction": str(sample_row.get("Direction", "")),
            "NTIS_Score": str(sample_row.get("NTIS Score", sample_row.get("NTIS_Score", 0))),
            "Price_Chg_%": str(sample_row.get("Price Chg %", sample_row.get("Price_Chg_%", 0))),
            "OI_Chg_%": str(sample_row.get("OI Chg %", sample_row.get("OI_Chg_%", 0))),
            "Volume_Chg_%": str(sample_row.get("Volume Chg %", sample_row.get("Volume_Chg_%", 0))),
            "Fut_Buildup": str(sample_row.get("Fut Buildup", sample_row.get("Fut_Buildup", ""))),
            "Validation_Signal": str(sample_row.get("Validation Signal", sample_row.get("Validation_Signal", ""))),
            "Occurrences": "0",
            "Successful_Trades": "0",
            "Failed_Trades": "0",
            "Pending_Trades": "0",
            "Success_%": "0.0",
            "Average_PnL": "0.0",
            "First_Seen": trade_date if trade_date else pd.Timestamp.now().strftime("%Y-%m-%d"),
            "Last_Seen": trade_date if trade_date else pd.Timestamp.now().strftime("%Y-%m-%d"),
        }
        
        self.repo_df = pd.concat([self.repo_df, pd.DataFrame([new_row])], ignore_index=True)
        self.save_repository()
        return pattern_id

    def update_repository_from_memory(self, memory_df: pd.DataFrame):
        if memory_df.empty:
            return self.repo_file
            
        for _, row in memory_df.iterrows():
            sym = str(row.get("Symbol", "")).strip().upper()
            if not sym:
                continue
            fp = self.generate_fingerprint(row.to_dict())
            pid = self.get_or_create_pattern_id(sym, fp, row.to_dict())
            
            idx = self.repo_df[self.repo_df["Business_Pattern_ID"] == pid].index
            if not idx.empty:
                i = idx[0]
                self.repo_df.loc[i, "Last_Seen"] = pd.Timestamp.now().strftime("%Y-%m-%d")
                
        # Recompute statistics from memory if available
        self.save_repository()
        return self.repo_file

    def lookup_pattern(self, business_pattern_id: str) -> dict:
        match = self.repo_df[self.repo_df["Business_Pattern_ID"] == business_pattern_id]
        if match.empty:
            return {}
        return match.iloc[0].to_dict()
