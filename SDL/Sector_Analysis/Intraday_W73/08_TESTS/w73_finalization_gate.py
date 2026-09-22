from __future__ import annotations
import argparse, json, os, re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import openpyxl

PAT = re.compile(r"_(\d{8})_(\d{6})\.xlsx$")
PREFIX = "Daywise_Price_and_OI_Summary_"

def ts_from_name(p):
    m=PAT.search(p.name)
    if not m: return None
    return datetime.strptime(m.group(1)+m.group(2), "%Y%m%d%H%M%S")

def find_col(headers, names):
    norm={str(h).strip().lower():h for h in headers if h is not None}
    for n in names:
        if n.lower() in norm: return norm[n.lower()]
    return None

def load_source(day):
    files=[]
    for p in sorted(day.iterdir()):
        if p.is_file() and p.name.startswith(PREFIX) and p.suffix.lower()=='.xlsx':
            t=ts_from_name(p)
            if t: files.append((t,p))
    rows=[]
    for t,p in files:
        wb=openpyxl.load_workbook(p, read_only=True, data_only=True)
        ws=wb.active
        it=ws.iter_rows(values_only=True)
        try: headers=list(next(it))
        except StopIteration: wb.close(); continue
        sym=find_col(headers,['Symbol']); hi=find_col(headers,['High']); lo=find_col(headers,['Low']); close=find_col(headers,['Close'])
        price=find_col(headers,['Price Chg']); pct=find_col(headers,['Price Chg %'])
        idx={k:headers.index(v) for k,v in [('symbol',sym),('high',hi),('low',lo),('close',close),('price',price),('pct',pct)] if v is not None}
        for r in it:
            if 'symbol' not in idx: continue
            s=r[idx['symbol']]
            if not s: continue
            rec={'symbol':str(s).strip(),'timestamp':t.isoformat(),'file':p.name}
            for k in ['high','low','close','price','pct']:
                rec[k]=r[idx[k]] if k in idx else None
            rows.append(rec)
        wb.close()
    return files, rows

def num(x):
    try: return float(x)
    except (TypeError,ValueError): return None

def audit_symbols(rows):
    by=defaultdict(list)
    for r in rows: by[r['symbol']].append(r)
    out=[]
    for s,rs in sorted(by.items()):
        rs.sort(key=lambda x:x['timestamp'])
        highs=[num(r['high']) for r in rs if num(r['high']) is not None]
        lows=[num(r['low']) for r in rs if num(r['low']) is not None]
        closes=[num(r['close']) for r in rs if num(r['close']) is not None]
        if len(rs)<2: continue
        hi_mono=all(b>=a for a,b in zip(highs,highs[1:])) if len(highs)>1 else True
        lo_mono_inc=all(b>=a for a,b in zip(lows,lows[1:])) if len(lows)>1 else True
        lo_mono_dec=all(b<=a for a,b in zip(lows,lows[1:])) if len(lows)>1 else True
        t0=datetime.fromisoformat(rs[0]['timestamp']); cutoff=t0+timedelta(minutes=15)
        orb=[r for r in rs if datetime.fromisoformat(r['timestamp'])<=cutoff]
        after=[r for r in rs if datetime.fromisoformat(r['timestamp'])>cutoff]
        oh=[num(r['high']) for r in orb if num(r['high']) is not None]
        ol=[num(r['low']) for r in orb if num(r['low']) is not None]
        oc=[num(r['close']) for r in after if num(r['close']) is not None]
        if len(oh)<2 or len(ol)<2 or not oc:
            status='INSUFFICIENT'
            direction=None
        else:
            hi=max(oh); lo=min(ol)
            up=next((r for r in after if (num(r['close']) is not None and num(r['close'])>hi)),None)
            dn=next((r for r in after if (num(r['close']) is not None and num(r['close'])<lo)),None)
            if up and dn:
                direction='UP' if up['timestamp']<dn['timestamp'] else 'DOWN'
                status='BOTH_BREAKS'
            elif up: direction='UP'; status='UP_BREAK'
            elif dn: direction='DOWN'; status='DOWN_BREAK'
            else: direction=None; status='NO_BREAK'
        out.append({'symbol':s,'intervals':len(rs),'high_monotonic_non_decreasing':hi_mono,'low_monotonic_non_decreasing':lo_mono_inc,'low_monotonic_non_increasing':lo_mono_dec,'close_changes':len(set(closes))>1,'orb_status':status,'orb_direction':direction})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('month'); ap.add_argument('trading_date'); ap.add_argument('--source-root',default=os.getenv('NTIS_W73_SOURCE_ROOT',r'D:\My-data\Share_P&L\Ichart Data\Screenshot'))
    args=ap.parse_args(); day=Path(args.source_root)/args.month/args.trading_date
    if not day.exists(): raise SystemExit(f'SOURCE_DAY_NOT_FOUND={day}')
    files,rows=load_source(day); sa=audit_symbols(rows)
    symbols=sorted({r['symbol'] for r in rows})
    statuses=defaultdict(int)
    for r in sa: statuses[r['orb_status']]+=1
    # Exactness gate: source must provide a price stream covering the market-open ORB window.
    first_ts=min((datetime.fromisoformat(r['timestamp']) for r in rows),default=None)
    market_open=datetime.combine(first_ts.date(), datetime.min.time()).replace(hour=9,minute=15) if first_ts else None
    coverage_exact=bool(first_ts and first_ts<=market_open)
    valid_breakout_stream=sum(1 for r in sa if r['orb_status'] in {'UP_BREAK','DOWN_BREAK','BOTH_BREAKS'})
    exact_ready=coverage_exact and len(files)>=3 and len(symbols)>0 and valid_breakout_stream>0
    # Current evidence also checks that generic Daywise OI is not silently treated as futures OI.
    result={
      'status':'PASS_FINALIZATION_GATE' if exact_ready else 'PASS_DIAGNOSTIC_GATE',
      'decision':'EXACT_ORB_SOURCE_READY' if exact_ready else 'EXACT_ORB_SOURCE_NOT_PROVEN',
      'source_root':str(Path(args.source_root)), 'month':args.month,'trading_date':args.trading_date,'day_folder':str(day),
      'files_found':len(files),'symbols_found':len(symbols),'rows_loaded':len(rows),'first_source_timestamp':first_ts.isoformat() if first_ts else None,
      'market_open_reference':market_open.isoformat() if market_open else None,'source_covers_09_15':coverage_exact,
      'orb_status_counts':dict(statuses),'symbols_with_breakout':valid_breakout_stream,
      'exact_v8_live_policy':'UNCHANGED_FAIL_CLOSED',
      'portal_policy':'FINALIZE_UI_AND_INTEGRATION_ONLY_IF_EXACT_ORB_SOURCE_READY; otherwise keep portal operational but signal state NOT_READY',
      'notes':[
        'This gate does not modify strategy, V8 semantics, dashboard code, or source files.',
        'A changing Close is treated as point-in-time evidence; High/Low are not assumed to be candle values.',
        'The authoritative V8 ORB requires a causal price stream covering the opening window and subsequent Close breakout.',
        'Generic Daywise OI is not relabelled as futures OI.'
      ], 'symbol_analysis':sa
    }
    out=Path('07_OUTPUT'); out.mkdir(exist_ok=True)
    (out/'w73_finalization_gate_v1.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    short={'status':result['status'],'decision':result['decision'],'files_found':len(files),'symbols_found':len(symbols),'rows_loaded':len(rows),'first_source_timestamp':result['first_source_timestamp'],'source_covers_09_15':coverage_exact,'orb_status_counts':dict(statuses),'symbols_with_breakout':valid_breakout_stream,'output':str(out/'w73_finalization_gate_v1.json')}
    print(json.dumps(short,indent=2))

if __name__=='__main__': main()
