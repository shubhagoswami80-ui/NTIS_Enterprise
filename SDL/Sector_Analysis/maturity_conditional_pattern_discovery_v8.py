from __future__ import annotations
import argparse,json,itertools,re
from pathlib import Path
from datetime import time
import pandas as pd

DEFAULT_ROOT=Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
CUTS={"09:30":time(9,30),"09:45":time(9,45),"10:00":time(10,0),"10:15":time(10,15)}
HARD_GATE=0.80
MIN_N=30
MIN_DATES=4
MAX_FEATURES_PER_PATTERN=3

def norm(x):
    return re.sub(r'_+','_',str(x).strip().lower().replace(' ','_').replace('-','_').replace('%','pct').replace('−','_').replace('−','_'))

def col(df,names):
    m={norm(c):c for c in df.columns}
    for n in names:
        if norm(n) in m:return m[norm(n)]
    return None

def truth(x):
    return str(x).strip().lower() in {'true','1','yes','y','up','down'}

def sign_state(x):
    try:
        v=float(x)
        if pd.isna(v): return None
        if v>0:return 'POS'
        if v<0:return 'NEG'
        return 'ZERO'
    except Exception:return None

def norm_dir(x):
    s=str(x).upper().strip()
    if 'UP' in s:return 'UP'
    if 'DOWN' in s:return 'DOWN'
    return 'OTHER'

def add_feature(rows, name, values):
    vals=pd.Series(values,index=rows.index)
    rows[name]=vals

def build_features(r):
    f=pd.DataFrame(index=r.index)
    # Structural state
    f['orb_dir']=r['orb_direction'].map(norm_dir)
    if 'price_direction' in r:f['price_dir']=r['price_direction'].map(norm_dir)
    if 'fut_direction' in r:f['fut_dir']=r['fut_direction'].map(norm_dir)
    if 'option_direction' in r:f['option_dir']=r['option_direction'].map(norm_dir)
    if 'fut_state' in r:f['fut_state']=r['fut_state'].astype(str).str.upper().str.strip().replace({'NAN':'NA'})
    if 'volume_pct' in r:f['volume_state']=r['volume_pct'].map(sign_state)
    if 'ce_num' in r:f['ce_state']=r['ce_num'].map(sign_state)
    if 'pe_num' in r:f['pe_state']=r['pe_num'].map(sign_state)
    if 'pec_num' in r:f['pec_state']=r['pec_num'].map(sign_state)
    if 'fut_num' in r:f['fut_oi_state']=r['fut_num'].map(sign_state)
    if 'ce_pct' in r:f['ce_pct_state']=r['ce_pct'].map(sign_state)
    if 'pe_pct' in r:f['pe_pct_state']=r['pe_pct'].map(sign_state)
    if 'pec_pct' in r:f['pec_pct_state']=r['pec_pct'].map(sign_state)
    if 'fut_pct' in r:f['fut_pct_state']=r['fut_pct'].map(sign_state)
    if 'price_chg_pct' in r:f['price_state']=r['price_chg_pct'].map(sign_state)
    if 'direction_agreement_with_orb' in r:f['orb_agree']=r['direction_agreement_with_orb'].map(lambda x:'YES' if bool(x) else 'NO')
    if 'direction_agreement' in r:f['evidence_agreement']=r['direction_agreement'].astype(str).str.upper().str.strip()
    if 'persistent' in r:f['persistent']=r['persistent'].map(lambda x:'YES' if truth(x) else 'NO')
    if 'strength_bucket' in r:f['strength_bucket']=r['strength_bucket'].astype(str).str.upper().str.strip().replace({'NAN':'NA'})
    # Evidence-count bands avoid arbitrary numeric threshold optimization.
    for src,out in [('core_evidence_count','core_count_band'),('magnitude_count','magnitude_count_band')]:
        if src in r:
            n=pd.to_numeric(r[src],errors='coerce')
            f[out]=pd.cut(n,[-1,0,1,2,99],labels=['0','1','2','3+'])
            f[out]=f[out].astype(str).replace('NAN','NA')
    # Interaction features that have direct semantic meaning.
    if 'orb_dir' in f.columns and 'fut_dir' in f.columns:
        f['orb_fut_agree']=((f.orb_dir==f.fut_dir)&f.orb_dir.isin(['UP','DOWN'])).map(lambda x:'YES' if x else 'NO')
    if 'orb_dir' in f.columns and 'price_dir' in f.columns:
        f['orb_price_agree']=((f.orb_dir==f.price_dir)&f.orb_dir.isin(['UP','DOWN'])).map(lambda x:'YES' if x else 'NO')
    return f

def main():
    ap=argparse.ArgumentParser(description='Cache-only maturity conditional pattern discovery; descriptive research, no SDL rule changes.')
    ap.add_argument('--root',default=str(DEFAULT_ROOT)); ap.add_argument('--min-n',type=int,default=MIN_N); ap.add_argument('--min-dates',type=int,default=MIN_DATES)
    a=ap.parse_args(); root=Path(a.root); intel=root/'.sector_intelligence'; disc=intel/'smart_replay_hit_discovery'; out=intel/'maturity_conditional_pattern_discovery_v8'; out.mkdir(parents=True,exist_ok=True)
    canon=intel/'data_strength_combination_study'/'canonical_strength_observations.csv'; multi=disc/'multi_window_outcomes.csv'
    summary={'status':'FAILED','cache_only':True,'raw_source_scan':False,'output_dir':str(out),'canonical_source':str(canon),'orb_outcome_source':str(multi),'maturity_cutoffs':list(CUTS),'primary_outcome':'existing reached_0.5x from multi_window_outcomes.csv','hard_validation_gate':HARD_GATE,'min_n':a.min_n,'min_dates':a.min_dates}
    if not canon.exists() or not multi.exists():
        summary['reason']='Required cache missing'; (out/'v8_summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2)); return 2
    parts=[]
    for ch in pd.read_csv(canon,low_memory=False,chunksize=200000):
        ch.columns=[norm(c) for c in ch.columns]
        ts=col(ch,['timestamp']); sym=col(ch,['symbol']); td=col(ch,['trade_date','trading_date','date'])
        if ts is None or sym is None:continue
        ch['_ts']=pd.to_datetime(ch[ts],errors='coerce'); ch['_symbol']=ch[sym].astype(str).str.strip(); ch['_date']=pd.to_datetime(ch[td],errors='coerce').dt.date if td else ch['_ts'].dt.date
        ch=ch[ch['_ts'].notna()&ch['_date'].notna()&ch['_symbol'].ne('')]
        keep=['_ts','_symbol','_date']+[x for x in ['price_direction','direction_agreement','core_evidence_count','magnitude_count','strength_bucket','persistent','option_direction','fut_direction','price_chg_pct','volume_pct','ce_num','pe_num','pec_num','ce_pct','pe_pct','pec_pct','fut_num','fut_pct','fut_state'] if x in ch.columns]
        parts.append(ch[keep])
    c=pd.concat(parts,ignore_index=True).sort_values(['_symbol','_date','_ts']).drop_duplicates(['_symbol','_date','_ts'])
    m=pd.read_csv(multi,low_memory=False); m.columns=[norm(x) for x in m.columns]
    outcome=col(m,['reached_0.5x','reached_0_5x','reached 0.5x'])
    required=['orb_minutes','symbol','trade_date','anchor_time','orb_direction']
    miss=[x for x in required if x not in m.columns]
    if miss or outcome is None:
        summary['reason']='Missing required fields: '+(', '.join(miss+[ 'reached_0.5x' ] if outcome is None else miss)); (out/'v8_summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2)); return 3
    m['_symbol']=m['symbol'].astype(str).str.strip(); m['_date']=pd.to_datetime(m['trade_date'],errors='coerce').dt.date; m['_anchor']=pd.to_datetime(m['anchor_time'],errors='coerce'); m['_reached']=m[outcome].map(truth)
    groups={(k[0],k[1]):g for k,g in c.groupby(['_symbol','_date'],sort=False)}
    rows=[]
    for _,e in m.iterrows():
        if pd.isna(e['_anchor']):continue
        g=groups.get((e['_symbol'],e['_date']))
        if g is None:continue
        for mat,cut in CUTS.items():
            # Critical temporal integrity: event must already exist by maturity; evidence must also be <= maturity.
            if e['_anchor'].time()>cut:continue
            elig=g[g['_ts'].dt.time<=cut]
            if elig.empty:continue
            ar=elig.iloc[-1]
            rec={'orb_minutes':int(e['orb_minutes']),'symbol':e['_symbol'],'trade_date':str(e['_date']),'orb_anchor_time':str(e['_anchor']),'orb_direction':str(e['orb_direction']).upper(),'maturity':mat,'evidence_timestamp':str(ar['_ts']),'reached_0_5x':bool(e['_reached'])}
            for x in ['price_direction','direction_agreement','core_evidence_count','magnitude_count','strength_bucket','persistent','option_direction','fut_direction','price_chg_pct','volume_pct','ce_num','pe_num','pec_num','ce_pct','pe_pct','pec_pct','fut_num','fut_pct','fut_state']:
                if x in ar:rec[x]=ar[x]
            rec['direction_agreement_with_orb']=((norm_dir(ar.get('price_direction',''))==norm_dir(e['orb_direction'])) and norm_dir(e['orb_direction']) in ['UP','DOWN'])
            rows.append(rec)
    r=pd.DataFrame(rows)
    if r.empty:
        summary['reason']='No maturity evidence matches'; (out/'v8_summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2)); return 4
    f=build_features(r); work=pd.concat([r[['orb_minutes','symbol','trade_date','maturity','reached_0_5x']],f],axis=1)
    work.to_csv(out/'maturity_feature_matrix.csv',index=False)
    candidates=[]
    feature_cols=[x for x in f.columns if x not in {'orb_dir'}]
    # Exclude very high-cardinality/free-text features.
    feature_cols=[x for x in feature_cols if work[x].nunique(dropna=True)<=8]
    for orb,mat in sorted(work[['orb_minutes','maturity']].drop_duplicates().itertuples(index=False,name=None)):
        g=work[(work.orb_minutes==orb)&(work.maturity==mat)].copy()
        if len(g)<a.min_n or g.trade_date.nunique()<a.min_dates:continue
        # Single features and semantically meaningful combinations up to 3 features.
        for k in range(1,MAX_FEATURES_PER_PATTERN+1):
            for cols in itertools.combinations(feature_cols,k):
                # Avoid multiple features that are exact aliases of the same concept.
                if len({('dir' if 'dir' in c or c.endswith('agreement') else 'oi' if 'state' in c and ('ce_' in c or 'pe_' in c or 'pec_' in c or 'fut_oi' in c) else c) for c in cols})<k and k>1:continue
                mask=pd.Series(True,index=g.index)
                valid=True; desc=[]
                for ccol in cols:
                    vc=g[ccol].astype(str); top=vc.value_counts(dropna=False)
                    if len(top)==0:valid=False;break
                    # Evaluate each state separately, retaining states with adequate sample/date support.
                    desc.append(ccol)
                if not valid:continue
                # Cartesian states only from observed values; cap each feature to its most common 5 states.
                states=[]
                for ccol in cols:
                    vals=g[ccol].dropna().astype(str).value_counts().head(5).index.tolist()
                    states.append(vals)
                for combo in itertools.product(*states):
                    h=g.copy()
                    for ccol,val in zip(cols,combo):h=h[h[ccol].astype(str)==val]
                    n=len(h); dates=h.trade_date.nunique()
                    if n<a.min_n or dates<a.min_dates:continue
                    rate=float(h.reached_0_5x.mean()); lift=rate-float(g.reached_0_5x.mean())
                    candidates.append({'orb_minutes':int(orb),'maturity':mat,'pattern_features':' & '.join(f'{c}={v}' for c,v in zip(cols,combo)),'n':n,'dates':dates,'symbols':h.symbol.nunique(),'hit_rate':rate,'base_rate':float(g.reached_0_5x.mean()),'lift':lift,'validation_class':'VALIDATION_CANDIDATE' if rate>=HARD_GATE else ('OPTIMIZATION_RESEARCH' if rate>=0.67 else 'BELOW_RESEARCH_GATE')})
    cand=pd.DataFrame(candidates)
    if not cand.empty:
        cand=cand.sort_values(['hit_rate','dates','n'],ascending=[False,False,False]).drop_duplicates(['orb_minutes','maturity','pattern_features'])
        cand.to_csv(out/'conditional_pattern_candidates.csv',index=False)
        cand[cand.hit_rate>=0.67].to_csv(out/'conditional_candidates_ge_67.csv',index=False)
        cand[cand.hit_rate>=HARD_GATE].to_csv(out/'conditional_candidates_ge_80.csv',index=False)
    else:
        pd.DataFrame(columns=['orb_minutes','maturity','pattern_features','n','dates','symbols','hit_rate','base_rate','lift','validation_class']).to_csv(out/'conditional_pattern_candidates.csv',index=False)
        pd.DataFrame().to_csv(out/'conditional_candidates_ge_67.csv',index=False); pd.DataFrame().to_csv(out/'conditional_candidates_ge_80.csv',index=False)
    summary.update({'status':'READY','canonical_rows':len(c),'canonical_symbols':c._symbol.nunique(),'canonical_dates':c._date.nunique(),'orb_outcome_rows':len(m),'matched_maturity_rows':len(r),'candidate_rows':int(len(cand)),'candidates_ge_67':int((cand.hit_rate>=0.67).sum()) if not cand.empty else 0,'candidates_ge_80':int((cand.hit_rate>=HARD_GATE).sum()) if not cand.empty else 0,'best_hit_rate':float(cand.hit_rate.max()) if not cand.empty else None,'best_pattern':cand.iloc[0].to_dict() if not cand.empty else None,'note':'Discovery only. Evidence is limited to information available by maturity; existing reached_0.5x outcome is used unchanged. No frozen SDL rule, score, qualification, breakout, confirmation, dashboard, or source workbook is modified. >=80% remains the hard validation gate; rate alone is insufficient without sample/date diversity and later holdout validation.'})
    (out/'v8_summary.json').write_text(json.dumps(summary,indent=2,default=str)); print(json.dumps(summary,indent=2)); return 0
if __name__=='__main__':raise SystemExit(main())
