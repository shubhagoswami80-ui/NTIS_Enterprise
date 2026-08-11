"""
===========================================================
NTIS Intraday Pattern Lifecycle Engine
Version : 1.1

Purpose:
    Manage pattern lifecycle states (NEW, LEARNING, STABLE,
    HIGH_CONFIDENCE, DECLINING, ARCHIVED), confidence evolution,
    outcome integration, merge rules, and reactivation rules
    linked to the Business Pattern ID.
===========================================================
"""

from pathlib import Path
import pandas as pd

from intraday_pattern_repository import IntradayPatternRepository


class IntradayPatternLifecycleEngine:

    def __init__(self, repository: IntradayPatternRepository = None):
        self.repository = repository if repository else IntradayPatternRepository()

    def determine_lifecycle_state(self, occurrences: int, success_rate: float, current_state: str = "NEW") -> str:
        # Reactivation rules: if ARCHIVED and new occurrences/positive evidence arrive, transition to LEARNING
        if current_state == "ARCHIVED" and occurrences > 0:
            return "LEARNING"

        if occurrences < 5:
            return "NEW"
        elif 5 <= occurrences < 15:
            return "LEARNING"
        elif occurrences >= 15 and success_rate >= 60.0:
            return "HIGH_CONFIDENCE"
        elif occurrences >= 15 and 45.0 <= success_rate < 60.0:
            return "STABLE"
        elif occurrences >= 10 and success_rate < 40.0:
            return "DECLINING"
        elif occurrences >= 30 and success_rate < 30.0:
            return "ARCHIVED"
        return "STABLE"

    def apply_merge_rules(self):
        """
        Detect duplicate Business Pattern IDs representing the same normalized fingerprint
        and merge statistics into the canonical repository record.
        """
        df = self.repository.repo_df
        if df.empty or "Pattern_Fingerprint" not in df.columns:
            return

        # Group by Symbol + Pattern_Fingerprint to detect duplicates
        grouped = []
        for (sym, fp), group in df.groupby(["Symbol", "Pattern_Fingerprint"]):
            if len(group) > 1:
                # Keep the first/canonical record and merge counts
                canonical = group.iloc[0].copy()
                total_occ = sum(int(float(x)) for x in group["Occurrences"].fillna(0))
                total_succ = sum(int(float(x)) for x in group["Successful_Trades"].fillna(0))
                total_fail = sum(int(float(x)) for x in group["Failed_Trades"].fillna(0))
                
                canonical["Occurrences"] = str(total_occ)
                canonical["Successful_Trades"] = str(total_succ)
                canonical["Failed_Trades"] = str(total_fail)
                
                rate = round((total_succ / total_occ) * 100, 2) if total_occ > 0 else 0.0
                canonical["Success_%"] = str(rate)
                
                first_seen = group["First_Seen"].min()
                last_seen = group["Last_Seen"].max()
                canonical["First_Seen"] = str(first_seen)
                canonical["Last_Seen"] = str(last_seen)
                
                grouped.append(canonical)
            else:
                grouped.append(group.iloc[0])

        if grouped:
            self.repository.repo_df = pd.DataFrame(grouped)
            self.repository.save_repository()

    def evaluate_lifecycle(self):
        self.apply_merge_rules()
        df = self.repository.repo_df
        if df.empty:
            return self.repository.repo_file

        states = []
        for _, row in df.iterrows():
            occ = int(float(row.get("Occurrences", 0)))
            succ = float(row.get("Success_%", 0.0))
            curr = str(row.get("Lifecycle_State", "NEW"))
            state = self.determine_lifecycle_state(occ, succ, curr)
            states.append(state)

        df["Lifecycle_State"] = states
        self.repository.repo_df = df
        self.repository.save_repository()
        return self.repository.repo_file

    def integrate_outcomes(self, memory_df: pd.DataFrame, trade_date: str = None):
        if memory_df.empty:
            return self.repository.repo_file

        for _, row in memory_df.iterrows():
            sym = str(row.get("Symbol", "")).strip().upper()
            if not sym:
                continue
            fp = self.repository.generate_fingerprint(row.to_dict())
            pid = self.repository.get_or_create_pattern_id(sym, fp, row.to_dict(), trade_date=trade_date)
            if not pid:
                continue

            match_idx = self.repository.repo_df[
                self.repository.repo_df["Business_Pattern_ID"] == pid
            ].index

            if not match_idx.empty:
                i = match_idx[0]
                curr_state = str(self.repository.repo_df.loc[i].get("Lifecycle_State", "NEW"))
                occ = int(float(self.repository.repo_df.loc[i, "Occurrences"])) + 1
                self.repository.repo_df.loc[i, "Occurrences"] = str(occ)
                if trade_date:
                    existing_first = str(self.repository.repo_df.loc[i].get("First_Seen", trade_date))
                    existing_last = str(self.repository.repo_df.loc[i].get("Last_Seen", trade_date))
                    self.repository.repo_df.loc[i, "First_Seen"] = min(existing_first, trade_date) if existing_first else trade_date
                    self.repository.repo_df.loc[i, "Last_Seen"] = max(existing_last, trade_date) if existing_last else trade_date
                else:
                    self.repository.repo_df.loc[i, "Last_Seen"] = pd.Timestamp.now().strftime("%Y-%m-%d")

                outcome = str(row.get("Outcome", "")).strip().upper()
                if outcome == "TARGET HIT" or outcome == "SUCCESS":
                    s = int(float(self.repository.repo_df.loc[i, "Successful_Trades"])) + 1
                    self.repository.repo_df.loc[i, "Successful_Trades"] = str(s)
                elif outcome == "STOP LOSS HIT" or outcome == "FAILED":
                    f = int(float(self.repository.repo_df.loc[i, "Failed_Trades"])) + 1
                    self.repository.repo_df.loc[i, "Failed_Trades"] = str(f)

                succ_trades = int(float(self.repository.repo_df.loc[i, "Successful_Trades"]))
                rate = round((succ_trades / occ) * 100, 2) if occ > 0 else 0.0
                self.repository.repo_df.loc[i, "Success_%"] = str(rate)
                
                state = self.determine_lifecycle_state(occ, rate, curr_state)
                self.repository.repo_df.loc[i, "Lifecycle_State"] = state

        self.repository.save_repository()
        return self.repository.repo_file
