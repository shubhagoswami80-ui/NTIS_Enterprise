from __future__ import annotations
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd


def find_cache(root: Path) -> Path:
    direct = root / 'canonical_strength_observations.csv'
    if direct.exists(): return direct
    hits = sorted(root.rglob('canonical_strength_observations.csv'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not hits: raise FileNotFoundError(f'CACHE_NOT_FOUND under {root}')
    return hits[0]


def num(s):
    return pd.to_numeric(s.astype(str).str.replace(',', '', regex=False).str.replace('−','-',regex=False).str.replace('%','',regex=False), errors='coerce')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--max-future', type=int, default=25)
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True, exist_ok=True)
    cache=Path(args.cache) if args.cache else find_cache(out.parent)
    print(f'CACHE_FOUND: {cache}')
    df=pd.read_csv(cache, low_memory=False)
    print(f'CACHE_ROWS: {len(df)}')
    required=['symbol','timestamp']
    miss=[c for c in required if c not in df.columns]
    if miss: raise RuntimeError(f'MISSING_COLUMNS: {miss}')
    df['timestamp']=pd.to_datetime(df['timestamp'], errors='coerce')
    df['symbol']=df['symbol'].astype(str).str.strip().str.upper()
    df=df.dropna(subset=['timestamp','symbol']).copy()
    df['trade_date']=df.get('trade_date', df['timestamp'].dt.date.astype(str)).astype(str)
    for c in ['open','high','low','close','price_chg','price_chg_pct']:
        if c not in df: df[c]=np.nan
        df[c]=num(df[c])
    # Reconstruct direction from numeric price change when possible; never infer from option/futures signs.
    df['derived_price_direction']=np.select([df['price_chg'].gt(0),df['price_chg'].lt(0)],['UP','DOWN'],default='UNKNOWN')
    df.loc[df['price_chg'].isna() & df['price_chg_pct'].gt(0),'derived_price_direction']='UP'
    df.loc[df['price_chg'].isna() & df['price_chg_pct'].lt(0),'derived_price_direction']='DOWN'
    # One row per symbol/date/timestamp, preferring complete OHLC then close then price change.
    df['quality']=df[['open','high','low','close']].notna().sum(axis=1)*10+df['close'].notna().astype(int)*2+df['price_chg'].notna().astype(int)
    df=df.sort_values(['symbol','trade_date','timestamp','quality'], ascending=[True,True,True,False])
    df=df.drop_duplicates(['symbol','trade_date','timestamp'], keep='first').reset_index(drop=True)
    print(f'TIMELINE_ROWS: {len(df)}')
    groups={}
    for key,g in df.groupby(['symbol','trade_date'], sort=False):
        g=g.sort_values('timestamp')
        groups[key]=g
    rows=[]
    for (sym,day),g in groups.items():
        arr=g.reset_index(drop=True)
        ts=arr['timestamp'].astype('int64').to_numpy()
        for i in range(len(arr)-1):
            a=arr.iloc[i]
            direction=a['derived_price_direction']
            future=arr.iloc[i+1:min(i+1+args.max_future,len(arr))]
            rec={'symbol':sym,'trade_date':day,'anchor_timestamp':a['timestamp'],'anchor_direction':direction,
                 'anchor_close':a['close'],'anchor_high':a['high'],'anchor_low':a['low'],
                 'future_observations':len(future)}
            if len(future)==0:
                rec.update(path_class='NO_FOLLOW_UP', outcome_quality='NONE')
            elif direction not in ('UP','DOWN'):
                rec.update(path_class='UNKNOWN_DIRECTION', outcome_quality='NONE')
            else:
                fc=future['close'].to_numpy(float); fh=future['high'].to_numpy(float); fl=future['low'].to_numpy(float)
                validc=fc[np.isfinite(fc)]; validh=fh[np.isfinite(fh)]; validl=fl[np.isfinite(fl)]
                base=a['close']
                # If OHLC path exists, calculate excursion. Otherwise use future direction as a lower-quality outcome.
                if np.isfinite(base) and (len(validc) or len(validh) or len(validl)):
                    hi=float(np.nanmax(validh)) if len(validh) else float(np.nanmax(validc))
                    lo=float(np.nanmin(validl)) if len(validl) else float(np.nanmin(validc))
                    denom=abs(float(base))
                    up=(hi-base)/denom*100 if denom else np.nan
                    dn=(base-lo)/denom*100 if denom else np.nan
                    favorable=up if direction=='UP' else dn
                    adverse=dn if direction=='UP' else up
                    last=float(validc[-1]) if len(validc) else np.nan
                    final=((last-base)/denom*100) if np.isfinite(last) and denom else np.nan
                    final_signed=final if direction=='UP' else -final
                    if favorable>0:
                        retrace=max(0.0, favorable-final_signed)
                        path='MOVE_THEN_RETRACE' if retrace>=favorable*0.5 else 'MOVE_HOLDING'
                    else: path='NO_MATERIAL_MOVE'
                    rec.update(max_high=hi,min_low=lo,favorable_exc_pct=favorable,adverse_exc_pct=adverse,final_move_signed_pct=final_signed,path_class=path,outcome_quality='FULL_OHLC' if len(validh) and len(validl) and len(validc) else 'CLOSE_PARTIAL')
                    for n in (1,2,3,5,10,20):
                        if len(future)>=n and np.isfinite(future.iloc[n-1]['close']) and denom:
                            mv=(future.iloc[n-1]['close']-base)/denom*100
                            rec[f'T{n}_signed_move_pct']=mv if direction=='UP' else -mv
                        else: rec[f'T{n}_signed_move_pct']=np.nan
                else:
                    dirs=future['derived_price_direction'].tolist()
                    same=sum(1 for d in dirs if d==direction)
                    opp=sum(1 for d in dirs if d in ('UP','DOWN') and d!=direction)
                    rec.update(path_class='DIRECTION_ONLY_CONTINUATION' if same>=1 else 'DIRECTION_ONLY_OPPOSITE',
                               outcome_quality='DIRECTION_ONLY',future_same_direction_count=same,future_opposite_count=opp)
            rows.append(rec)
    res=pd.DataFrame(rows)
    res.to_csv(out/'historical_anchor_outcomes.csv',index=False)
    summary={
      'status':'HISTORICAL_OUTCOME_RECONSTRUCTION_COMPLETE','cache_rows':int(len(df)),
      'outcome_rows':int(len(res)),'symbols':int(res.symbol.nunique()),'dates':int(res.trade_date.nunique()),
      'path_class_counts':res.path_class.value_counts(dropna=False).to_dict(),
      'outcome_quality_counts':res.outcome_quality.value_counts(dropna=False).to_dict(),
      'anchor_direction_counts':res.anchor_direction.value_counts(dropna=False).to_dict(),
      'full_ohlc_rows':int((res.outcome_quality=='FULL_OHLC').sum()),
      'direction_only_rows':int((res.outcome_quality=='DIRECTION_ONLY').sum()),
      'no_follow_up':int((res.path_class=='NO_FOLLOW_UP').sum()),
      'unknown_direction':int((res.path_class=='UNKNOWN_DIRECTION').sum()),
      'duplicate_symbol_date_timestamp_groups_removed':int(df.duplicated(['symbol','trade_date','timestamp']).sum())
    }
    (out/'research_summary.json').write_text(json.dumps(summary,indent=2,default=str),encoding='utf-8')
    print(json.dumps(summary,indent=2,default=str))

if __name__=='__main__': main()
