"""
===========================================================
NTIS Intraday Pattern Lifecycle Engine
Version : 1.0

Purpose:
    Manage pattern lifecycle states (NEW, LEARNING, STABLE,
    HIGH_CONFIDENCE, DECLINING, ARCHIVED), confidence evolution,
    and outcome integration linked to the Business Pattern ID.
===========================================================
"""

from pathlib import Path
import pandas as pd

from intraday_pattern_repository import IntradayPatternRepository


class IntradayPatternLifecycleEngine:

    def __init__(self, repository: IntradayPatternRepository = None):
        self.repository = repository if repository else IntradayPatternRepository()

    def determine_lifecycle_state(self, occurrences: int, success_rate: float) -> str:
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

    def evaluate_lifecycle(self):
        df = self.repository.repo_df
        if df.empty:
            return self.repository.repo_file

        states = []
        for _, row in df.iterrows():
            occ = int(float(row.get("Occurrences", 0)))
            succ = float(row.get("Success_%", 0.0))
            state = self.determine_lifecycle_state(occ, succ)
            states.append(state)

        df["Lifecycle_State"] = states
        self.repository.repo_df = df
        self.repository.save_repository()
        return self.repository.repo_file

    def integrate_outcomes(self, memory_df: pd.DataFrame):
        if memory_df.empty:
            return self.repository.repo_file

        for _, row in memory_df.iterrows():
            sym = str(row.get("Symbol", "")).strip().upper()
            if not sym:
                continue
            fp = self.repository.generate_fingerprint(row.to_dict())
            pid = self.repository.get_or_create_pattern_id(sym, fp, row.to_dict())

            match_idx = self.repository.repo_df[
                self.repository.repo_df["Business_Pattern_ID"] == pid
            ].index

            if not match_idx.empty:
                i = match_idx[0]
                occ = int(float(self.repository.repo_df.loc[i, "Occurrences"])) + 1
                self.repository.repo_df.loc[i, "Occurrences"] = str(occ)

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
                
                state = self.determine_lifecycle_state(occ, rate)
                self.repository.repo_df.loc[i, "Lifecycle_State"] = state

        self.repository.save_repository()
        return self.repository.repo_file
