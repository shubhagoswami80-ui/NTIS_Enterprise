from pathlib import Path
root=Path(__file__).resolve().parent
T=root.parent
d=T/'dashboard.py'; e=T/'decision_evidence.py'
if not d.exists() or not e.exists(): raise SystemExit('SAFE STOP: dashboard.py or decision_evidence.py not found')
x=e.read_text(encoding='utf-8')
marker='\ndef enrich_decision(signal: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:\n'
if '_decision_score(' not in x:
    if marker not in x: raise SystemExit('SAFE STOP: enrich_decision signature not found')
    helper='''\n\ndef _decision_score(signal, sr_status, conflicts):\n    direction=str(signal.get("direction","NEUTRAL")).upper(); price=_num(signal.get("price_change_pct"))\n    if direction not in {"BULLISH","BEARISH"} or price is None or abs(price)<=0.75: return 0,"NOT TRADABLE"\n    s=min(15.0,5.0+max(0.0,min(10.0,(abs(price)-0.75)*3.0)))\n    s+=min(2.0,float(signal.get("momentum_score",0) or 0)*0.4)\n    oi=_num(signal.get("oi_change_pct")); s+=10 if oi is not None else 0\n    if oi is not None and oi>3: s+=3\n    elif oi is not None and oi>0: s+=1\n    pe=_num(signal.get("pece_value")); pcr=_num(signal.get("pcr_change_pct")); opt=0\n    if pe is not None: opt+=9 if ((direction=="BULLISH" and pe>0) or (direction=="BEARISH" and pe<0)) else 2\n    if pcr is not None: opt+=6 if ((direction=="BULLISH" and pcr>0) or (direction=="BEARISH" and pcr<0)) else 1\n    s+=min(15,opt)\n    fut=str(signal.get("futures_direction","NEUTRAL")).upper(); foi=_num(signal.get("futures_oi_change_pct"))\n    if fut==direction:\n        s+=7; s+=min(3,foi) if foi is not None and foi>0 else 0\n    elif fut not in {"NEUTRAL","NOT_AVAILABLE"}: s+=1\n    if "BROKEN" in sr_status or "CROSSED" in sr_status: s+=15\n    elif "AT_" in sr_status or "TEST" in sr_status: s+=7\n    elif "APPROACHING" in sr_status: s+=5\n    elif "ROOM" in sr_status: s+=9\n    else: s+=4\n    fr=str(signal.get("first_range_status","")).upper()\n    if direction=="BULLISH": s+=10 if "HIGH_BROKEN" in fr else 5 if "HIGH_PENDING" in fr else 3\n    else: s+=10 if "LOW_BROKEN" in fr else 5 if "LOW_PENDING" in fr else 3\n    vol=_num(signal.get("volume_change_pct")); s+=5 if vol is not None and vol>0 else 2 if vol is not None else 0\n    s+=max(0,5-len(conflicts)*2); s=int(round(max(0,min(100,s))))\n    return s,("VERY STRONG" if s>=85 else "STRONG" if s>=75 else "MODERATE" if s>=65 else "WEAK" if s>=55 else "CONFLICTED / LOW")\n'''
    x=x.replace(marker,helper+marker,1)
needle='    direction = str(out.get("direction", "NEUTRAL")).upper()\n'
if 'price_gate = _num(out.get("price_change_pct"))' not in x:
    if needle not in x: raise SystemExit('SAFE STOP: direction line not found')
    gate='''    direction = str(out.get("direction", "NEUTRAL")).upper()\n    price_gate = _num(out.get("price_change_pct"))\n    if price_gate is None or abs(price_gate) <= 0.75:\n        out.update({"eligibility_status":"NOT_TRADABLE","decision_score":0,"decision_strength":"NOT TRADABLE","setup":"NOT TRADABLE","confirmation":"REJECTED","action":"EXCLUDE","decision_quality":"LOW","decision_reason":f"Price move {price_gate if price_gate is not None else 'unavailable'} does not clear the strict +/-0.75% gate."})\n        return out\n    out["eligibility_status"]="ELIGIBLE"\n'''
    x=x.replace(needle,gate,1)
q='    quality = "HIGH" if len(source_roles) >= 5 and not conflicts else "MEDIUM" if len(source_roles) >= 3 else "LOW"\n'
if 'decision_score, decision_strength = _decision_score' not in x:
    if q not in x: raise SystemExit('SAFE STOP: quality line not found')
    x=x.replace(q,'    decision_score, decision_strength = _decision_score(out, sr_status, conflicts)\n\n'+q,1)
c='        "decision_color": "red" if direction == "BEARISH" else "green" if direction == "BULLISH" else "amber",\n'
if '"decision_score": decision_score' not in x:
    if c not in x: raise SystemExit('SAFE STOP: decision_color output not found')
    x=x.replace(c,c+'        "decision_score": decision_score,\n        "decision_strength": decision_strength,\n',1)
e.write_text(x,encoding='utf-8')

y=d.read_text(encoding='utf-8')
a=y.find('def _rank(result: pd.DataFrame) -> pd.DataFrame:'); b=y.find('\ndef _css():',a)
if a<0 or b<0: raise SystemExit('SAFE STOP: _rank boundaries not found')
rank='''def _rank(result: pd.DataFrame) -> pd.DataFrame:\n    if result.empty: return result.copy()\n    out=result.copy()\n    if "eligibility_status" in out.columns:\n        out=out[out["eligibility_status"].astype(str).str.upper().eq("ELIGIBLE")].copy()\n    elif "price_change_pct" in out.columns:\n        px=pd.to_numeric(out["price_change_pct"],errors="coerce"); out=out[px.abs()>0.75].copy()\n    if out.empty: return out\n    out["_decision_score"]=pd.to_numeric(out.get("decision_score",0),errors="coerce").fillna(0)\n    return out.sort_values("_decision_score",ascending=False,na_position="last")\n'''
y=y[:a]+rank+y[b:]
d.write_text(y,encoding='utf-8')
print('Decision Model v6 patch completed.')
