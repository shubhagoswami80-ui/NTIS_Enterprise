from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import ast
import csv
import json
import re
from typing import Any

V8_COLUMNS = (
    "orb_minutes","maturity","orb_dir","price_dir","fut_dir","option_dir",
    "fut_state","volume_state","ce_state","pe_state","pec_state",
    "fut_oi_state","ce_pct_state","pe_pct_state","pec_pct_state",
    "fut_pct_state","price_state","orb_agree","evidence_agreement",
    "persistent","strength_bucket","core_count_band","magnitude_count_band",
    "orb_fut_agree","orb_price_agree",
)

@dataclass(frozen=True)
class ParityReport:
    status: str
    matrix_path: str
    v8_source_path: str
    matrix_columns: list[str]
    v8_columns_found: list[str]
    missing_from_matrix: list[str]
    missing_from_source: list[str]
    source_constants: dict[str, Any]
    warnings: list[str]

def matrix_columns(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh).fieldnames or [])

def source_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def ast_names(path: Path) -> set[str]:
    tree = ast.parse(source_text(path), filename=str(path))
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}

def extract_literals(text: str, keys: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in keys:
        m = re.search(rf"\b{re.escape(key)}\s*=\s*([^\n#]+)", text)
        if m:
            out[key] = m.group(1).strip()
    return out

def inspect(matrix_path: Path, v8_source_path: Path) -> ParityReport:
    cols = matrix_columns(matrix_path)
    text = source_text(v8_source_path)
    names = ast_names(v8_source_path)

    # Structural evidence only. This function intentionally does not declare
    # semantic parity from column names alone.
    found = [c for c in V8_COLUMNS if c in text or c in names]
    missing_matrix = [c for c in V8_COLUMNS if c not in cols]
    missing_source = [c for c in V8_COLUMNS if c not in found]

    warnings = [
        "STRUCTURAL_ONLY",
        "COLUMN_PRESENCE_DOES_NOT_PROVE_EXACT_V8_SEMANTICS",
        "MANUAL_OR_TARGETED_SEMANTIC_REVIEW_REQUIRED",
    ]
    status = "PASS_STRUCTURAL" if not missing_matrix and not missing_source else "REVIEW_REQUIRED"

    return ParityReport(
        status=status,
        matrix_path=str(matrix_path),
        v8_source_path=str(v8_source_path),
        matrix_columns=cols,
        v8_columns_found=found,
        missing_from_matrix=missing_matrix,
        missing_from_source=missing_source,
        source_constants=extract_literals(
            text,
            ("ORB_MINUTES", "MATURITY_CUTS", "STRENGTH_BUCKETS",
             "PERSISTENCE", "PRICE_THRESHOLDS", "OI_THRESHOLDS"),
        ),
        warnings=warnings,
    )

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    matrix = root / "00_BASELINE" / "maturity_feature_matrix.csv"
    source = root / "01_RESEARCH_SOURCE" / "maturity_conditional_pattern_discovery_v8.py"
    report = inspect(matrix, source)
    out = root / "07_OUTPUT" / "v8_semantic_parity_structural_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"STATUS={report.status}")
    print(f"MATRIX_COLUMNS={len(report.matrix_columns)}")
    print(f"V8_COLUMNS_FOUND={len(report.v8_columns_found)}")
    print(f"MISSING_FROM_MATRIX={len(report.missing_from_matrix)}")
    print(f"MISSING_FROM_SOURCE={len(report.missing_from_source)}")
    print(f"REPORT={out}")
    return 0 if report.status == "PASS_STRUCTURAL" else 2

if __name__ == "__main__":
    raise SystemExit(main())
