from __future__ import annotations
import json, os, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / '03_LIVE_ADAPTER'
DECISION = ROOT / '06_ALERTS'
for p in (ADAPTER, DECISION):
    if str(p) not in sys.path: sys.path.insert(0, str(p))

from w73_source_adapter import W73SourceAdapter, W73SourceConfig
from w73_point_in_time_cache import W73PointInTimeCache
from w73_live_decision_service import evaluate_latest_maturity, decision_summary


def _arg(name: str, default: str | None = None) -> str | None:
    import argparse
    return default


def run(month_folder: str, trading_date: str) -> dict:
    adapter = W73SourceAdapter(W73SourceConfig.from_environment())
    intervals = adapter.list_intervals(month_folder, trading_date)
    if not intervals:
        raise FileNotFoundError(f'No approved W73 interval XLSX files found for {month_folder}/{trading_date}')

    cache = W73PointInTimeCache()
    all_rows: list[dict] = []
    interval_reports = []
    for source in intervals:
        header, records = adapter.read_workbook(source.path)
        cache_path = cache.write_interval(source, trading_date, records)
        interval_reports.append({
            'timestamp': source.timestamp.isoformat(),
            'file': source.path.name,
            'records': len(records),
            'cache_path': str(cache_path),
        })
        for record in records:
            row = dict(record)
            row['_observation_timestamp'] = source.timestamp.isoformat()
            row['_source_file'] = source.path.name
            row['_trading_date'] = trading_date
            all_rows.append(row)

    asof, maturity, decisions = evaluate_latest_maturity(
        all_rows, trading_date=trading_date
    )
    summary = decision_summary(decisions)
    ready = [d for d in decisions if d.status == 'READY']
    qualified = [d for d in decisions if d.action == 'QUALIFIED']
    report = {
        'status': 'PASS_RUNTIME',
        'month_folder': month_folder,
        'trading_date': trading_date,
        'source_root': str(adapter.config.source_root),
        'interval_count': len(intervals),
        'latest_source_timestamp': intervals[-1].timestamp.isoformat(),
        'latest_source_file': intervals[-1].path.name,
        'pit_rows': len(all_rows),
        'asof': asof.isoformat() if asof else None,
        'latest_maturity_evaluated': maturity,
        'decision_summary': summary,
        'ready_count': len(ready),
        'qualified_count': len(qualified),
        'qualified_symbols': [d.symbol for d in qualified],
        'not_ready_samples': [
            {'symbol': d.symbol, 'missing_fields': list(d.missing_fields), 'warnings': list(d.warnings)}
            for d in decisions if d.action == 'NOT_READY'
        ][:10],
        'intervals': interval_reports,
    }
    out = ROOT / '07_OUTPUT' / 'real_source_runtime_validation_v1.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('month_folder')
    ap.add_argument('trading_date')
    args = ap.parse_args()
    r = run(args.month_folder, args.trading_date)
    print('STATUS=' + r['status'])
    print('TRADING_DATE=' + r['trading_date'])
    print('INTERVALS=' + str(r['interval_count']))
    print('LATEST=' + r['latest_source_timestamp'])
    print('PIT_ROWS=' + str(r['pit_rows']))
    print('MATURITY=' + str(r['latest_maturity_evaluated']))
    print('READY=' + str(r['ready_count']))
    print('QUALIFIED=' + str(r['qualified_count']))
    print('QUALIFIED_SYMBOLS=' + ','.join(r['qualified_symbols']))
    print('REPORT=' + str(ROOT / '07_OUTPUT' / 'real_source_runtime_validation_v1.json'))
