
from pathlib import Path
import json, re, ast
import pandas as pd

ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
SI = ROOT / ".sector_intelligence"
OUT = SI / "v11_near_hit_persistence_path_quality"

def find_csv(name):
    hits = sorted(SI.rglob(name)) if SI.exists() else []
    return hits[0] if hits else None

def col(df, names):
    m = {str(c).strip().lower(): c for c in df.columns}
    for n in names:
        if n.lower() in m:
            return m[n.lower()]
    return None

def num(df, names):
    c = col(df, names)
    return pd.to_numeric(df[c], errors="coerce") if c else pd.Series(float("nan"), index=df.index)

def boolean(s):
    if s.dtype == bool:
        return s
    return s.astype(str).str.strip().str.upper().map({
        "TRUE":True,"1":True,"YES":True,"Y":True,
        "FALSE":False,"0":False,"NO":False,"N":False
    }).fillna(False)

def pattern_terms(s):
    s = "" if pd.isna(s) else str(s).strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            x = ast.literal_eval(s)
            if isinstance(x, (list,tuple)):
                s = " & ".join(map(str,x))
        except Exception:
            pass
    return [x.strip().strip("()") for x in re.split(r"\s*&\s*|\s+AND\s+", s, flags=re.I) if x.strip()]

def match(df, expr):
    mask = pd.Series(True, index=df.index)
    unresolved = []
    for term in pattern_terms(expr):
        c = next((x for x in df.columns if str(x).lower() == term.lower()), None)
        if c:
            mask &= boolean(df[c])
        elif term.lower().startswith("not_"):
            b = term[4:]
            c = next((x for x in df.columns if str(x).lower() == b.lower()), None)
            if c:
                mask &= ~boolean(df[c])
            else:
                unresolved.append(term)
        else:
            unresolved.append(term)
    return (None if unresolved else mask), unresolved

def main():
    OUT.mkdir(parents=True, exist_ok=True)

    op = find_csv("multi_window_outcomes.csv")
    if not op:
        raise FileNotFoundError("multi_window_outcomes.csv not found under .sector_intelligence")
    outcomes = pd.read_csv(op, low_memory=False)

    rc = col(outcomes, ["reached_0.5x","reached_0_5x"])
    if not rc:
        raise ValueError("Existing replay outcome field reached_0.5x is missing")
    outcomes["_hit"] = boolean(outcomes[rc])
    outcomes["_fav"] = num(outcomes, ["favorable_pct","favorable_percent"])
    outcomes["_adv"] = num(outcomes, ["adverse_pct","adverse_percent"])
    outcomes["_final"] = num(outcomes, ["final_pct","final_percent"])

    cand_paths = []
    for name in [
        "candidate_rows.csv","pattern_candidates.csv",
        "pattern_candidates_5m.csv","pattern_candidates_10m.csv",
        "pattern_candidates_15m.csv"
    ]:
        p = find_csv(name)
        if p and p not in cand_paths:
            cand_paths.append(p)
    if not cand_paths:
        raise FileNotFoundError("V8 candidate CSVs not found")

    frames=[]
    for p in cand_paths:
        d=pd.read_csv(p, low_memory=False)
        if not d.empty:
            d["_source"]=str(p)
            frames.append(d)
    candidates=pd.concat(frames, ignore_index=True, sort=False)

    pc=col(candidates, ["pattern","pattern_expression","conditions","condition","rule"])
    if not pc:
        raise ValueError("No pattern-expression column found in candidate files")

    rate=num(candidates, ["favorable_rate","favorable_pct","hit_rate","rate"])
    n=num(candidates, ["n","count","sample_size","observations"])
    dates=num(candidates, ["dates","date_count","unique_dates"])
    syms=num(candidates, ["symbols","symbol_count","unique_symbols"])
    wc=col(candidates, ["orb_minutes","window","window_minutes","orb_window"])

    c=pd.DataFrame({
        "pattern":candidates[pc].astype(str),
        "orb_minutes":candidates[wc] if wc else "",
        "candidate_rate":rate,
        "candidate_n":n,
        "candidate_dates":dates,
        "candidate_symbols":syms,
        "_source":candidates["_source"]
    })
    c=c[(c.candidate_rate>=0.60)&(c.candidate_rate<0.67)].drop_duplicates(
        ["pattern","orb_minutes"], keep="first"
    )

    rows=[]; audit=[]
    dc=col(outcomes, ["trade_date","date"])
    sc=col(outcomes, ["symbol","stock"])

    for _,r in c.iterrows():
        mask, unresolved=match(outcomes,r.pattern)
        if mask is None:
            audit.append({**r.to_dict(),"match_status":"UNRESOLVED","unresolved":"|".join(unresolved)})
            continue
        sub=outcomes.loc[mask]
        if sub.empty:
            audit.append({**r.to_dict(),"match_status":"MATCHED_ZERO"})
            continue

        fav=sub["_fav"].dropna()
        adv=sub["_adv"].dropna()
        fin=sub["_final"].dropna()
        aligned=min(len(fav),len(fin))
        persistence=float((fin.abs().iloc[:aligned] >= fav.abs().iloc[:aligned]*0.50).mean()) if aligned else float("nan")

        rows.append({
            "orb_minutes":r.orb_minutes,
            "pattern":r.pattern,
            "candidate_rate":r.candidate_rate,
            "candidate_n":r.candidate_n,
            "candidate_dates":r.candidate_dates,
            "candidate_symbols":r.candidate_symbols,
            "matched_n":len(sub),
            "matched_dates":sub[dc].nunique() if dc else None,
            "matched_symbols":sub[sc].nunique() if sc else None,
            "reached_0.5x_rate":float(sub["_hit"].mean()),
            "favorable_pct_median":float(fav.median()) if len(fav) else None,
            "adverse_pct_median":float(adv.median()) if len(adv) else None,
            "final_pct_median":float(fin.median()) if len(fin) else None,
            "positive_final_rate":float((fin>0).mean()) if len(fin) else None,
            "persistence_proxy_rate":persistence,
            "path_quality_flag":"PERSISTENCE_SUPPORT" if pd.notna(persistence) and persistence>=0.50 else "INITIAL_MOVE_DOMINANT"
        })
        audit.append({**r.to_dict(),"match_status":"MATCHED","matched_n":len(sub)})

    result=pd.DataFrame(rows)
    if not result.empty:
        result=result.sort_values(
            ["reached_0.5x_rate","persistence_proxy_rate","matched_n"],
            ascending=[False,False,False], kind="stable"
        )

    pd.DataFrame(audit).to_csv(OUT/"candidate_match_audit.csv",index=False)
    result.to_csv(OUT/"v11_path_quality_by_candidate.csv",index=False)
    summary={
        "status":"READY",
        "study":"V11_NEAR_HIT_PERSISTENCE_PATH_QUALITY",
        "outcome_rows":len(outcomes),
        "candidate_rows_total":len(candidates),
        "near_hit_candidates_60_to_lt67":len(c),
        "matched_candidates":len(result),
        "max_reached_0.5x_rate":float(result["reached_0.5x_rate"].max()) if not result.empty else None,
        "authoritative_target":"existing reached_0.5x",
        "fixed_0.5_percent_target_used":False,
        "production_changes":False
    }
    (OUT/"v11_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
    print("OUTPUT_DIR:",OUT)

if __name__=="__main__":
    main()
