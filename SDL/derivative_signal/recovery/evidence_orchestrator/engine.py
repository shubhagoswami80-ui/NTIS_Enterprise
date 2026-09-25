from __future__ import annotations
from typing import Any
import pandas as pd

def _frame(value):
    return value.copy() if isinstance(value,pd.DataFrame) else pd.DataFrame()

def build_evidence_package(*, sdl=None, retracement=None, rsi=None, stock_state=None, pit=None, unusual=None, outcomes=None, pdna=None, alerts=None)->dict[str,Any]:
    """Final read-only evidence composition. No component can become a selection gate."""
    return {
      "sdl":_frame(sdl),
      "retracement":_frame(retracement),
      "rsi":_frame(rsi),
      "stock_state":_frame(stock_state),
      "pit_differential":_frame(pit),
      "eod_unusual":_frame(unusual),
      "historical_outcomes":_frame(outcomes),
      "pdna":_frame(pdna),
      "alerts":_frame(alerts),
      "selection_gate":False,
      "decision_owner":"SDL",
    }
