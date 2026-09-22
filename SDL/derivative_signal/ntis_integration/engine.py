from __future__ import annotations
from typing import Any, Callable, Iterable
EVIDENCE_KEYS=("sdl","retracement","rsi_momentum","stock_state","pit_differential","eod_unusual_activity","historical_outcome","pdna","alerts")
def _copy(value:Any)->Any:
    if isinstance(value,dict): return {str(k):_copy(v) for k,v in value.items()}
    if isinstance(value,list): return [_copy(v) for v in value]
    return value
def compose_evidence(*,sdl=None,retracement=None,rsi_momentum=None,stock_state=None,pit_differential=None,eod_unusual_activity=None,historical_outcome=None,pdna=None,alerts=None,trading_date=None,observation_timestamp=None,symbol=None)->dict[str,Any]:
    values={"sdl":sdl,"retracement":retracement,"rsi_momentum":rsi_momentum,"stock_state":stock_state,"pit_differential":pit_differential,"eod_unusual_activity":eod_unusual_activity,"historical_outcome":historical_outcome,"pdna":pdna,"alerts":alerts}
    return {"schema_version":1,"symbol":symbol,"trading_date":trading_date,"observation_timestamp":observation_timestamp,"evidence":{k:_copy(values[k]) for k in EVIDENCE_KEYS},"selection_gate":False,"decision_owner":"SDL"}
def integrate_alerts(records:Iterable[dict[str,Any]],*,rules:Iterable[dict[str,Any]],build_context:Callable[...,dict[str,Any]],evaluate_snapshot:Callable[...,list[dict[str,Any]]],store:Any=None,trading_date:str,previous_by_symbol:dict[str,dict[str,Any]]|None=None)->list[dict[str,Any]]:
    previous_by_symbol=previous_by_symbol or {}; output=[]
    for record in records:
        current=dict(record); symbol=str(current.get("symbol",current.get("Symbol",""))).strip().upper(); timestamp=current.get("observation_timestamp")
        if not symbol or timestamp in (None,""): raise ValueError("Alert integration requires symbol and observation_timestamp")
        current["symbol"]=symbol; current["trading_date"]=trading_date
        context=build_context(current,previous_by_symbol.get(symbol),trading_date=trading_date,observation_timestamp=str(timestamp))
        output.extend(evaluate_snapshot(rules,context,store=store))
    return output
