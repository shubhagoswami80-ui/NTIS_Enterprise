from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'03_LIVE_ADAPTER'))
sys.path.insert(0,str(ROOT/'02_FEATURE_ENGINE'))
from w73_live_ingestor import discover_files,read_workbook,build_pece_index
from w73_exact_v8_live_engine import build_exact_v8
D='2026-09-23'; M='September26'; SYMS=('BANDHANBNK','MOTILALOFS','POLICYBZR','RADICO','SAIL')
files=discover_files(D,M); pe=build_pece_index(D); rows=[]
for p,ts in files: rows.extend([r for r in read_workbook(p,ts,pe) if str(r.get('Symbol','')).strip().upper() in SYMS])
print('TOTAL_ROWS=',len(rows),'PECE_INDEX_FILES=',len(pe))
for maturity in ('09:45','10:00','10:15'):
 print('===',maturity,'===')
 for s in SYMS:
  sr=[r for r in rows if str(r.get('Symbol','')).strip().upper()==s]
  x=build_exact_v8(sr,symbol=s,trading_date=D,maturity=maturity,orb_minutes=15); f=x.feature_vector
  print(s,'STATUS=',x.status,'VARIANTS=',x.variants,'MISSING=',x.missing_fields,'PEC_NUM=',f.get('pec_num'),'PEC_PCT=',f.get('pec_pct'),'PEC_STATE=',f.get('pec_state'),'PEC_PCT_STATE=',f.get('pec_pct_state'),'OBS=',x.observation_timestamp,'WARNINGS=',x.warnings)
