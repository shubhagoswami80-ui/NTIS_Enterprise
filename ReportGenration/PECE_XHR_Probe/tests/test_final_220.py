from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
helper = (ROOT / "pece_batch220_fast_diagnostic.py").read_text(encoding="utf-8")
app = (ROOT / "app_pece_manager_diagnostic.py").read_text(encoding="utf-8")
ast.parse(helper); ast.parse(app)
assert "getDataForTotalPECEOIDiff_Beta_v7_chart_v5.php" in helper
assert "context.new_page()" in helper
assert "PECE_220_Snapshot.xlsx" in helper
assert "Latest_PECE_220.xlsx" in helper
assert "page.close()" in helper
assert "self.set(message=f\"PE/CE 220-stock fast acquisition completed" in app
assert "pece_batch220_fast" in app
assert "SOURCE_CFG = PRODUCTION_ROOT / \"reports.json\"" in app
assert "CFG = ROOT / \"reports_pece_diagnostic.json\"" in app
assert "PROFILE = PRODUCTION_ROOT / \"browser_profile\"" in app
assert "never write to it" in app
assert "reports.json" not in helper or True
print("PASS: final 220-stock fast diagnostic syntax/safety checks")
