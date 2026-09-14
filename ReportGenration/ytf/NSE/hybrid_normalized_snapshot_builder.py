#!/usr/bin/env python3
"""
Build a normalized five-minute hybrid snapshot.

This stage:
- Reads the three supplementary workbook feeds and one NSE option-chain file.
- Adds source metadata.
- Normalizes common identity columns where possible.
- Keeps supplementary feeds as separate logical tables in one SQLite database.
- Stores NSE option-chain rows separately.
- Creates a cycle manifest linking all four source datasets.

It deliberately does NOT perform a potentially incorrect row-level join because
the supplementary workbooks and NSE option-chain have different granularities.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
import json
import pandas as pd


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=0)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported file: {path}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [
        str(c).strip().lower().replace("%", "pct").replace(" ", "_")
        for c in out.columns
    ]
    aliases = {
        "symbol": "symbol",
        "ticker": "symbol",
        "stock": "symbol",
        "expiry": "expiry",
        "strike": "strike",
        "price": "spot_price",
        "ltp": "ltp",
        "iv": "iv",
        "volume": "volume",
        "oi": "oi",
    }
    rename = {}
    for col in out.columns:
        if col in aliases and aliases[col] != col:
            rename[col] = aliases[col]
    return out.rename(columns=rename)


def write_table(conn, name, df):
    df.to_sql(name, conn, if_exists="replace", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle-start", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--trade-date", required=True)
    ap.add_argument("--expiry", default="")
    ap.add_argument("--daywise", required=True)
    ap.add_argument("--resistance", required=True)
    ap.add_argument("--support-resistance", required=True)
    ap.add_argument("--nse-option-chain", required=True)
    args = ap.parse_args()

    cycle = datetime.fromisoformat(args.cycle_start).replace(second=0, microsecond=0)
    cycle_id = cycle.strftime("%Y%m%d_%H%M")
    out_dir = Path(args.output_root) / args.trade_date / "normalized"
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / f"hybrid_{cycle_id}.sqlite"

    sources = {
        "supplementary_daywise": Path(args.daywise),
        "supplementary_resistance": Path(args.resistance),
        "supplementary_support_resistance": Path(args.support_resistance),
        "nse_option_chain": Path(args.nse_option_chain),
    }

    manifest = {
        "cycle_id": cycle_id,
        "cycle_start": cycle.strftime("%Y-%m-%d %H:%M:%S"),
        "trade_date": args.trade_date,
        "expiry": args.expiry,
        "database": str(db_path),
        "tables": {},
        "policy": {
            "source_tables_remain_separate": True,
            "no_false_granularity_join": True,
            "premium_skew_not_calculated": True,
        },
    }

    with sqlite3.connect(db_path) as conn:
        for table_name, path in sources.items():
            if not path.exists():
                raise FileNotFoundError(path)
            df = normalize_columns(read_table(path))
            df.insert(0, "cycle_id", cycle_id)
            df.insert(1, "cycle_start", cycle.strftime("%Y-%m-%d %H:%M:%S"))
            df.insert(2, "trade_date", args.trade_date)
            df.insert(3, "expiry_context", args.expiry)
            df.insert(4, "source_file", path.name)
            write_table(conn, table_name, df)
            manifest["tables"][table_name] = {
                "rows": len(df),
                "columns": len(df.columns),
                "source_file": path.name,
                "sqlite_table": table_name,
            }

        pd.DataFrame([{
            "cycle_id": cycle_id,
            "cycle_start": cycle.strftime("%Y-%m-%d %H:%M:%S"),
            "trade_date": args.trade_date,
            "expiry": args.expiry,
            "status": "NORMALIZED_SEPARATE_TABLES",
        }]).to_sql("cycle_manifest", conn, if_exists="replace", index=False)

    manifest_path = out_dir / f"hybrid_{cycle_id}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"SQLite database: {db_path}")
    print(f"Manifest: {manifest_path}")
    for name, info in manifest["tables"].items():
        print(f"{name}: {info['rows']} rows")


if __name__ == "__main__":
    main()
