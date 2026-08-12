from pathlib import Path
import pandas as pd

HIST = Path('E:/NSE_Daily_Analysis/Historical_Data')
PRED = HIST / 'Predictions'
OUT = HIST / 'Outcomes'

pred_files = sorted(PRED.rglob('NTIS_Prediction_*.csv'))
out_files = sorted(OUT.rglob('NTIS_Outcome_*.csv'))
print('prediction files count', len(pred_files))
print('outcome files count', len(out_files))

first_pred = pred_files[0]
print('first prediction file', first_pred)
pred_df = pd.read_csv(first_pred)
print('prediction columns', list(pred_df.columns))
print('prediction sample rows', pred_df[['Symbol', 'Pattern', 'Pattern Reason', 'Confidence']].head(5).to_dict(orient='records'))

first_out = out_files[0]
print('first outcome file', first_out)
out_df = pd.read_csv(first_out)
print('outcome columns', list(out_df.columns))
print('outcome sample rows', out_df[['Symbol', 'Pattern', 'Pattern Reason', 'Outcome', 'Confidence']].head(5).to_dict(orient='records'))
print('outcome unique Outcome values', out_df['Outcome'].dropna().unique().tolist() if 'Outcome' in out_df.columns else [])
print('outcome unique Pattern values sample', out_df['Pattern'].dropna().unique()[:10].tolist() if 'Pattern' in out_df.columns else [])
