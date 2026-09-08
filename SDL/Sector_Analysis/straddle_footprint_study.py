from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

PROJECT=Path(r'E:\NSE_Daily_Analysis'); SDL=PROJECT/'SDL'; DATA=SDL/'data'; SECTOR=SDL/'Sector_Analysis'
OUT=SECTOR/'.sector_intelligence'/'straddle_footprint_study'
SOURCES=[DATA/'output/early_prediction_research/first_22_point_in_time.csv',DATA/'output/early_prediction_futures_oi_v4_2_controlled/first_22_point_in_time_controlled.csv',DATA/'output/early_prediction_futures_oi_v4_2/first_22_point_in_time_futures_enriched.csv',DATA/'output/continuation_research/continuation_research_events.csv',DATA/'output/early_prediction_gate_audit/gate_audit_events.csv',DATA/'output/required_evidence']
CANONICAL=SECTOR/'.sector_intelligence'/'straddle_historical_research'/'canonical_observations.csv'
A={'symbol':['symbol','Symbol'],'date':['trading_date','Trading Date','date','Date'],'timestamp':['observation_timestamp','timestamp','Timestamp','datetime','DateTime'],'price':['price_chg_pct','Price Chg %','Price Chg (%)','Price chg (%)'],'volume':['volume_chg_pct','Volume Chg %','Volume Chg (%)'],'ce':['ce_oi_change','CE OI Change','Tol CE OI Chg'],'pe':['pe_oi_change','PE OI Change','Tol PE OI Chg'],'pc':['pe_ce_change','PE-CE OI Change','Tol PE-CE OI Chg'],'ce_pct':['ce_oi_change_pct','CE OI Change %','CE OI Chg %','Tol CE OI Chg %'],'pe_pct':['pe_oi_change_pct','PE OI Change %','PE OI Chg %','Tol PE OI Chg %'],'pc_pct':['pe_ce_change_pct','PE-CE OI Change %','PE-CE OI Chg %','Tol PE-CE OI Chg %'],'fstate':['futures_state','Future State','Futures State','Buildup','Futures Buildup'],'fchg':['futures_change','Futures Change','Future Change']}
def pick(d,ns):
 l={str(c).strip().lower():c for c in d.columns}
 for n in ns:
  if n in d.columns:return n
  if n.lower() in l:return l[n.lower()]
 return None
def norm(d,p):
 if d.empty:return pd.DataFrame()
 o=pd.DataFrame(index=d.index)
 for k,ns in A.items():
  c=pick(d,ns); o[k]=d[c] if c else pd.NA
 o['source_file']=str(p); o['source_family']=p.name;o['symbol']=o.symbol.astype('string').str.upper().str.strip();o['date']=pd.to_datetime(o.date,errors='coerce').dt.date;o['timestamp']=pd.to_datetime(o.timestamp,errors='coerce',format='mixed')
 for c in A:
  if c not in ('symbol','date','timestamp','fstate'):o[c]=pd.to_numeric(o[c].astype(str).str.replace(',','',regex=False).str.replace('%','',regex=False),errors='coerce')
 return o[o.symbol.notna()&o.symbol.ne('')]
def allpaths():
 r=[]
 for p in SOURCES:
  if p.is_file() and p.suffix.lower()=='.csv':r.append(p)
  elif p.is_dir():r+=list(p.rglob('*.csv'))
 if CANONICAL.exists():r.append(CANONICAL)
 return list(dict.fromkeys(r))
def main():
 OUT.mkdir(parents=True,exist_ok=True); frames=[]; diag=[]
 for p in allpaths():
  try:d=pd.read_csv(p,low_memory=False)
  except Exception:d=pd.DataFrame()
  diag.append({'source':str(p),'rows':len(d),'readable':not d.empty})
  if not d.empty:
   n=norm(d,p)
   if not n.empty:frames.append(n)
 pd.DataFrame(diag).to_csv(OUT/'source_diagnostics.csv',index=False)
 if not frames: print('NO_USABLE_HISTORICAL_ROWS');return
 d=pd.concat(frames,ignore_index=True).drop_duplicates();d['price_direction']=d.price.map(lambda x:'UP' if pd.notna(x) and x>0 else ('DOWN' if pd.notna(x) and x<0 else 'UNKNOWN'))
 def cls(r):
  opt=any(pd.notna(r[k]) for k in ('ce','pe','pc')); fut=str(r.fstate).upper().strip() in ('LB','SB','SC','LO')
  if opt and fut:return 'OPTION_AND_FUTURES'
  if opt:return 'OPTION_ONLY'
  if fut:return 'FUTURES_ONLY'
  if pd.notna(r.price) or pd.notna(r.volume):return 'PRICE_VOLUME_ONLY_OR_PARTIAL'
  return 'NO_FOOTPRINT'
 d['footprint_class']=d.apply(cls,axis=1);d['option_remarkable_gt999']=d[['ce','pe','pc']].abs().gt(999).any(axis=1);d['futures_remarkable_gt999']=d.fchg.abs().gt(999);d['remarkable_gt999']=d.option_remarkable_gt999|d.futures_remarkable_gt999;d['evidence_path']=d.footprint_class+' | PRICE_'+d.price_direction+' | FUT_'+d.fstate.fillna('').astype(str).str.upper()
 rows=[]
 for n,g in d.groupby('evidence_path',dropna=False):rows.append({'evidence_path':str(n),'observations':len(g),'symbols':g.symbol.nunique(),'trading_dates':g.date.nunique(),'timestamped':int(g.timestamp.notna().sum()),'remarkable_gt999':int(g.remarkable_gt999.sum())})
 d.to_csv(OUT/'observation_classification.csv',index=False);pd.DataFrame(rows).sort_values(['trading_dates','observations'],ascending=False).to_csv(OUT/'evidence_path_summary.csv',index=False)
 x=d.dropna(subset=['symbol','date','timestamp']).sort_values(['symbol','date','timestamp']); lead=[]
 for (s,day),g in x.groupby(['symbol','date'],sort=False):
  g=g.reset_index(drop=True)
  for i in range(len(g)-1):
   a,b=g.iloc[i],g.iloc[i+1]
   if pd.notna(a.price) and pd.notna(b.price):lead.append({'symbol':s,'date':day,'from_timestamp':a.timestamp,'to_timestamp':b.timestamp,'evidence_path':a.evidence_path,'price_before':a.price,'price_after':b.price,'price_delta':b.price-a.price,'futures_state':a.fstate,'remarkable_gt999':bool(a.remarkable_gt999)})
 pd.DataFrame(lead).to_csv(OUT/'chronological_lead_candidates.csv',index=False)
 meta={'status':'DISCOVERY_V2_COMPLETE','production_modified':False,'rows':len(d),'symbols':int(d.symbol.nunique()),'trading_dates':int(d.date.nunique()),'timestamped':int(d.timestamp.notna().sum()),'remarkable_gt999':int(d.remarkable_gt999.sum())};(OUT/'research_summary.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta,indent=2))
if __name__=='__main__':main()
