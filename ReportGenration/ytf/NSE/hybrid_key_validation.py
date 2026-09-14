#!/usr/bin/env python3
"""
Validate and prepare join keys for a synchronized hybrid five-minute cycle.

This layer does not calculate Premium Skew. It checks whether the available
sources contain sufficient, reliable identity fields for a later analytical
join. It never invents missing symbol, expiry, strike, or timestamp values.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=0)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".sqlite", ".db"}:
        with sqlite3.connect(path) as con:
            return pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table'", con
            )
    raise ValueError(f"Unsupported input: {path}")


def find_column(df, names):
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def inspect_source(path: Path, source_name: str):
    df = read_table(path)
    symbol_col = find_column(df, ["symbol", "ticker", "stock"])
    expiry_col = find_column(df, ["expiry", "expiry_date", "expiration"])
    strike_col = find_column(df, ["strike", "strike_price"])
    timestamp_col = find_column(
        df, ["feed_timestamp", "timestamp", "datetime", "time", "cycle_start"]
    )

    result = {
        "source": source_name,
        "file": path.name,
        "rows": len(df),
        "columns": len(df.columns),
        "symbol_column": symbol_col or "",
        "expiry_column": expiry_col or "",
        "strike_column": strike_col or "",
        "timestamp_column": timestamp_col or "",
        "symbol_present": bool(symbol_col),
        "expiry_present": bool(expiry_col),
        "strike_present": bool(strike_col),
        "timestamp_present": bool(timestamp_col),
        "duplicate_symbol_count": None,
        "blank_symbol_count": None,
        "duplicate_key_count": None,
        "status": "CHECKED",
        "warnings": [],
    }

    if symbol_col:
        symbols = df[symbol_col].astype("string").str.strip().str.upper()
        result["blank_symbol_count"] = int(symbols.isna().sum() + (symbols == "").sum())
        result["duplicate_symbol_count"] = int(symbols.duplicated(keep=False).sum())
        if result["blank_symbol_count"]:
            result["warnings"].append("blank_symbols_present")
    else:
        result["warnings"].append("symbol_key_missing")

    if expiry_col:
        if df[expiry_col].isna().any():
            result["warnings"].append("blank_expiry_values_present")
    else:
        result["warnings"].append("expiry_key_missing")

    if strike_col:
        if df[strike_col].isna().any():
            result["warnings"].append("blank_strike_values_present")
    else:
        result["warnings"].append("strike_key_missing")

    if timestamp_col:
        parsed = pd.to_datetime(df[timestamp_col], errors="coerce")
        if parsed.isna().any():
            result["warnings"].append("unparseable_timestamps_present")
    else:
        result["warnings"].append("timestamp_key_missing")

    # A complete option-level key requires symbol, expiry, strike and timestamp.
    if all(result[k] for k in [
        "symbol_column", "expiry_column", "strike_column", "timestamp_column"
    ]):
        keys = pd.DataFrame({
            "symbol": df[symbol_col].astype("string").str.strip().str.upper(),
            "expiry": df[expiry_col].astype("string").str.strip().str.upper(),
            "strike": df[strike_col].astype("string").str.strip(),
            "timestamp": pd.to_datetime(df[timestamp_col], errors="coerce"),
        })
        result["duplicate_key_count"] = int(keys.duplicated(keep=False).sum())
        if result["duplicate_key_count"]:
            result["warnings"].append("duplicate_option_keys_present")

    if result["warnings"]:
        result["status"] = "WARNINGS"
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--cycle-start", required=True)
    ap.add_argument("--daywise", required=True)
    ap.add_argument("--resistance", required=True)
    ap.add_argument("--support-resistance", required=True)
    ap.add_argument("--nse-option-chain", required=True)
    args = ap.parse_args()

    cycle = datetime.fromisoformat(args.cycle_start).replace(second=0, microsecond=0)
    cycle_id = cycle.strftime("%Y%m%d_%H%M")
    out_dir = Path(args.output_root) / cycle.strftime("%Y-%m-%d") / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = [
        ("daywise", Path(args.daywise)),
        ("resistance", Path(args.resistance)),
        ("support_resistance", Path(args.support_resistance)),
        ("nse_option_chain", Path(args.nse_option_chain)),
    ]

    reports = []
    for name, path in inputs:
        if not path.exists():
            reports.append({
                "source": name, "file": str(path), "status": "MISSING",
                "warnings": ["file_not_found"]
            })
            continue
        try:
            reports.append(inspect_source(path, name))
        except Exception as exc:
            reports.append({
                "source": name, "file": str(path), "status": "READ_ERROR",
                "warnings": [str(exc)]
            })

    required_sources_ok = all(r["status"] not in {"MISSING", "READ_ERROR"} for r in reports)
    nse = next((r for r in reports if r["source"] == "nse_option_chain"), {})
    option_key_ready = all(nse.get(k, False) for k in [
        "symbol_present", "expiry_present", "strike_present", "timestamp_present"
    ])

    summary = {
        "cycle_id": cycle_id,
        "cycle_start": cycle.strftime("%Y-%m-%d %H:%M:%S"),
        "required_sources_readable": required_sources_ok,
        "nse_option_key_ready": option_key_ready,
        "ready_for_schema_specific_join": bool(required_sources_ok and option_key_ready),
        "reports": reports,
        "policy": {
            "no_missing_keys_invented": True,
            "no_premium_skew_calculated": True,
            "supplementary_sources_not_treated_as_option_chain": True,
            "warnings_require_review": True,
        },
    }

    json_path = out_dir / f"key_validation_{cycle_id}.json"
    csv_path = out_dir / f"key_validation_{cycle_id}.csv"
    json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(reports).to_csv(csv_path, index=False)

    print(f"Cycle: {cycle_id}")
    print(f"Readable sources: {required_sources_ok}")
    print(f"NSE option key ready: {option_key_ready}")
    print(f"Ready for schema-specific join: {summary['ready_for_schema_specific_join']}")
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
