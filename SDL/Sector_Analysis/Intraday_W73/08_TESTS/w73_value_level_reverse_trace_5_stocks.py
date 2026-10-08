"""
NTIS W73 — VALUE-LEVEL 5-STOCK REVERSE TRACE
================================================
Controlled, read-only diagnostic.

Purpose:
Trace actual numeric/raw values through:
RAW XLSX -> PIT CACHE -> Exact-V8 feature construction -> W73-A/W73-B.

It does NOT:
- modify raw XLSX
- modify PIT cache
- modify W73 strategy code
- modify dashboard
- use post-cutoff observations for a decision
- treat missing as zero

Output:
08_TESTS\controlled_validation_output\
  W73_VALUE_TRACE_<date>.csv
  W73_VALUE_TRACE_<date>.json

The trace intentionally records exact values where the current runtime exposes them.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for p in (
    ROOT / "03_LIVE_ADAPTER",
    ROOT / "02_FEATURE_ENGINE",
    ROOT / "06_ALERTS",
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from w73_exact_v8_live_engine import build_exact_v8  # noqa: E402
from w73_live_decision_service import evaluate_symbol  # noqa: E402

SYMBOLS = ("SAIL", "POLICYBZR", "BANDHANBNK", "MOTILALOFS", "RADICO")
MATURITIES = (
    ("09:30", time(9, 30)),
    ("09:45", time(9, 45)),
    ("10:00", time(10, 0)),
    ("10:15", time(10, 15)),
)

# Exact source fields documented in the W73 source contract, plus fields used
# by the V8 live engine. We preserve the original source names.
SOURCE_FIELDS = (
    "Symbol", "Sector", "ATM Straddle Price", "ATM Straddle %",
    "Fair Price", "Open", "High", "Low", "Close", "VWAP",
    "Price Chg", "Price Chg %", "IV", "IV Chg", "IV Chg %",
    "OI Chg", "OI Chg %", "Volume", "Volume Chg (%)",
    "PCR Chg", "PCR Chg %", "Buildup", "Rollover (%)",
    "MWPL (%)", "MWPL (%) Chg", "5D Price Chg %", "5D OI Chg %",
    "5D Buildup", "Tot CE OI", "Tot PE OI", "Tot PE-CE OI",
    "Tot CE OI Chg", "Tot CE OI Chg %", "Tot PE OI Chg",
    "Tot PE OI Chg %", "Tot PE-CE OI Chg", "Delivery (%)",
    "Delivery (%) Chg", "IVR", "IVP", "Max Pain",
    "CE Max OI Strike", "Dist from CE Max OI Strike (%)",
    "PE Max OI Strike", "Dist from PE Max OI Strike (%)",
)

def norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")

def missing(v: Any) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except Exception:
        pass
    return str(v).strip().lower() in {"", "nan", "none", "null", "nat"}

def json_safe(v: Any):
    if isinstance(v, dict):
        return {str(k): json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [json_safe(x) for x in v]
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    return v

def parse_ts(v: Any) -> datetime:
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))

def source_ts(path: Path):
    m = re.search(r"_(\d{8})_(\d{6})\.xlsx$", path.name, re.I)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")

def source_files(root: Path, month: str, date: str):
    day = root / month / date
    if not day.exists():
        return []
    out = []
    for p in day.glob("Daywise_Price_and_OI_Summary_*.xlsx"):
        ts = source_ts(p)
        if ts:
            out.append((ts, p))
    return sorted(out, key=lambda x: x[0])

def find_column(columns, requested):
    target = norm(requested)
    exact = [c for c in columns if norm(c) == target]
    if exact:
        return exact[0]
    return None

def source_row(path: Path, symbol: str):
    df = pd.read_excel(path, sheet_name=0)
    symcol = find_column(df.columns, "Symbol") or find_column(df.columns, "Ticker")
    if not symcol:
        return None
    hit = df[df[symcol].astype(str).str.strip().str.upper().eq(symbol.upper())]
    if hit.empty:
        return None
    raw = hit.iloc[0].to_dict()
    return {
        field: raw.get(find_column(df.columns, field))
        if find_column(df.columns, field) is not None else None
        for field in SOURCE_FIELDS
    }

def load_rows(path: Path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def row_timestamp(r):
    for k in ("_observation_timestamp", "observation_timestamp",
              "source_timestamp", "timestamp", "event_timestamp"):
        if r.get(k):
            return parse_ts(r[k])
    return None

def row_symbol(r):
    for k in ("Symbol", "symbol", "Ticker", "ticker"):
        if str(r.get(k, "")).strip():
            return str(r[k]).strip().upper()
    return ""

def snapshot_at_or_before(rows, cutoff):
    return [r for r in rows if row_timestamp(r) and row_timestamp(r) <= cutoff]

def latest_by_field(rows, field):
    usable = [r for r in rows if not missing(r.get(field))]
    if not usable:
        return None
    usable.sort(key=row_timestamp)
    return usable[-1].get(field)

def collect_pit_values(rows):
    # Exact values in the accumulated PIT observations. For state-building
    # diagnostics, show latest value available by cutoff for each source field.
    return {field: json_safe(latest_by_field(rows, field)) for field in SOURCE_FIELDS}

def flatten_feature_vector(d):
    fv = getattr(d, "feature_vector", None)
    return json_safe(fv if fv is not None else {})

def flatten_trajectory(d):
    return json_safe(getattr(d, "trajectory", {}) or {})

def compare_values(source_values, pit_values, feature_vector):
    # Explicit, value-level comparison for fields with direct correspondence.
    direct = {}
    for field in SOURCE_FIELDS:
        sv = source_values.get(field)
        pv = pit_values.get(field)
        direct[field] = {
            "source": json_safe(sv),
            "pit": json_safe(pv),
            "source_present": not missing(sv),
            "pit_present": not missing(pv),
            "same": (
                (missing(sv) and missing(pv))
                or (not missing(sv) and not missing(pv) and str(sv) == str(pv))
            ),
        }

    # Particularly important PE-CE path.
    pec = {}
    for key in (
        "Tot PE-CE OI Chg",
        "Tot PE-CE OI Chg %",
        "pec",
        "pec_pct",
        "pec_state",
        "pec_pct_state",
        "pece_oi_chg",
        "pece_oi_chg_pct",
        "tot_pe_ce_oi_chg",
        "tot_pe_ce_oi_chg_pct",
    ):
        pec[key] = {
            "source": source_values.get(key) if key in source_values else None,
            "pit": pit_values.get(key) if key in pit_values else None,
            "v8": feature_vector.get(key) if key in feature_vector else None,
        }
    return direct, pec

def first_divergence(source_values, pit_values, fv, decision):
    # A value-level conservative classifier. It reports the earliest layer
    # where evidence is demonstrably present upstream but absent downstream.
    key_pairs = (
        ("Tot PE-CE OI Chg %", ("pec_pct", "pec_pct_state", "pec_pct_value")),
        ("Tot PE-CE OI Chg", ("pec", "pec_value")),
        ("High", ("orb_high", "orb_hi")),
        ("Low", ("orb_low", "orb_lo")),
        ("Close", ("price", "close", "current_price")),
    )

    for src, downstream_keys in key_pairs:
        sv = source_values.get(src)
        pv = pit_values.get(src)
        if not missing(sv) and missing(pv):
            return "PIT", f"{src}: source={json_safe(sv)!r}, PIT=None"
        if not missing(pv):
            present_v8 = False
            for k in downstream_keys:
                if k in fv and not missing(fv.get(k)):
                    present_v8 = True
                    break
            # Only classify a V8 divergence when a downstream representation
            # is expected and the decision explicitly reports that field.
            miss = set(getattr(decision, "missing_fields", ()) or ())
            if not present_v8 and any(k in miss for k in downstream_keys):
                return "V8_DERIVATION", f"{src}: PIT={json_safe(pv)!r}, V8 missing={sorted(miss & set(downstream_keys))}"
    return "NONE", ""

def run(args):
    cache = Path(args.cache)
    source_root = Path(args.source_root)
    rows = load_rows(cache)
    files = source_files(source_root, args.month, args.date)

    result_rows = []
    detail = []

    date_dt = datetime.strptime(args.date, "%Y-%m-%d")

    for symbol in SYMBOLS:
        sym_rows = [r for r in rows if row_symbol(r) == symbol]

        for maturity, mt in MATURITIES:
            cutoff = date_dt.replace(hour=mt.hour, minute=mt.minute)
            pit_rows = snapshot_at_or_before(sym_rows, cutoff)

            src_rows = []
            for ts, path in files:
                if ts <= cutoff:
                    sr = source_row(path, symbol)
                    if sr is not None:
                        src_rows.append((ts, path, sr))

            src_latest = src_rows[-1][2] if src_rows else {}
            pit_latest = collect_pit_values(pit_rows)

            decision = None
            try:
                if pit_rows:
                    decision = evaluate_symbol(
                        pit_rows,
                        symbol=symbol,
                        trading_date=args.date,
                        maturity=maturity,
                        orb_minutes=15,
                    )
            except Exception as exc:
                decision_error = repr(exc)
            else:
                decision_error = ""

            fv = flatten_feature_vector(decision) if decision else {}
            traj = flatten_trajectory(decision) if decision else {}

            direct, pec = compare_values(src_latest, pit_latest, fv)
            divergence_layer, divergence_reason = first_divergence(
                src_latest, pit_latest, fv, decision
            ) if decision else ("PIT", "No decision because no PIT rows")

            # Preserve ALL actual source/PIT values as JSON columns.
            rec = {
                "date": args.date,
                "symbol": symbol,
                "maturity": maturity,
                "cutoff": cutoff.isoformat(),
                "pit_rows_at_cutoff": len(pit_rows),
                "source_rows_at_cutoff": len(src_rows),
                "source_last_timestamp": src_rows[-1][0].isoformat() if src_rows else "",
                "source_last_file": src_rows[-1][1].name if src_rows else "",
                "SOURCE_VALUES": json.dumps(json_safe(src_latest), default=str, ensure_ascii=False),
                "PIT_VALUES": json.dumps(json_safe(pit_latest), default=str, ensure_ascii=False),
                "V8_FEATURE_VECTOR": json.dumps(fv, default=str, ensure_ascii=False),
                "V8_TRAJECTORY": json.dumps(traj, default=str, ensure_ascii=False),
                "PECE_TRACE": json.dumps(pec, default=str, ensure_ascii=False),
                "EXACT_V8_STATUS": getattr(decision, "status", "") if decision else "NO_PIT_ROWS",
                "W73_ACTION": getattr(decision, "action", "") if decision else "NOT_EVALUATED",
                "W73_VARIANT": getattr(decision, "variant", "") if decision else "",
                "V8_MISSING_FIELDS": "|".join(getattr(decision, "missing_fields", ()) or ()) if decision else "",
                "V8_WARNINGS": "|".join(getattr(decision, "warnings", ()) or ()) if decision else "",
                "FIRST_DIVERGENCE_LAYER": divergence_layer,
                "FIRST_DIVERGENCE_REASON": divergence_reason,
                "DECISION_ERROR": decision_error,
            }
            result_rows.append(rec)

            detail.append({
                "symbol": symbol,
                "maturity": maturity,
                "source_values": json_safe(src_latest),
                "pit_values": json_safe(pit_latest),
                "v8_feature_vector": fv,
                "v8_trajectory": traj,
                "pece_trace": pec,
                "exact_v8_status": rec["EXACT_V8_STATUS"],
                "w73_action": rec["W73_ACTION"],
                "w73_variant": rec["W73_VARIANT"],
                "missing_fields": list(getattr(decision, "missing_fields", ()) or ()) if decision else [],
                "warnings": list(getattr(decision, "warnings", ()) or ()) if decision else [],
                "first_divergence_layer": divergence_layer,
                "first_divergence_reason": divergence_reason,
                "source_last_timestamp": rec["source_last_timestamp"],
                "source_last_file": rec["source_last_file"],
            })

    out = ROOT / "08_TESTS" / "controlled_validation_output"
    out.mkdir(parents=True, exist_ok=True)

    csv_path = out / f"W73_VALUE_TRACE_{args.date}.csv"
    json_path = out / f"W73_VALUE_TRACE_{args.date}.json"

    pd.DataFrame(result_rows).to_csv(csv_path, index=False, encoding="utf-8")
    payload = {
        "contract": "W73_VALUE_LEVEL_REVERSE_TRACE_V1",
        "date": args.date,
        "symbols": list(SYMBOLS),
        "maturities": [m for m, _ in MATURITIES],
        "cache": str(cache),
        "source_root": str(source_root),
        "rows": detail,
        "integrity": {
            "raw_source_modified": False,
            "pit_cache_modified": False,
            "strategy_code_modified": False,
            "dashboard_modified": False,
            "future_data_used_for_decision": False,
            "post_cutoff_values_used_for_decision": False,
        },
    }
    json_path.write_text(
        json.dumps(payload, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"VALUE_TRACE_CSV={csv_path}")
    print(f"VALUE_TRACE_JSON={json_path}")
    print(f"ROWS={len(result_rows)}")
    print("INTEGRITY=" + json.dumps(payload["integrity"], sort_keys=True))

    for r in result_rows:
        print(
            f"{r['symbol']} {r['maturity']} | "
            f"V8={r['EXACT_V8_STATUS']} | "
            f"ACTION={r['W73_ACTION']} | "
            f"VARIANT={r['W73_VARIANT']} | "
            f"FIRST_DIVERGENCE={r['FIRST_DIVERGENCE_LAYER']} | "
            f"MISSING={r['V8_MISSING_FIELDS']}"
        )

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--cache", required=True)
    p.add_argument(
        "--source-root",
        default=os.environ.get(
            "NTIS_W73_SOURCE_ROOT",
            r"D:\My-data\Share P&L\Ichart Data\Screenshot",
        ),
    )
    p.add_argument("--month", default="September26")
    args = p.parse_args()
    run(args)

if __name__ == "__main__":
    main()
