"""
NTIS W73 — Controlled Reverse Validation: NSE Top 5 Gainers

Purpose
-------
Read-only validation for a fixed five-symbol basket against the frozen W73
LiveDecision / Exact-V8 logic.

This script:
1. Reads ONLY an existing PIT JSONL cache.
2. Evaluates the five symbols at each frozen maturity cutoff:
   09:30, 09:45, 10:00, 10:15.
3. Uses only observations available at that cutoff for the W73 decision.
4. Separately records the later price path AFTER the cutoff for validation.
5. Never feeds future observations into the decision.
6. Does not modify source data, PIT cache, dashboard, or strategy code.

Symbols supplied by the user:
SAIL, POLICYBZR, BANDHANBNK, MOTILALOFS, RADICO

Important:
- This is a validation/research script, not a trading-signal generator.
- "QUALIFIED" means only the authoritative W73 LiveDecision action.
- Forward movement is reported as validation evidence only; it is never an input
  to the W73 decision.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DIR = ROOT / "03_LIVE_ADAPTER"
ALERT_DIR = ROOT / "06_ALERTS"

for p in (ADAPTER_DIR, ALERT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from w73_live_decision_service import evaluate_symbol  # noqa: E402


SYMBOLS = (
    "SAIL",
    "POLICYBZR",
    "BANDHANBNK",
    "MOTILALOFS",
    "RADICO",
)

MATURITIES = (
    ("09:30", time(9, 30)),
    ("09:45", time(9, 45)),
    ("10:00", time(10, 0)),
    ("10:15", time(10, 15)),
)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(str(value))


def load_pit(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"PIT cache not found: {path}")
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def find_default_cache(trading_date: str) -> Path | None:
    base = ROOT / "07_OUTPUT" / "live_cache"
    candidates = [
        base / f"{trading_date}.jsonl",
        base / f"{trading_date}_pit.jsonl",
        base / f"pit_{trading_date}.jsonl",
    ]
    for p in candidates:
        if p.exists():
            return p

    # Controlled discovery only inside W73 live_cache.
    if base.exists():
        matches = sorted(base.glob(f"*{trading_date}*.jsonl"))
        if matches:
            return matches[0]
    return None


def cutoff_ts(trading_date: str, maturity: str) -> datetime:
    hh, mm = map(int, maturity.split(":"))
    return datetime.fromisoformat(trading_date).replace(
        hour=hh, minute=mm, second=0, microsecond=0
    )


def symbol_rows(rows: list[dict], symbol: str) -> list[dict]:
    return [
        r for r in rows
        if str(r.get("Symbol", "")).strip().upper() == symbol
    ]


def observed_asof(rows: list[dict]) -> str:
    timestamps = []
    for r in rows:
        raw = r.get("_observation_timestamp", r.get("timestamp"))
        if raw:
            try:
                timestamps.append(parse_ts(raw))
            except ValueError:
                pass
    return max(timestamps).isoformat() if timestamps else ""


def first_value(rows: list[dict], field: str):
    ordered = sorted(
        rows,
        key=lambda r: parse_ts(r["_observation_timestamp"])
        if r.get("_observation_timestamp")
        else datetime.min,
    )
    for r in ordered:
        value = r.get(field)
        if value not in (None, ""):
            return value
    return ""


def forward_price_evidence(all_symbol_rows: list[dict], cutoff: datetime) -> dict:
    future = []
    for r in all_symbol_rows:
        raw = r.get("_observation_timestamp")
        if not raw:
            continue
        try:
            ts = parse_ts(raw)
        except ValueError:
            continue
        if ts <= cutoff:
            continue
        try:
            close = float(str(r.get("Close", "")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        future.append((ts, close))

    if not future:
        return {
            "forward_observations": 0,
            "forward_first_close": "",
            "forward_max_close": "",
            "forward_min_close": "",
            "forward_max_move_pct": "",
            "forward_min_move_pct": "",
        }

    future.sort()
    first_close = future[0][1]
    max_close = max(x[1] for x in future)
    min_close = min(x[1] for x in future)

    if first_close:
        max_move = (max_close / first_close - 1.0) * 100.0
        min_move = (min_close / first_close - 1.0) * 100.0
    else:
        max_move = min_move = None

    return {
        "forward_observations": len(future),
        "forward_first_close": first_close,
        "forward_max_close": max_close,
        "forward_min_close": min_close,
        "forward_max_move_pct": max_move,
        "forward_min_move_pct": min_move,
    }


def run(trading_date: str, cache_file: Path, output_dir: Path) -> None:
    rows = load_pit(cache_file)
    if not rows:
        raise RuntimeError("PIT cache contains no rows.")

    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for symbol in SYMBOLS:
        all_rows = symbol_rows(rows, symbol)
        if not all_rows:
            results.append({
                "trading_date": trading_date,
                "symbol": symbol,
                "maturity": "",
                "status": "NO_SYMBOL_ROWS",
                "action": "NOT_EVALUATED",
                "variant": "",
                "observation_timestamp": "",
                "source_timestamp": "",
                "missing_fields": "",
                "warnings": "NO_SYMBOL_ROWS",
                "trajectory": "",
                "forward_observations": 0,
                "forward_first_close": "",
                "forward_max_close": "",
                "forward_min_close": "",
                "forward_max_move_pct": "",
                "forward_min_move_pct": "",
            })
            continue

        for maturity, _ in MATURITIES:
            cutoff = cutoff_ts(trading_date, maturity)
            pit_rows = [
                r for r in all_rows
                if r.get("_observation_timestamp")
                and parse_ts(r["_observation_timestamp"]) <= cutoff
            ]

            if not pit_rows:
                results.append({
                    "trading_date": trading_date,
                    "symbol": symbol,
                    "maturity": maturity,
                    "status": "NOT_READY",
                    "action": "NOT_READY",
                    "variant": "",
                    "observation_timestamp": "",
                    "source_timestamp": "",
                    "missing_fields": "",
                    "warnings": "NO_PIT_ROWS_AT_CUTOFF",
                    "trajectory": "",
                    **forward_price_evidence(all_rows, cutoff),
                })
                continue

            decision = evaluate_symbol(
                pit_rows,
                symbol=symbol,
                trading_date=trading_date,
                maturity=maturity,
                orb_minutes=15,
            )

            evidence = forward_price_evidence(all_rows, cutoff)
            results.append({
                "trading_date": trading_date,
                "symbol": symbol,
                "maturity": maturity,
                "status": decision.status,
                "action": decision.action,
                "variant": decision.variant or "",
                "observation_timestamp": decision.observation_timestamp,
                "source_timestamp": decision.source_timestamp,
                "missing_fields": "|".join(decision.missing_fields),
                "warnings": "|".join(decision.warnings),
                "trajectory": json.dumps(decision.trajectory, sort_keys=True),
                **evidence,
            })

    csv_path = output_dir / f"W73_CONTROLLED_REVERSE_VALIDATION_{trading_date}.csv"
    json_path = output_dir / f"W73_CONTROLLED_REVERSE_VALIDATION_{trading_date}.json"

    fields = list(results[0].keys()) if results else []
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    summary = {
        "trading_date": trading_date,
        "cache_file": str(cache_file),
        "cache_rows": len(rows),
        "symbols": list(SYMBOLS),
        "maturities": [m for m, _ in MATURITIES],
        "results": results,
        "decision_counts": {
            action: sum(1 for r in results if r["action"] == action)
            for action in ("QUALIFIED", "WAIT", "NOT_READY", "NOT_EVALUATED")
        },
        "integrity": {
            "future_data_used_for_decision": False,
            "raw_source_modified": False,
            "pit_cache_modified": False,
            "strategy_code_modified": False,
            "forward_evidence_used_for_decision": False,
        },
    }
    json_path.write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"TRADING_DATE={trading_date}")
    print(f"PIT_CACHE={cache_file}")
    print(f"PIT_ROWS={len(rows)}")
    print(f"SYMBOLS={','.join(SYMBOLS)}")
    print("MATURITIES=09:30,09:45,10:00,10:15")
    print(f"CSV={csv_path}")
    print(f"JSON={json_path}")
    print("DECISION_COUNTS=" + json.dumps(summary["decision_counts"], sort_keys=True))
    print("FUTURE_DATA_USED_FOR_DECISION=False")
    print("RAW_SOURCE_MODIFIED=False")
    print("PIT_CACHE_MODIFIED=False")
    print("STRATEGY_CODE_MODIFIED=False")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trading date YYYY-MM-DD")
    parser.add_argument("--cache", default="", help="Existing W73 PIT JSONL cache")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "08_TESTS" / "controlled_validation_output"),
    )
    args = parser.parse_args()

    cache = Path(args.cache) if args.cache else find_default_cache(args.date)
    if cache is None:
        raise SystemExit(
            "No PIT cache found inside 07_OUTPUT/live_cache. "
            "Supply --cache with the existing W73 PIT JSONL file."
        )

    run(args.date, cache, Path(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
