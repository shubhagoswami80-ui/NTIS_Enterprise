import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from evidence_orchestrator import build_evidence_package

def test_composes_without_mutation():
    s=pd.DataFrame([{"symbol":"ABC","direction":"BULLISH"}])
    out=build_evidence_package(sdl=s,pit=s)
    assert len(out["sdl"])==1 and len(out["pit_differential"])==1
    assert out["selection_gate"] is False
    assert out["decision_owner"]=="SDL"
def test_missing_layers_are_empty():
    out=build_evidence_package()
    assert out["rsi"].empty and out["pdna"].empty
