import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from pdna_ranking import rank_pdna_candidates

def test_quantitative_order_only():
    df=pd.DataFrame([
      {"symbol":"A","replay_strength":90,"historical_success_ratio":.8,"evidence_confidence":.8,"repository_confidence":.8,"pattern_maturity":.8},
      {"symbol":"B","replay_strength":50,"historical_success_ratio":.5,"evidence_confidence":.5,"repository_confidence":.5,"pattern_maturity":.5},
    ])
    out=rank_pdna_candidates(df)
    assert out.iloc[0]["symbol"]=="A"
    assert out.iloc[0]["rank"]==1
    assert "pdna_score" in out
def test_empty():
    assert rank_pdna_candidates(pd.DataFrame()).empty
