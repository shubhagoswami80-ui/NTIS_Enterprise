from __future__ import annotations
import argparse, json, re
from pathlib import Path
import pandas as pd

TARGETS = {
    "option_ce": ["ce oi"],
    "option_pe": ["pe oi"],
    "option_pe_ce": ["pe-ce oi", "pe ce oi"],
    "futures_oi": ["futures oi", "future oi"],
    "volume": ["volume chg", "volume change"],
}
STATE = ["buildup", "futures state", "future state", "futures buildup", "future buildup"]

def norm(x):
    return re.sub(r"\s+", " ", str(x).lower().replace("_", " ")).strip()

def is_percent(c):
    n = norm(c)
    return "%" in str(c) or "percent" in n or "percentage" in n

def clean_value(x):
    s = str(x).replace(",", "").replace("−", "-").strip()
    if s.endswith("%"): s = s[:-1].strip()
    try: return float(s)
    except: return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    root, out = Path(args.root), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows, files = [], sorted(root.rglob("*.xlsx"))
    for p in files:
        try: xl = pd.ExcelFile(p)
        except Exception: continue
        for sh in xl.sheet_names:
            try: df = pd.read_excel(p, sheet_name=sh, nrows=30)
            except Exception: continue
            for col in df.columns:
                n, role = norm(col), None
                for k, aliases in TARGETS.items():
                    if any(a in n for a in aliases):
                        role = k; break
                if not role and any(a in n for a in STATE): role = "futures_state"
                if not role: continue
                vals = df[col].dropna().head(10).tolist()
                nums = [v for v in (clean_value(x) for x in vals) if v is not None]
                rows.append({
                    "file": str(p), "sheet": sh, "physical_column": str(col),
                    "role": role, "is_percent": is_percent(col),
                    "sample_values": " | ".join(map(str, vals)),
                    "sample_numeric_min": min(nums) if nums else None,
                    "sample_numeric_max": max(nums) if nums else None
                })

    result = pd.DataFrame(rows).drop_duplicates()
    result.to_csv(out/"schema_column_inventory.csv", index=False)

    if not result.empty:
        compact = (result.groupby(["role","physical_column","is_percent"], dropna=False)
                   .agg(files=("file","nunique"), sheets=("sheet","nunique"),
                        sample=("sample_values","first"))
                   .reset_index()
                   .sort_values(["role","is_percent","physical_column"]))
        compact.to_csv(out/"schema_unique_columns.csv", index=False)

        checks = []
        for role in ["option_ce","option_pe","option_pe_ce","futures_oi","volume"]:
            r = result[result.role == role]
            checks.append({
                "role": role,
                "unique_columns": int(r.physical_column.nunique()),
                "percent_columns": int(r[r.is_percent].physical_column.nunique()),
                "number_columns": int(r[~r.is_percent].physical_column.nunique()),
                "example_columns": " | ".join(map(str, r.physical_column.drop_duplicates().head(12).tolist()))
            })
        r = result[result.role == "futures_state"]
        checks.append({
            "role":"futures_state",
            "unique_columns":int(r.physical_column.nunique()),
            "percent_columns":0, "number_columns":0,
            "example_columns":" | ".join(map(str,r.physical_column.drop_duplicates().head(12).tolist()))
        })
        pd.DataFrame(checks).to_csv(out/"schema_validation_summary.csv", index=False)

    meta = {
        "status":"SCHEMA_AUDIT_COMPLETE", "production_modified":False,
        "xlsx_scanned":len(files), "matched_rows":len(result),
        "outputs":["schema_column_inventory.csv","schema_unique_columns.csv","schema_validation_summary.csv"]
    }
    (out/"research_summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))

if __name__ == "__main__":
    main()
