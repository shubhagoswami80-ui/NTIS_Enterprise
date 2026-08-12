from pathlib import Path
import pandas as pd
import datetime
from similarity_core_clean.integration.historical_pattern_intelligence import HistoricalPatternIntelligence

HIST = Path('E:/NSE_Daily_Analysis/Historical_Data')
PRED = HIST / 'Predictions'
OUT = HIST / 'Outcomes'

pred_files = sorted(PRED.rglob('NTIS_Prediction_*.csv'))
out_files = sorted(OUT.rglob('NTIS_Outcome_*.csv'))

pred_names = {p.relative_to(PRED).as_posix(): p for p in pred_files}
out_names = {o.relative_to(OUT).as_posix(): o for o in out_files}

pairs = []
unmatched_preds = []
unmatched_out = []
records = []
no_trade_count = 0
raw_prediction_rows = 0

def date_from_token(tok):
    return datetime.datetime.strptime(tok, '%d%b%Y').date().isoformat()

for rel, pred in pred_names.items():
    token = pred.stem.replace('NTIS_Prediction_', '')
    outp = OUT / Path(rel).parent / f'NTIS_Outcome_{token}.csv'
    if outp.exists():
        pairs.append((pred, outp))
    else:
        unmatched_preds.append(pred)

for rel, out in out_names.items():
    token = out.stem.replace('NTIS_Outcome_', '')
    predp = PRED / Path(rel).parent / f'NTIS_Prediction_{token}.csv'
    if not predp.exists():
        unmatched_out.append(out)

for pred, out in pairs:
    try:
        pdf = pd.read_csv(pred)
    except Exception:
        continue
    if 'Symbol' not in pdf.columns:
        continue
    raw_prediction_rows += len(pdf)
    try:
        outdf = pd.read_csv(out)
    except Exception:
        outdf = None

    if outdf is not None and 'Symbol' in outdf.columns:
        outcome_cols = [c for c in ['Outcome', 'Actual Return %', 'Model Accuracy %', 'Pattern', 'Pattern Reason', 'Confidence'] if c in outdf.columns]
        merged = pdf.merge(outdf[['Symbol'] + outcome_cols], on='Symbol', how='left')
    else:
        merged = pdf.copy()
        merged['Outcome'] = None
        merged['Actual Return %'] = None
        merged['Model Accuracy %'] = None

    date_token = pred.stem.replace('NTIS_Prediction_', '')
    date_iso = date_from_token(date_token)

    for _, row in merged.iterrows():
        symbol = str(row.get('Symbol') or '').strip()
        pattern = str(row.get('Pattern') or '').strip()
        if not pattern and 'Pattern_OUTCOME' in row.index:
            pattern = str(row.get('Pattern_OUTCOME') or '').strip()

        outcome = row.get('Outcome') if row.get('Outcome') == row.get('Outcome') else ''
        outcome = str(outcome).strip()
        if outcome.upper() == 'SUCCESS':
            wins, losses, pending = 1, 0, 0
        elif outcome.upper() == 'FAILED':
            wins, losses, pending = 0, 1, 0
        elif outcome.upper() == 'PENDING':
            wins, losses, pending = 0, 0, 1
        elif outcome.upper() == 'NO TRADE':
            wins, losses, pending = 0, 0, 1
            no_trade_count += 1
        elif outcome == '':
            wins, losses, pending = 0, 0, 1
        else:
            wins, losses, pending = 0, 0, 1

        try:
            actual_return = float(row.get('Actual Return %')) if row.get('Actual Return %') == row.get('Actual Return %') else None
        except Exception:
            actual_return = None
        try:
            confidence = float(row.get('Confidence')) if row.get('Confidence') == row.get('Confidence') else 0.0
        except Exception:
            confidence = 0.0

        if wins + losses > 0 and actual_return is None:
            average_return = 0.0
        elif wins + losses > 0:
            average_return = actual_return
        else:
            average_return = 0.0

        record = {
            'symbol': symbol,
            'business_pattern_id': f'{symbol}|{pattern}|{date_iso}',
            'pattern_classification': pattern,
            'pattern_dna': str(row.get('Pattern Reason') or ''),
            'fingerprint_version': '1.0',
            'first_seen': date_iso,
            'last_seen': date_iso,
            'occurrences': 1,
            'wins': wins,
            'losses': losses,
            'pending': pending,
            'success_rate': 1.0 if wins == 1 else 0.0,
            'average_return': average_return,
            'confidence': confidence,
            'lifecycle_status': 'HISTORICAL',
            'normalized_features': {'symbol': symbol, 'date': date_iso, 'confidence': confidence},
            'evidence_vector': {},
            'historical_outcome': outcome,
        }
        records.append(record)

aggregated = HistoricalPatternIntelligence()._aggregate_records(records)
unique_profiles = len(aggregated)
occurrences = sum(r['occurrences'] for r in aggregated)
wins = sum(r['wins'] for r in aggregated)
losses = sum(r['losses'] for r in aggregated)
pending = sum(r['pending'] for r in aggregated)
resolved = wins + losses
resolved_rows = [r for r in records if r['wins'] + r['losses'] > 0]
resolved_nonzero = [r for r in resolved_rows if abs(r['average_return']) > 1e-12]
avg_return_resolved = sum(r['average_return'] for r in resolved_rows) / len(resolved_rows) if resolved_rows else 0.0
success_rate_resolved = wins / resolved if resolved > 0 else 0.0
profiles = sorted(aggregated, key=lambda r: (-r['occurrences'], r['symbol'], r['pattern_classification']))
profiles_wins = sorted(aggregated, key=lambda r: (-r['wins'], -r['occurrences']))
profiles_sr = sorted([r for r in aggregated if (r['wins'] + r['losses']) >= 2], key=lambda r: (-(r['wins'] / (r['wins'] + r['losses']) if (r['wins'] + r['losses']) > 0 else 0), -r['wins'], -r['occurrences']))

print('prediction_files', len(pred_files))
print('outcome_files', len(out_files))
print('matched_pairs', len(pairs))
print('unmatched_prediction_files', len(unmatched_preds))
print('unmatched_outcome_files', len(unmatched_out))
print('raw_prediction_rows', raw_prediction_rows)
print('raw_matched_symbol_observations', len(records))
print('unique_profiles', unique_profiles)
print('total_occurrences', occurrences)
print('resolved_occurrences', resolved)
print('wins', wins)
print('losses', losses)
print('pending', pending)
print('no_trade_count', no_trade_count)
print('success_rate_resolved', success_rate_resolved)
print('avg_return_resolved', avg_return_resolved)
print('resolved_nonzero_count', len(resolved_nonzero))
print('top10_occurrences', [(r['symbol'], r['pattern_classification'], r['occurrences']) for r in profiles[:10]])
print('top10_wins', [(r['symbol'], r['pattern_classification'], r['wins']) for r in profiles_wins[:10]])
print('top10_success_rate', [(r['symbol'], r['pattern_classification'], r['wins'], r['losses'], float(r['wins']) / (r['wins'] + r['losses']) if (r['wins'] + r['losses']) > 0 else 0) for r in profiles_sr[:10]])
