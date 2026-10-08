from __future__ import annotations
import csv, hashlib, json, os, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
for p in (ROOT/'02_FEATURE_ENGINE',ROOT/'03_LIVE_ADAPTER'): sys.path.insert(0,str(p))
from w73_exact_v8_live_engine import build_exact_v8
from w73_live_ingestor import build_pece_index, discover_files, read_workbook, source_root
from w73_universe_engine import evaluate, load_config
MONTH=os.environ.get('NTIS_W73_SOURCE_MONTH','September26')
SOURCE_ROOT=Path(os.environ.get('NTIS_W73_SOURCE_ROOT',str(source_root())))
PECE_ROOT=Path(os.environ.get('NTIS_W73_PECE_SOURCE_ROOT',r'D:\My-data\Share_P&L\Ichart Data\Screenshot\PECE_Volume'))
DATES=['2026-09-23','2026-09-24','2026-09-25']; MATURITIES=['09:45','10:00','10:15']
REFERENCE={
('2026-09-23','09:45'):{'W73-A':{'SAIL'},'W73-B':set(),'NEXT-LAYER':set()},
('2026-09-23','10:00'):{'W73-A':{'SAIL'},'W73-B':{'UPL'},'NEXT-LAYER':set()},
('2026-09-23','10:15'):{'W73-A':{'SAIL'},'W73-B':set(),'NEXT-LAYER':set()},
('2026-09-24','09:45'):{'W73-A':set(),'W73-B':set(),'NEXT-LAYER':set()},
('2026-09-24','10:00'):{'W73-A':set(),'W73-B':set(),'NEXT-LAYER':set()},
('2026-09-24','10:15'):{'W73-A':set(),'W73-B':set(),'NEXT-LAYER':set()},
('2026-09-25','09:45'):{'W73-A':{'FORTIS','MAXHEALTH'},'W73-B':set(),'NEXT-LAYER':{'ZYDUSLIFE','RADICO'}},
('2026-09-25','10:00'):{'W73-A':{'ADANIPOWER'},'W73-B':set(),'NEXT-LAYER':set()},
('2026-09-25','10:15'):{'W73-A':{'ADANIPOWER'},'W73-B':set(),'NEXT-LAYER':{'ASIANPAINT'}}}

def sha256(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def ts(v):
 if isinstance(v,datetime): return v
 if v in (None,''): return None
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).replace(tzinfo=None)
 except:return None
def cutoff(day,mat):
 h,m=map(int,mat.split(':')); return datetime.fromisoformat(day).replace(hour=h,minute=m,second=0,microsecond=0)
def first_alerts(rows,asof,cfg):
 by=defaultdict(list)
 for r in rows:
  t=ts(r.get('_observation_timestamp'))
  if t and t<=asof: by[t.isoformat(timespec='seconds')].append(r)
 out={}
 for k in sorted(by):
  for d in evaluate(by[k],k,cfg):
   s=str(d.symbol).upper()
   if d.eligible and s not in out: out[s]={'timestamp':k,'filter_version':d.filter_version}
 return out
def classify(d):
 a=bool(d.variants.get('W73-A')); b=bool(d.variants.get('W73-B'))
 if d.status=='READY' and a:return 'W73-A'
 if d.status=='READY' and b:return 'W73-B'
 try:n=int(d.trajectory.get('px_negative_count_pre_maturity'))
 except:n=None
 f=d.feature_vector or {}
 if d.status=='READY' and not(a or b) and n is not None and n<=3 and (f.get('orb_agree')=='NO' or f.get('orb_price_agree')=='NO') and f.get('magnitude_count_band')=='0':return 'NEXT-LAYER'
 return 'NOT_READY' if d.status!='READY' else 'READY-NONMATCH'
def run_checkpoint(day,mat):
 asof=cutoff(day,mat); files=discover_files(day,MONTH,cutoff=asof)
 if not files: raise RuntimeError(f'NO_SOURCE_FILES: {day} <= {mat}')
 pece=build_pece_index(day); rows=[]; sm=[]
 for p,fts in files:
  sm.append({'file':str(p),'filename_timestamp':fts.isoformat(timespec='seconds'),'sha256':sha256(p),'size':p.stat().st_size,'created':datetime.fromtimestamp(p.stat().st_ctime).isoformat(timespec='seconds')})
  rows.extend(read_workbook(p,fts,pece))
 rows=[r for r in rows if (ts(r.get('_observation_timestamp')) or datetime.min)<=asof]
 alerts=first_alerts(rows,asof,load_config(ROOT/'07_OUTPUT'/'universe_config.json'))
 symbols=sorted({str(r.get('Symbol','')).strip().upper() for r in rows if r.get('Symbol')}); out=[]
 for s in symbols:
  sr=[r for r in rows if str(r.get('Symbol','')).strip().upper()==s and (ts(r.get('_observation_timestamp')) or datetime.min)<=asof]
  d=build_exact_v8(sr,symbol=s,trading_date=day,maturity=mat,orb_minutes=15); layer=classify(d)
  if layer in ('W73-A','W73-B','NEXT-LAYER'):
   fa=alerts.get(s); out.append({'date':day,'checkpoint':mat,'symbol':s,'first_alert':fa['timestamp'] if fa else 'MISSING','first_alert_filter_version':fa['filter_version'] if fa else 'MISSING','pit_asof':asof.isoformat(timespec='seconds'),'exact_v8':d.status,'layer':layer,'w73_a':bool(d.variants.get('W73-A')),'w73_b':bool(d.variants.get('W73-B')),'observation_timestamp':d.observation_timestamp,'source_files_used':len(sm),'future_data_excluded':True})
 actual={k:set() for k in ('W73-A','W73-B','NEXT-LAYER')}
 for r in out: actual[r['layer']].add(r['symbol'])
 exp=REFERENCE[(day,mat)]; val={k:('MATCH' if actual[k]==exp[k] else 'MISMATCH') for k in actual}
 return out,{'date':day,'checkpoint':mat,'pit_asof':asof.isoformat(timespec='seconds'),'source_root':str(SOURCE_ROOT),'pece_root':str(PECE_ROOT),'source_file_count':len(sm),'source_files':sm,'row_count':len(rows),'symbol_count':len(symbols),'first_alert_count':len(alerts),'actual_layers':{k:sorted(v) for k,v in actual.items()},'reference_layers':{k:sorted(v) for k,v in exp.items()},'validation':val,'overall_reference_match':all(v=='MATCH' for v in val.values()),'reference_is_non_authoritative':True,'cache_used':False,'future_data_excluded':True}
def main():
 outdir=ROOT/'08_TESTS'/'source_truth_acceptance_output'; outdir.mkdir(parents=True,exist_ok=True); allrows=[]; m={'run_started':datetime.now().isoformat(timespec='seconds'),'status':'RUNNING','mode':'RAW_SOURCE_DIRECT_ACCEPTANCE','cache_used':False,'source_root':str(SOURCE_ROOT),'pece_root':str(PECE_ROOT),'dates':DATES,'maturities':MATURITIES,'reference_is_non_authoritative':True,'checkpoints':[]}
 try:
  for day in DATES:
   for mat in MATURITIES:
    rows,meta=run_checkpoint(day,mat); allrows+=rows; m['checkpoints'].append(meta)
 except Exception as e:
  m['status']='FAIL';m['error']=repr(e);(outdir/'W73_SOURCE_TRUTH_ACCEPTANCE_MANIFEST.json').write_text(json.dumps(m,indent=2,default=str),encoding='utf-8');print('SOURCE_TRUTH_ACCEPTANCE=FAIL');print(repr(e));return 2
 m['status']='COMPLETE';m['run_finished']=datetime.now().isoformat(timespec='seconds');(outdir/'W73_SOURCE_TRUTH_ACCEPTANCE_MANIFEST.json').write_text(json.dumps(m,indent=2,default=str),encoding='utf-8')
 fields=['date','checkpoint','symbol','first_alert','first_alert_filter_version','pit_asof','exact_v8','layer','w73_a','w73_b','observation_timestamp','source_files_used','future_data_excluded']
 with (outdir/'W73_SOURCE_TRUTH_ACCEPTANCE_RESULTS.csv').open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(allrows)
 print('SOURCE_TRUTH_ACCEPTANCE=COMPLETE')
 for c in m['checkpoints']: print(f"{c['date']} {c['checkpoint']} | files={c['source_file_count']} rows={c['row_count']} symbols={c['symbol_count']} | A={','.join(c['actual_layers']['W73-A']) or '-'} | B={','.join(c['actual_layers']['W73-B']) or '-'} | NL={','.join(c['actual_layers']['NEXT-LAYER']) or '-'} | REF={'MATCH' if c['overall_reference_match'] else 'MISMATCH'}")
 print('MANIFEST='+str(outdir/'W73_SOURCE_TRUTH_ACCEPTANCE_MANIFEST.json'));print('RESULTS='+str(outdir/'W73_SOURCE_TRUTH_ACCEPTANCE_RESULTS.csv'));return 0
if __name__=='__main__':raise SystemExit(main())
