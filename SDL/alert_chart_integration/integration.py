from __future__ import annotations
from typing import Any

def build_alert_snapshot(current: dict[str,Any], previous: dict[str,Any]|None=None, *, trading_date=None, observation_timestamp=None)->dict[str,Any]:
    """Thin integration boundary for existing alert_chart package.
    It does not evaluate selection, alter decisions, or invent timestamps.
    """
    cur=dict(current or {})
    prev=dict(previous or {})
    if trading_date is not None: cur["trading_date"]=trading_date; prev.setdefault("trading_date",trading_date)
    if observation_timestamp is not None: cur["observation_timestamp"]=observation_timestamp
    return {"current":cur,"previous":prev,"is_selection_gate":False,"source":"SDL_AUTHORITATIVE"}
