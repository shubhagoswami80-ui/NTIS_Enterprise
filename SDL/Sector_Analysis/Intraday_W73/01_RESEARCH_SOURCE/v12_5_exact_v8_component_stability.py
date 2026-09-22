from pathlib import Path
import argparse, itertools, json, re
import pandas as pd

DEFAULT_ROOT=Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
HARD_GATE=0.80
RESEARCH_GATE=0.67
MIN_N=30
MIN_DATES=4
MAX_COMBO=3

def norm(x):
    return re.sub(r'_+','_',str(x).strip().lower().replace(' ','_').replace('-','_').replace('%','pct').replace('âˆ’','_'))

def family(c):
    c=str(c)
    if c in {"orb_agree","orb_price_agree","orb_fut_agree"}: return "ORB"
    if c in {"price_dir","price_state"}: return "PRICE"
    if c in {"option_dir","ce_state","pe_state","pec_state","ce_pct_state","pe_pct_state","pec_pct_state"}: return "OPTIONS"
    if c in {"fut_dir","fut_state","fut_oi_state","fut_pct_state"}: return "FUTURES"
    if c=="volume_state": return "VOLUME"
    if c in {"evidence_agreement","persistent","strength_bucket","core_count_band","magnitude_count_band"}: return "EVIDENCE"
    return "OTHER"

def main():
    ap=argparse.ArgumentParser(description="Exact V8 component stability and cross-family mix-and-match study; research only.")
    ap.add_argument("--root",default=str(DEFAULT_ROOT))
    ap.add_argument("--min-n",type=int,default=MIN_N)
    ap.add_argument("--min-dates",type=int,default=MIN_DATES)
    a=ap.parse_args(); root=Path(a.root)
    src=root/".sector_intelligence"/"maturity_conditional_pattern_discovery_v8"/"maturity_feature_matrix.csv"
    out=root/".sector_intelligence"/"v12_5_exact_v8_component_stability"; out.mkdir(parents=True,exist_ok=True)
    if not src.exists():
        raise FileNotFoundError(f"Missing exact V8 feature matrix: {src}")
    r=pd.read_csv(src,low_memory=False)
    r.columns=[norm(c) for c in r.columns]
    required={"orb_minutes","symbol","trade_date","maturity","reached_0_5x"}
    missing=sorted(required-set(r.columns))
    if missing: raise ValueError(f"Missing required columns: {missing}")
    r["trade_date"]=pd.to_datetime(r["trade_date"],errors="coerce").dt.date
    r["reached_0_5x"]=r["reached_0_5x"].astype(str).str.strip().str.lower().isin({"true","1","yes","y","up","down"})
    feature_cols=[c for c in r.columns if c not in {"orb_minutes","symbol","trade_date","maturity","reached_0_5x","orb_dir"}]
    feature_cols=[c for c in feature_cols if r[c].nunique(dropna=True)<=8]
    feature_cols=[c for c in feature_cols if family(c)!="OTHER"]
    dates=sorted(d for d in r.trade_date.dropna().unique())
    if len(dates)<8: raise ValueError("Too few dates for chronological component stability study.")
    holdout_n=max(4, len(dates)//3)
    train_dates=dates[:-holdout_n]; holdout_dates=dates[-holdout_n:]
    train=r[r.trade_date.isin(train_dates)].copy()
    hold=r[r.trade_date.isin(holdout_dates)].copy()

    def eval_filter(df, cols, vals):
        m=pd.Series(True,index=df.index)
        for c,v in zip(cols,vals):
            m &= df[c].astype(str).eq(str(v))
        h=df[m]
        return h

    # Individual footprints: exact V8 states, with chronological stability.
    indiv=[]
    for c in feature_cols:
        vals=train[c].dropna().astype(str).value_counts().head(8).index.tolist()
        for v in vals:
            h=eval_filter(train,[c],[v]); n=len(h); nd=h.trade_date.nunique()
            if n<a.min_n or nd<a.min_dates: continue
            q=eval_filter(hold,[c],[v])
            rate=float(h.reached_0_5x.mean()); hr=float(q.reached_0_5x.mean()) if len(q) else None
            indiv.append({"feature":c,"family":family(c),"state":v,"train_n":n,"train_dates":nd,"train_symbols":h.symbol.nunique(),
                          "train_hit_rate":rate,"holdout_n":len(q),"holdout_dates":q.trade_date.nunique(),
                          "holdout_symbols":q.symbol.nunique(),"holdout_hit_rate":hr,
                          "train_class":"FINAL_CANDIDATE" if rate>=HARD_GATE else ("OPTIMIZATION_RESEARCH" if rate>=RESEARCH_GATE else "BELOW_RESEARCH_GATE"),
                          "holdout_class":"FINAL_CANDIDATE" if hr is not None and hr>=HARD_GATE and len(q)>=a.min_n and q.trade_date.nunique()>=3 and q.symbol.nunique()>=10 else
                              ("OPTIMIZATION_RESEARCH" if hr is not None and hr>=RESEARCH_GATE else "NO_SUPPORT_OR_BELOW_GATE")})
    indiv_df=pd.DataFrame(indiv)
    indiv_df.to_csv(out/"component_stability.csv",index=False)

    # Mix-and-match: cross-family exact state combinations. Components must individually have
    # enough train support; this is deliberately stricter than V8's unrestricted combinations.
    comps=[]
    states_by_feature={}
    for c in feature_cols:
        vals=train[c].dropna().astype(str).value_counts().head(8).index.tolist()
        states_by_feature[c]=[v for v in vals if len(eval_filter(train,[c],[v]))>=a.min_n and eval_filter(train,[c],[v]).trade_date.nunique()>=a.min_dates]
    features_by_family={}
    for c in feature_cols: features_by_family.setdefault(family(c),[]).append(c)
    fams=sorted(features_by_family)
    # choose 2/3 distinct families; then one feature from each.
    for k in (2,3):
        for fam_combo in itertools.combinations(fams,k):
            for cols in itertools.product(*(features_by_family[f] for f in fam_combo)):
                if len(set(cols))<k: continue
                state_lists=[states_by_feature.get(c,[]) for c in cols]
                if any(not x for x in state_lists): continue
                for vals in itertools.product(*state_lists):
                    h=eval_filter(train,list(cols),vals)
                    n=len(h); nd=h.trade_date.nunique()
                    if n<a.min_n or nd<a.min_dates: continue
                    q=eval_filter(hold,list(cols),vals)
                    tr=float(h.reached_0_5x.mean()); hr=float(q.reached_0_5x.mean()) if len(q) else None
                    comps.append({"factor_count":k,"families":"|".join(fam_combo),
                                  "pattern_features":" & ".join(f"{c}={v}" for c,v in zip(cols,vals)),
                                  "train_n":n,"train_dates":nd,"train_symbols":h.symbol.nunique(),"train_hit_rate":tr,
                                  "holdout_n":len(q),"holdout_dates":q.trade_date.nunique(),"holdout_symbols":q.symbol.nunique(),
                                  "holdout_hit_rate":hr,
                                  "holdout_support":"SUPPORTED" if len(q)>0 else "NO_SUPPORT",
                                  "train_class":"FINAL_CANDIDATE" if tr>=HARD_GATE else ("OPTIMIZATION_RESEARCH" if tr>=RESEARCH_GATE else "BELOW_RESEARCH_GATE"),
                                  "holdout_class":"FINAL_VALIDATION" if hr is not None and hr>=HARD_GATE and len(q)>=a.min_n and q.trade_date.nunique()>=3 and q.symbol.nunique()>=10 else
                                      ("OPTIMIZATION_RESEARCH" if hr is not None and hr>=RESEARCH_GATE else "NO_SUPPORT_OR_BELOW_GATE")})
    comp_df=pd.DataFrame(comps)
    if not comp_df.empty:
        comp_df=comp_df.sort_values(["holdout_class","holdout_hit_rate","holdout_n"],ascending=[True,False,False],na_position="last")
    comp_df.to_csv(out/"cross_family_mix_match_stability.csv",index=False)

    # Concise gate summary and diagnostic on recurrence.
    supported=comp_df[comp_df.holdout_n.fillna(0)>0] if not comp_df.empty else comp_df
    final=comp_df[(comp_df.holdout_hit_rate.fillna(-1)>=HARD_GATE)&(comp_df.holdout_n>=a.min_n)&(comp_df.holdout_dates>=3)&(comp_df.holdout_symbols>=10)] if not comp_df.empty else comp_df
    research=comp_df[(comp_df.holdout_hit_rate.fillna(-1)>=RESEARCH_GATE)&(comp_df.holdout_hit_rate.fillna(-1)<HARD_GATE)] if not comp_df.empty else comp_df
    summary={
      "status":"READY","study":"V12_5_EXACT_V8_COMPONENT_STABILITY",
      "source":str(src),"production_changes":False,
      "authoritative_target":"reached_0_5x","fixed_0_5_percent_target_used":False,
      "exact_v8_semantics":True,"feature_count":len(feature_cols),
      "total_dates":len(dates),"train_dates":len(train_dates),"holdout_dates":len(holdout_dates),
      "train_date_start":str(train_dates[0]),"train_date_end":str(train_dates[-1]),
      "holdout_date_start":str(holdout_dates[0]),"holdout_date_end":str(holdout_dates[-1]),
      "component_rows":len(indiv_df),"cross_family_rows":len(comp_df),
      "cross_family_holdout_supported":len(supported),
      "cross_family_final_validation_candidates":len(final),
      "cross_family_holdout_research_candidates":len(research),
      "max_holdout_rate":float(supported.holdout_hit_rate.max()) if len(supported) else None,
      "design":"1-factor component stability plus 2/3-factor cross-family exact-state combinations; no reconstructed semantics",
      "gate":"Final validation requires >=80% plus holdout n>=30, dates>=3, symbols>=10; gate not lowered.",
      "interpretation":"No-support in holdout is recurrence failure/insufficient support, not a fabricated 0% hit rate."
    }
    (out/"study_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
