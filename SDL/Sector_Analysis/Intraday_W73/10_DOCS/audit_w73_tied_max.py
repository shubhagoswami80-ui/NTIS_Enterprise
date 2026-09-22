from pathlib import Path
import hashlib, json
import pandas as pd
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "00_BASELINE" / "chronological_validation_corrected.csv"
OUT = ROOT / "00_BASELINE"
REQ = {"holdout_rate","holdout_n","holdout_dates","holdout_symbols"}
META = {"candidate_id","pattern_id","rank","score","holdout_rate","holdout_n","holdout_dates","holdout_symbols","train_rate","train_n","train_dates","train_symbols","target","reached_0_5x"}

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def clean(v):
    if pd.isna(v): return None
    return v.item() if hasattr(v,"item") else v

def main():
    df=pd.read_csv(BASE)
    miss=sorted(REQ-set(df.columns))
    if miss: raise RuntimeError(f"Missing columns: {miss}")
    r=df.copy()
    for c in REQ: r[c]=pd.to_numeric(r[c],errors="coerce")
    r=r.dropna(subset=list(REQ))
    r=r[(r.holdout_n>=30)&(r.holdout_dates>=3)&(r.holdout_symbols>=10)]
    rate=float(r.holdout_rate.max())
    tied=r[r.holdout_rate==rate].copy()
    candidates=[]
    for idx,row in tied.iterrows():
        cond={}
        for c in r.columns:
            if c not in META and pd.notna(row[c]): cond[c]=clean(row[c])
        candidates.append({"source_row":int(idx),"candidate_id":str(row.get("candidate_id",row.get("pattern_id",f"ROW_{idx}"))),"holdout_rate":rate,"holdout_n":int(row.holdout_n),"holdout_dates":int(row.holdout_dates),"holdout_symbols":int(row.holdout_symbols),"conditions":cond})
    fields=sorted(set().union(*(x["conditions"].keys() for x in candidates)))
    comparison=[]
    for f in fields:
        vals=[x["conditions"].get(f,"<MISSING>") for x in candidates]
        comparison.append({"feature":f,"candidate_1":vals[0] if len(vals)>0 else "<MISSING>","candidate_2":vals[1] if len(vals)>1 else "<MISSING>","same":len(set(map(str,vals)))==1})
    payload={"schema_version":"W73_TIED_MAX_AUDIT_V1","created_at":datetime.now().isoformat(timespec="seconds"),"source":str(BASE),"source_sha256":sha256(BASE),"max_holdout_rate":rate,"max_holdout_rate_pct":rate*100,"tied_max_count":len(candidates),"candidates":candidates,"common_conditions":{x["feature"]:x["candidate_1"] for x in comparison if x["same"]},"differing_conditions":[x for x in comparison if not x["same"]],"decision":"TWO CANDIDATES TIE AT THE MAXIMUM. Both are preserved. No tie-breaker is invented."}
    (OUT/"strategy_baseline_v1_tied_max.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")
    pd.DataFrame(comparison).to_csv(OUT/"tied_max_condition_comparison.csv",index=False)
    print("STATUS COMPLETE")
    print(f"MAX_RATE_PCT={rate*100:.3f}")
    print(f"TIED_MAX={len(candidates)}")
    print(f"COMMON_CONDITIONS={len(payload['common_conditions'])}")
    print(f"DIFFERING_CONDITIONS={len(payload['differing_conditions'])}")
    for i,x in enumerate(candidates,1): print(f"CANDIDATE_{i}={x['candidate_id']}")
    print(f"OUTPUT={OUT/'strategy_baseline_v1_tied_max.json'}")

if __name__=="__main__": main()
