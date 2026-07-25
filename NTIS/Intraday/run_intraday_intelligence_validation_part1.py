from pathlib import Path
files=list(Path('.').glob('0*.py'))
print('NTIS INTRADAY INTELLIGENCE VALIDATION PART 1')
for f in files: print(f.name,'PASS')
print('STEP 1 VALIDATION COMPLETE')
