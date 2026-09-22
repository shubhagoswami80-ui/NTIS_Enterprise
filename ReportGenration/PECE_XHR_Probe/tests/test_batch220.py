from pathlib import Path
import ast, zipfile
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'app_pece_manager_diagnostic.py').read_text(encoding='utf-8')
helper=(ROOT/'pece_batch220_diagnostic.py').read_text(encoding='utf-8')
ast.parse(app); ast.parse(helper)
assert 'from pece_batch220_diagnostic import acquire_batch220' in app
assert 'if command == "pece_batch220":' in app
assert 'RUN PE/CE ALL 220 STOCKS' in app
assert 'TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"' in helper
assert 'ENDPOINT_MARKER = "getDataForTotalPECEOIDiff_Beta_v7_chart_v5.php"' in helper
assert '220' in helper
assert 'Latest_PECE_220.xlsx' in helper
assert 'sessionid' in helper.lower() and '[REDACTED]' in helper
assert 'reports.json' not in helper
print('PASS: PE/CE 220-stock final acquisition diagnostic validation')
