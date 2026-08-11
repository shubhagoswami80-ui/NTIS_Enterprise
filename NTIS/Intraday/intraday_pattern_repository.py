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
from intraday_config import ADMISSION_POLICY_CONFIG


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
                    for col in ["Occurrences", "Successful_Trades", "Failed_Trades", "Success_%", "Average_PnL", "Confidence_Score", "First_Seen", "Last_Seen", "Last_Validated"]:
                        if col not in df.columns:
                            df[col] = "0" if col not in ["Success_%", "Average_PnL", "Confidence_Score"] else "0.0"
                    return df
            except Exception:
                pass

        return pd.DataFrame(columns=[
            "Business_Pattern_ID",
            "Symbol",
            "Pattern_Fingerprint",
            "Pattern_DNA",
            "Pattern_ID",
            "Pattern_Name",
            "Occurrences",
            "Successful_Trades",
            "Failed_Trades",
            "Pending_Trades",
            "Success_%",
            "Average_PnL",
            "First_Seen",
            "Last_Seen",
            "Confidence_Score",
            "Last_Validated",
            "Lifecycle_State",
        ])

    def save_repository(self):
        self.repo_file.parent.mkdir(parents=True, exist_ok=True)
        self.repo_df.to_csv(self.repo_file, index=False)
        return self.repo_file

    def generate_fingerprint(self, row):
        if isinstance(row, str):
            pattern_dna = row
        elif hasattr(row, "get"):
            pattern_dna = str(row.get("Pattern_DNA", ""))
            if not pattern_dna:
                try:
                    from intraday_pattern_engine import IntradayPatternEngine
                    pattern_dna = IntradayPatternEngine().build_pattern_dna(row)
                except Exception:
                    pattern_dna = str(row)
        else:
            pattern_dna = str(row)

        return hashlib.sha1(pattern_dna.encode("utf-8")).hexdigest()[:12].upper()

    def get_or_create_pattern_id(self, symbol, fingerprint, sample_row=None, trade_date=None):
        symbol = str(symbol).strip().upper()
        fingerprint = str(fingerprint).strip().upper()

        match = pd.DataFrame()

        if fingerprint and "Pattern_Fingerprint" in self.repo_df.columns:
            match = self.repo_df[
                (self.repo_df["Symbol"] == symbol) &
                (self.repo_df["Pattern_Fingerprint"] == fingerprint)
            ]

        if not match.empty:
            return str(match.iloc[0]["Business_Pattern_ID"])

        # For NEW Pattern_Fingerprint values, evaluate configurable admission policy
        if sample_row and hasattr(sample_row, "get"):
            try:
                score = float(sample_row.get("NTIS Score", sample_row.get("NTIS_Score", 50)))
            except Exception:
                score = 50.0
            pattern_name = str(sample_row.get("Pattern", "")).strip()
            min_score = ADMISSION_POLICY_CONFIG.get("MIN_SCORE", 25.0)
            if score < min_score and pattern_name in {"Neutral", ""}:
                return None  # Admission fails, skip repository insertion

        existing = self.repo_df[self.repo_df.get("Symbol", pd.Series(dtype=str)) == symbol]
        seq = len(existing) + 1
        business_id = f"PAT-{symbol}-{seq:06d}"

        date_value = trade_date if trade_date else pd.Timestamp.now().strftime("%Y-%m-%d")

        pattern_dna = ""
        pattern_id = ""
        pattern_name = ""
        if sample_row and hasattr(sample_row, "get"):
            pattern_dna = str(sample_row.get("Pattern_DNA", "")).strip()
            pattern_id = str(sample_row.get("Pattern_ID", "")).strip()
            pattern_name = str(sample_row.get("Pattern", "")).strip()

        new_row = {
            "Business_Pattern_ID": business_id,
            "Symbol": symbol,
            "Pattern_Fingerprint": fingerprint,
            "Pattern_DNA": pattern_dna,
            "Pattern_ID": pattern_id,
            "Pattern_Name": pattern_name,
            "Occurrences": "0",
            "Successful_Trades": "0",
            "Failed_Trades": "0",
            "Pending_Trades": "0",
            "Success_%": "0.0",
            "Average_PnL": "0.0",
            "First_Seen": date_value,
            "Last_Seen": date_value,
            "Confidence_Score": "0.0",
            "Last_Validated": date_value,
            "Lifecycle_State": "NEW",
        }

        self.repo_df = pd.concat(
            [self.repo_df, pd.DataFrame([new_row])],
            ignore_index=True
        )

        self.save_repository()
        return business_id

    def update_evidence(self, business_pattern_id, outcome_dict, trade_date=None):
        business_pattern_id = str(business_pattern_id).strip()
        match_idx = self.repo_df[self.repo_df["Business_Pattern_ID"] == business_pattern_id].index
        if match_idx.empty:
            return False

        i = match_idx[0]
        date_value = trade_date if trade_date else pd.Timestamp.now().strftime("%Y-%m-%d")

        for col in ["Occurrences", "Successful_Trades", "Failed_Trades", "Success_%", "Average_PnL", "Confidence_Score", "First_Seen", "Last_Seen", "Last_Validated"]:
            if col not in self.repo_df.columns:
                self.repo_df[col] = "0" if col not in ["Success_%", "Average_PnL", "Confidence_Score"] else "0.0"

        try:
            occ = int(float(self.repo_df.loc[i, "Occurrences"])) + 1
        except Exception:
            occ = 1
        self.repo_df.loc[i, "Occurrences"] = str(occ)

        existing_first = str(self.repo_df.loc[i].get("First_Seen", date_value))
        existing_last = str(self.repo_df.loc[i].get("Last_Seen", date_value))
        self.repo_df.loc[i, "First_Seen"] = min(existing_first, date_value) if existing_first else date_value
        self.repo_df.loc[i, "Last_Seen"] = max(existing_last, date_value) if existing_last else date_value
        self.repo_df.loc[i, "Last_Validated"] = date_value

        outcome = str(outcome_dict.get("Outcome", "")).strip().upper()
        if outcome in {"TARGET HIT", "SUCCESS", "WIN"}:
            try:
                s = int(float(self.repo_df.loc[i, "Successful_Trades"])) + 1
            except Exception:
                s = 1
            self.repo_df.loc[i, "Successful_Trades"] = str(s)
        elif outcome in {"STOP LOSS HIT", "FAILED", "LOSS"}:
            try:
                f = int(float(self.repo_df.loc[i, "Failed_Trades"])) + 1
            except Exception:
                f = 1
            self.repo_df.loc[i, "Failed_Trades"] = str(f)

        try:
            succ = int(float(self.repo_df.loc[i, "Successful_Trades"]))
            rate = round((succ / occ) * 100, 2) if occ > 0 else 0.0
            self.repo_df.loc[i, "Success_%"] = str(rate)
        except Exception:
            pass

        pnl = outcome_dict.get("PnL", outcome_dict.get("Return %", outcome_dict.get("Average_PnL", None)))
        if pnl is not None:
            try:
                curr_avg = float(self.repo_df.loc[i, "Average_PnL"]) if pd.notna(self.repo_df.loc[i, "Average_PnL"]) else 0.0
                new_pnl = float(pnl)
                new_avg = round(((curr_avg * (occ - 1)) + new_pnl) / occ, 2)
                self.repo_df.loc[i, "Average_PnL"] = str(new_avg)
            except Exception:
                pass

        try:
            success_rate = float(self.repo_df.loc[i, "Success_%"])
            confidence = round(min(100.0, (occ * 2.0) + (success_rate * 0.8)), 2)
            self.repo_df.loc[i, "Confidence_Score"] = str(confidence)
        except Exception:
            self.repo_df.loc[i, "Confidence_Score"] = "50.0"

        self.save_repository()
        return True
