from __future__ import annotations
import pandas as pd

def rank_pdna_candidates(records: pd.DataFrame) -> pd.DataFrame:
    """Evidence-only PDNA candidate ordering; never changes SDL selection."""
    if records is None or records.empty:
        return pd.DataFrame(columns=["rank","symbol","pdna_score","pdna_reason"])
    df=records.copy()
    def n(col):
        return pd.to_numeric(df[col],errors="coerce").fillna(0.0) if col in df else pd.Series(0.0,index=df.index)
    replay=n("replay_strength").clip(0,100)/100
    hist=n("historical_success_ratio").clip(0,1)
    evidence=n("evidence_confidence").clip(0,1)
    repo=n("repository_confidence").clip(0,1)
    maturity=n("pattern_maturity").clip(0,1)
    df["pdna_score"]=(0.30*replay+0.25*hist+0.20*evidence+0.15*repo+0.10*maturity).round(4)
    df["pdna_reason"]="quantitative fingerprint evidence"
    df=df.sort_values(["pdna_score"],ascending=False,kind="mergesort").reset_index(drop=True)
    df.insert(0,"rank",range(1,len(df)+1))
    return df
