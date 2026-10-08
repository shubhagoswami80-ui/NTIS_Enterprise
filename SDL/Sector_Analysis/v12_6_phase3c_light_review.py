from pathlib import Path
import pandas as pd, json
R=Path(".sector_intelligence/v12_6_exhaustive_research"); F=R/"phase3b_robust_population.csv"
if not F.exists(): raise FileNotFoundError(F)
d=pd.read_csv(F)
for c in ["holdout_n","holdout_rate","holdout_dates","holdout_symbols","factor_count","top_holdout_date_share","top_holdout_symbol_share"]:
    if c in d: d[c]=pd.to_numeric(d[c],errors="coerce")
d["band"]=pd.cut(d.holdout_rate,[-1,.65,.70,.72,1.01],labels=["<65%","65-<70%","70-<72%","72%+"],right=False)
d.groupby("band",observed=False).agg(candidates=("candidate_id","size"),median_rate=("holdout_rate","median"),max_rate=("holdout_rate","max"),median_n=("holdout_n","median"),median_dates=("holdout_dates","median"),median_symbols=("holdout_symbols","median")).reset_index().to_csv(R/"phase3c_performance_bands.csv",index=False)
rows=[]
for _,x in d.iterrows():
    for f in str(x.get("factors","")).split("|"):
        if f and f.lower()!="nan": rows.append({"factor":f,"band":x.band,"candidate_id":x.candidate_id,"holdout_rate":x.holdout_rate})
fr=pd.DataFrame(rows)
(fr.groupby(["band","factor"],observed=False).agg(candidate_count=("candidate_id","nunique"),mean_rate=("holdout_rate","mean"),max_rate=("holdout_rate","max")).reset_index() if len(fr) else pd.DataFrame()).to_csv(R/"phase3c_factor_recurrence.csv",index=False)
d.groupby(["band","kind"],observed=False).agg(candidates=("candidate_id","size"),max_rate=("holdout_rate","max"),median_rate=("holdout_rate","median")).reset_index().to_csv(R/"phase3c_family_recurrence.csv",index=False)
d.groupby(["band","factor_count"],observed=False).agg(candidates=("candidate_id","size"),max_rate=("holdout_rate","max"),median_rate=("holdout_rate","median")).reset_index().to_csv(R/"phase3c_factor_count_recurrence.csv",index=False)
d.sort_values(["holdout_rate","holdout_n"],ascending=[False,False]).head(100).to_csv(R/"phase3c_top100_robust.csv",index=False)
summary={"status":"V12_6_PHASE3C_LIGHT_REVIEW_COMPLETE","production_modified":False,"robust_population":len(d),"max_robust_rate":float(d.holdout_rate.max()),"n_ge_70":int((d.holdout_rate>=.70).sum()),"n_ge_72":int((d.holdout_rate>=.72).sum()),"n_ge_80":int((d.holdout_rate>=.80).sum())}
(R/"v12_6_phase3c_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
