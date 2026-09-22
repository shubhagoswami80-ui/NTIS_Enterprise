from pathlib import Path
import importlib.util

p = Path(__file__).resolve().parents[1] / "10_DOCS" / "orb_source_capability_audit_v1.py"
spec = importlib.util.spec_from_file_location("audit", p)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.norm("Price Chg %") == "price chg %"
assert m.find_col(["Symbol","Price Chg %"], ["Price Chg %"]) == "Price Chg %"
print("ORB source capability audit unit checks: PASS")
