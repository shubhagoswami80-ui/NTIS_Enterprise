from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd


def num(s):
    return pd.to_numeric(s.astype(str).str.replace(',', '', regex=False).str.replace('−','-',regex=False).str.replace('%','',regex=False), errors='coerce')


def find_file(root, name):
    p=Path(root)/name
    if p.exists(): return p
    hits=sorted(Path(root).rglob(name), key=lambda x:x.stat().st_mtime, reverse=True)
    if not hits: raise FileNotFoundError(f'{name} NOT_FOUND under {root}')
    return hits[0]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--study', default='')
    ap.add_argument('--cache', default='')
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True, exist_ok=True)
    study=Path(args.study) if args.study else out.parent/'historical_outcome_reconstruction'
    cache=Path(args.cache) if args.cache else find_file(out.parent/'data_strength_combination_study','canonical_strength_observations.csv')
    outcomes=find_file(study,'historical_anchor_outcomes.csv')
    print(f'CACHE_FOUND: {cache}')
    print(f'OUTCOMES_FOUND: {outcomes}')
    c=pd.read_csv(cache,low_memory=False)
    o=pd.read_csv(outcomes,low_memory=False)
    for d in (c,o):
        if 'timestamp' in d: d['timestamp']=pd.to_datetime(d['timestamp'],errors='coerce')
        if 'anchor_timestamp' in d: d['anchor_timestamp']=pd.to_datetime(d['anchor_timestamp'],errors='coerce')
        if 'trade_date' in d: d['trade_date']=d['trade_date'].astype(str)
    c['symbol']=c['symbol'].astype(str).str.strip().str.upper()
    o['symbol']=o['symbol'].astype(str).str.strip().str.upper()

    # Independent duplicate audit BEFORE any deduplication.
    dup_groups=int(c.duplicated(['symbol','trade_date','timestamp'],keep=False).groupby([c['symbol'],c['trade_date'],c['timestamp']]).first().sum()) if len(c) else 0
    dup_rows=int(c.duplicated(['symbol','trade_date','timestamp'],keep=False).sum()) if len(c) else 0
    pair_counts=c.groupby(['symbol','trade_date']).size()
    multi_pairs=int((pair_counts>1).sum())

    # Outcome population and validity diagnostics.
    path_counts=o['path_class'].fillna('MISSING').value_counts().to_dict()
    quality_counts=o['outcome_quality'].fillna('MISSING').value_counts().to_dict()
    direction_counts=o['anchor_direction'].fillna('MISSING').value_counts().to_dict()

    tcols=[f'T{n}_signed_move_pct' for n in (1,2,3,5,10,20)]
    t_stats={}
    for col in tcols:
        if col in o:
            s=num(o[col]); t_stats[col]={'valid':int(s.notna().sum()),'positive':int((s>0).sum()),'negative':int((s<0).sum()),'zero':int((s==0).sum()),'median':float(s.median()) if s.notna().any() else None}

    # Check whether FULL_OHLC rows actually have excursion fields and whether the classification is internally coherent.
    full=o[o.outcome_quality.astype(str).eq('FULL_OHLC')].copy()
    finite_fav=num(full.get('favorable_exc_pct',pd.Series(index=full.index,dtype=float)))
    finite_adv=num(full.get('adverse_exc_pct',pd.Series(index=full.index,dtype=float)))
    finite_final=num(full.get('final_move_signed_pct',pd.Series(index=full.index,dtype=float)))
    class_check={
        'full_ohlc_rows':int(len(full)),
        'full_ohlc_with_favorable':int(finite_fav.notna().sum()),
        'full_ohlc_with_adverse':int(finite_adv.notna().sum()),
        'full_ohlc_with_final':int(finite_final.notna().sum()),
        'move_holding_with_positive_excursion':int(((full.path_class=='MOVE_HOLDING') & finite_fav.gt(0)).sum()),
        'move_then_retrace_with_positive_excursion':int(((full.path_class=='MOVE_THEN_RETRACE') & finite_fav.gt(0)).sum()),
        'no_material_move_with_positive_excursion':int(((full.path_class=='NO_MATERIAL_MOVE') & finite_fav.gt(0)).sum()),
    }

    # Date coverage and rows with future observations.
    date_cov=o.groupby('trade_date').size().sort_index()
    symbol_cov=o.groupby('symbol').size().sort_values(ascending=False)

    summary={
      'status':'HISTORICAL_OUTCOME_AUDIT_COMPLETE',
      'cache_rows':int(len(c)), 'outcome_rows':int(len(o)),
      'cache_symbols':int(c.symbol.nunique()), 'outcome_symbols':int(o.symbol.nunique()),
      'cache_dates':int(c.trade_date.nunique()), 'outcome_dates':int(o.trade_date.nunique()),
      'duplicate_symbol_date_timestamp_groups':dup_groups,
      'duplicate_rows_in_duplicate_groups':dup_rows,
      'unique_symbol_date_pairs':int(c.groupby(['symbol','trade_date']).ngroups),
      'symbol_date_pairs_multiple_timestamps':multi_pairs,
      'path_class_counts':path_counts,
      'outcome_quality_counts':quality_counts,
      'anchor_direction_counts':direction_counts,
      'T_stats':t_stats,
      'classification_internal_checks':class_check,
      'date_min':str(o.trade_date.min()), 'date_max':str(o.trade_date.max()),
    }
    (out/'audit_summary.json').write_text(json.dumps(summary,indent=2,default=str),encoding='utf-8')
    pd.DataFrame({'trade_date':date_cov.index.astype(str),'outcome_rows':date_cov.values}).to_csv(out/'outcome_by_date.csv',index=False)
    pd.DataFrame({'symbol':symbol_cov.index,'outcome_rows':symbol_cov.values}).to_csv(out/'outcome_by_symbol.csv',index=False)
    pd.DataFrame([{'metric':k,'value':v} for k,v in summary.items() if not isinstance(v,(dict,list))]).to_csv(out/'audit_key_metrics.csv',index=False)
    print(json.dumps(summary,indent=2,default=str))

if __name__=='__main__': main()
