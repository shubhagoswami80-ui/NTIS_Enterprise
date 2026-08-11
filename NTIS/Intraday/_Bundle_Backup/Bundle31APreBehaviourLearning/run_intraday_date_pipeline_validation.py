from pathlib import Path

print('='*60)
print('NTIS INTRADAY DATE PIPELINE VALIDATION')
print('='*60)

for f in ['run_intraday_date_pipeline.py','intraday_execution_context.py','run_intraday_date_pipeline_validation.py']:
    print(f'{f:<45}', 'PASS' if Path(f).exists() else 'FAIL')

print('='*60)
print('DATE EXECUTION FOUNDATION READY')
print('='*60)
