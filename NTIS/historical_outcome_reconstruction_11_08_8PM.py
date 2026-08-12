from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

BASE_DIR = Path('E:/NSE_Daily_Analysis')
PREDICTION_DIR = BASE_DIR / 'Historical_Data' / 'Predictions'
SOURCE_BASE = BASE_DIR / '2026'

MATCH_FIELDS = ['Symbol', 'Price Chg %', 'OI Chg %', 'PCR Chg %']
DATE_FORMATS = ['%d-%b-%Y', '%d-%b-%y', '%d/%m/%Y', '%Y-%m-%d']


@dataclass(frozen=True)
class ReconstructionResult:
    archive: str
    rows: int
    source_resolved: int
    source_unresolved: int
    evaluation_resolved: int
    evaluation_unresolved: int
    success: int
    failed: int
    no_trade: int
    unresolved: int
    return_min: Optional[float]
    return_max: Optional[float]


@dataclass(frozen=True)
class RowDetail:
    archive: str
    symbol: str
    source_date: Optional[str]
    entry_close: Optional[float]
    evaluation_date: Optional[str]
    evaluation_close: Optional[float]
    return_pct: Optional[float]
    outcome: str
    reason: str


def parse_date(value: Any) -> Optional[datetime]:
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = str(value).strip()
        if not text:
            return None
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    except Exception:
        pass
    return None


def normalized_match_key(row: pd.Series) -> Tuple[str, Optional[float], Optional[float], Optional[float]]:
    symbol = str(row.get('Symbol') or '').strip().upper()
    def parse_float(field: str) -> Optional[float]:
        if field not in row.index:
            return None
        value = row.get(field)
        if pd.isna(value):
            return None
        if isinstance(value, str):
            value = value.replace('%', '').replace(',', '').strip()
        try:
            return round(float(value), 2)
        except Exception:
            return None
    return (
        symbol,
        parse_float('Price Chg %'),
        parse_float('OI Chg %'),
        parse_float('PCR Chg %'),
    )


def load_source_rows() -> Dict[datetime, pd.DataFrame]:
    source_rows: Dict[datetime, pd.DataFrame] = {}
    for month_dir in sorted(SOURCE_BASE.iterdir()):
        if not month_dir.is_dir():
            continue
        source_dir = month_dir / '01_Price_OI'
        if not source_dir.exists():
            continue
        for source_file in sorted(source_dir.glob('*.xlsx')):
            try:
                df = pd.read_excel(source_file, sheet_name=0)
            except Exception:
                continue
            if 'Symbol' not in df.columns or any(field not in df.columns for field in MATCH_FIELDS[1:]):
                continue
            date = parse_source_date_from_filename(source_file.name)
            if date is None:
                continue
            if date in source_rows:
                source_rows[date] = pd.concat([source_rows[date], df], ignore_index=True)
            else:
                source_rows[date] = df.copy()
    return source_rows


def parse_source_date_from_filename(filename: str) -> Optional[datetime]:
    stem = Path(filename).stem
    parts = stem.replace('(', '_').replace(')', '_').split('_')
    ymd_date: Optional[datetime] = None
    fallback: Optional[datetime] = None
    for token in parts:
        token = token.strip()
        if not token:
            continue
        try:
            ymd_date = datetime.strptime(token, '%Y-%m-%d')
            break
        except ValueError:
            pass
        try:
            parsed = datetime.strptime(token, '%d%b%Y')
            if fallback is None:
                fallback = parsed
        except ValueError:
            pass
        try:
            parsed = datetime.strptime(token, '%d%b%y')
            if fallback is None:
                fallback = parsed
        except ValueError:
            pass
    return ymd_date or fallback


def build_source_index(source_rows: Dict[datetime, pd.DataFrame]) -> Dict[Tuple[str, Optional[float], Optional[float], Optional[float]], List[datetime]]:
    index: Dict[Tuple[str, Optional[float], Optional[float], Optional[float]], List[datetime]] = {}
    for date, df in source_rows.items():
        for _, row in df.iterrows():
            key = normalized_match_key(row)
            index.setdefault(key, []).append(date)
    return index


def resolve_source_date(row: pd.Series, source_index: Dict[Tuple[str, Optional[float], Optional[float], Optional[float]], List[datetime]]) -> Optional[datetime]:
    date_value = parse_date(row.get('Date'))
    if date_value is not None:
        return date_value
    return source_index.get(normalized_match_key(row), [None])[0]


def next_trading_date(source_date: datetime, available_dates: Sequence[datetime]) -> Optional[datetime]:
    later = [d for d in available_dates if d > source_date]
    return min(later) if later else None


def evaluate_row(row: pd.Series, source_rows: Dict[datetime, pd.DataFrame], source_index: Dict[Tuple[str, Optional[float], Optional[float], Optional[float]], List[datetime]], available_dates: List[datetime]) -> RowDetail:
    archive = row.get('_archive', '')
    symbol = str(row.get('Symbol') or '').strip()
    allocation = str(row.get('Signal') or '').strip().upper()
    source_date = resolve_source_date(row, source_index)
    if source_date is None:
        return RowDetail(archive, symbol, None, None, None, None, None, 'UNRESOLVED', 'no source date')

    source_df = source_rows.get(source_date)
    if source_df is None:
        return RowDetail(archive, symbol, None, None, None, None, None, 'UNRESOLVED', 'source row missing')

    match = source_df[source_df['Symbol'].astype(str).str.strip() == symbol]
    if match.empty:
        return RowDetail(archive, symbol, source_date.isoformat(), None, None, None, None, 'UNRESOLVED', 'symbol missing on source date')

    row_match = match.iloc[0]
    entry_close = _safe_float(row_match.get('Close'))
    if entry_close is None:
        return RowDetail(archive, symbol, source_date.isoformat(), None, None, None, None, 'UNRESOLVED', 'entry close missing')

    evaluation_date = next_trading_date(source_date, available_dates)
    if evaluation_date is None:
        return RowDetail(archive, symbol, source_date.isoformat(), entry_close, None, None, None, 'UNRESOLVED', 'no next trading date')

    next_df = source_rows.get(evaluation_date)
    if next_df is None:
        return RowDetail(archive, symbol, source_date.isoformat(), entry_close, evaluation_date.isoformat(), None, None, 'UNRESOLVED', 'next date missing')

    next_match = next_df[next_df['Symbol'].astype(str).str.strip() == symbol]
    if next_match.empty:
        return RowDetail(archive, symbol, source_date.isoformat(), entry_close, evaluation_date.isoformat(), None, None, 'UNRESOLVED', 'symbol missing on evaluation date')

    evaluation_close = _safe_float(next_match.iloc[0].get('Close'))
    if evaluation_close is None:
        return RowDetail(archive, symbol, source_date.isoformat(), entry_close, evaluation_date.isoformat(), None, None, 'UNRESOLVED', 'evaluation close missing')
    if entry_close == 0.0:
        return RowDetail(archive, symbol, source_date.isoformat(), entry_close, evaluation_date.isoformat(), evaluation_close, None, 'UNRESOLVED', 'entry close zero')

    return_pct = ((evaluation_close - entry_close) / entry_close) * 100
    outcome = _derive_outcome(allocation, return_pct)
    return RowDetail(
        archive,
        symbol,
        source_date.isoformat(),
        entry_close,
        evaluation_date.isoformat(),
        evaluation_close,
        return_pct,
        outcome,
        'resolved',
    )


def _safe_float(value: Any) -> Optional[float]:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _derive_outcome(signal: str, return_pct: float) -> str:
    if signal in {'BUY', 'STRONG BUY'}:
        return 'SUCCESS' if return_pct > 0 else 'FAILED'
    if signal in {'SELL', 'STRONG SELL'}:
        return 'SUCCESS' if return_pct < 0 else 'FAILED'
    if 'WAIT' in signal or 'NON-TRADE' in signal or signal == '':
        return 'NO TRADE'
    return 'UNRESOLVED'


def process_archives() -> Tuple[Sequence[ReconstructionResult], Sequence[RowDetail]]:
    source_rows = load_source_rows()
    available_dates = sorted(source_rows)
    source_index = build_source_index(source_rows)

    results: List[ReconstructionResult] = []
    details: List[RowDetail] = []
    for archive_file in sorted(PREDICTION_DIR.rglob('NTIS_Prediction_*.csv')):
        df = pd.read_csv(archive_file)
        df['_archive'] = archive_file.name
        archive_details: List[RowDetail] = []
        for _, row in df.iterrows():
            archive_details.append(evaluate_row(row, source_rows, source_index, available_dates))
        details.extend(archive_details)
        results.append(_summarize_archive(archive_file.name, archive_details))
    return results, details


def _summarize_archive(archive_name: str, detail_rows: Sequence[RowDetail]) -> ReconstructionResult:
    return_pcts = [r.return_pct for r in detail_rows if r.return_pct is not None]
    success = sum(1 for r in detail_rows if r.outcome == 'SUCCESS')
    failed = sum(1 for r in detail_rows if r.outcome == 'FAILED')
    no_trade = sum(1 for r in detail_rows if r.outcome == 'NO TRADE')
    unresolved = sum(1 for r in detail_rows if r.outcome == 'UNRESOLVED' or r.reason != 'resolved')
    source_resolved = sum(1 for r in detail_rows if r.source_date is not None)
    source_unresolved = len(detail_rows) - source_resolved
    evaluation_resolved = sum(1 for r in detail_rows if r.evaluation_date is not None)
    evaluation_unresolved = len(detail_rows) - evaluation_resolved
    return ReconstructionResult(
        archive=archive_name,
        rows=len(detail_rows),
        source_resolved=source_resolved,
        source_unresolved=source_unresolved,
        evaluation_resolved=evaluation_resolved,
        evaluation_unresolved=evaluation_unresolved,
        success=success,
        failed=failed,
        no_trade=no_trade,
        unresolved=unresolved,
        return_min=min(return_pcts) if return_pcts else None,
        return_max=max(return_pcts) if return_pcts else None,
    )


def summary_line(results: Sequence[ReconstructionResult]) -> str:
    total_rows = sum(r.rows for r in results)
    total_source_resolved = sum(r.source_resolved for r in results)
    total_source_unresolved = sum(r.source_unresolved for r in results)
    total_eval_resolved = sum(r.evaluation_resolved for r in results)
    total_eval_unresolved = sum(r.evaluation_unresolved for r in results)
    total_success = sum(r.success for r in results)
    total_failed = sum(r.failed for r in results)
    total_no_trade = sum(r.no_trade for r in results)
    total_unresolved = sum(r.unresolved for r in results)
    all_returns = [r for res in results for r in [res.return_min, res.return_max] if r is not None]
    return (
        f'ARCHIVES={len(results)} ROWS={total_rows} SOURCE_RESOLVED={total_source_resolved} SOURCE_UNRESOLVED={total_source_unresolved} '
        f'EVALUATION_RESOLVED={total_eval_resolved} EVALUATION_UNRESOLVED={total_eval_unresolved} '
        f'SUCCESS={total_success} FAILED={total_failed} NO_TRADE={total_no_trade} UNRESOLVED={total_unresolved} '
        f'RETURN_MIN={min(all_returns) if all_returns else None} RETURN_MAX={max(all_returns) if all_returns else None}'
    )


def colpal_verification(details: Sequence[RowDetail]) -> Optional[str]:
    for row in details:
        if row.symbol == 'COLPAL':
            return (
                f'{row.archive} | {row.source_date or "UNRESOLVED"} | {row.entry_close or "UNRESOLVED"} | '
                f'{row.evaluation_date or "UNRESOLVED"} | {row.evaluation_close or "UNRESOLVED"} | '
                f'{round(row.return_pct,4) if row.return_pct is not None else "UNRESOLVED"} | {row.outcome}'
            )
    return None


def main() -> None:
    results, details = process_archives()
    print(summary_line(results))
    verify = colpal_verification(details)
    if verify:
        print('COLPAL:', verify)
    unresolved = sum(1 for r in details if r.outcome == 'UNRESOLVED' or r.reason != 'resolved')
    print('UNRESOLVED_ROWS=', unresolved)


if __name__ == '__main__':
    main()
