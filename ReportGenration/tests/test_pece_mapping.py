from __future__ import annotations

import json
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "pece_xhr_golive_engine.py"

spec = importlib.util.spec_from_file_location("pece_engine", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

assert len(mod.REPORT_HEADERS) == 37
assert len(mod.PACKED_PAIRS) == 6

sample = [
    "15:40",
    "23500.00:#17CE06",
    "16:0.07",
    "18.7:0.08",
    "23397.92",
    "11.02",
    885,
    277037,
    "-4959:-1.76:red",
    "229:0.08:",
    1346074,
    1136334,
    "-209740:red",
    "28177:red",
    "29060:#4CAF50",
    "0.84:",
    "1132688.2307692:#FFEBEB",
    "1150857.3076923:green",
    "1.02:#4CAF50",
    "18170:green",
    0.8,
    "53295:#FFEBEB",
    "74333:green",
    3.96,
    6.54,
    "1.39:#4CAF50",
    "21038:green",
    0.92,
    "-1608:-0.14",
    "797:0.07",
    2405,
]

mapped = mod._map_source_row(sample)

assert len(mapped) == 37
assert mapped[0] == "15:40"
assert mapped[1] == "23500.00"
assert mapped[2:6] == ["16", "0.07", "18.7", "0.08"]
assert mapped[10:14] == ["-4959", "-1.76", "229", "0.08"]
assert mapped[32:36] == ["-1608", "-0.14", "797", "0.07"]
assert str(mapped[36]) == "2405"

# No color/presentation metadata may survive in report values.
assert "#17CE06" not in mapped[1]
assert "red" not in " ".join(str(x) for x in mapped)

# Time must not be split.
assert ":" in mapped[0]

# Validate a representative DataTables payload with the exact native width.
payload = json.dumps({"aaData": [sample]})
ok, reason, count, obj = mod.validate_payload(payload)
assert ok and reason == "ok" and count == 1 and obj is not None

# Reject incorrect source widths rather than silently fabricating columns.
bad = json.dumps({"aaData": [sample[:-1]]})
ok, reason, count, obj = mod.validate_payload(bad)
assert not ok and "unexpected_source_width" in reason

# Verify flattened output uses the full report schema.
result = {
    "symbol": "NIFTYNXT50",
    "valid": True,
    "object": {"aaData": [sample]},
}
rows = mod._flatten_rows([result], "20260911_201059")
assert len(rows) == 1
assert list(rows[0].keys())[:37] == mod.REPORT_HEADERS
assert rows[0]["Time"] == "15:40"
assert rows[0]["Fut Price"] == "23500.00"
assert str(rows[0]["OI ChgTrend"]) == "2405"
assert rows[0]["Symbol"] == "NIFTYNXT50"

print("PASS: PE/CE 31-to-37 mapping, Time preservation, schema, payload-width validation, and flattening tests")
