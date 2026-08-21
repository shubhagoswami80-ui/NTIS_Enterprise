from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from dashboard import (
    _discover_sources,
    _first_range_from_path,
    _process_snapshot,
    _snapshot_rows,
    _rank,
    QUALIFIED_STATES,
)

DEFAULT_SYMBOLS = [
    "MOTILALOFS", "MUTHOOTFIN", "SBICARD", "MCX", "BANDHANBNK",
    "NAM-INDIA", "COFORGE", "PREMIERENE", "SWIGGY", "ABCAPITAL",
    "PERSISTENT", "VEDL", "360ONE", "ETERNAL", "SHRIRAMFIN",
    "RECLTD", "PFC", "BDL", "HINDALCO", "GMRAIRPORT",
    "DIXON",
]


def num(v):
    try:
        if v is None or pd.isna(v) or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(
        description="NTIS SDL gate-to-dashboard audit. Read-only: does not modify state."
    )
    ap.add_argument("--date", default="2026-08-20")
    ap.add_argument(
        "--root",
        default=r"D:\My-data\Share_P&L\Ichart Data\Screenshot\August26\2026-08-20",
    )
    ap.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    args = ap.parse_args()

    symbols = {s.strip().upper() for s in args.symbols if s.strip()}
    paths = _discover_sources(args.date, Path(args.root))

    if not paths:
        print("NO DAYWISE SNAPSHOTS FOUND")
        return

    first_range = _first_range_from_path(paths[0], args.date)
    previous = {}
    previous_state = {}
    previous_ranked = set()
    audit = []

    for seq, path in enumerate(paths, 1):
        try:
            result = _process_snapshot(path, args.date, previous, first_range)
        except Exception as exc:
            print(f"ERROR {path.name}: {type(exc).__name__}: {exc}")
            continue

        if result.empty:
            continue

        timestamp = path.stat().st_mtime
        ts = pd.Timestamp.fromtimestamp(timestamp).strftime("%H:%M:%S")

        ranked = _rank(result)
        ranked_symbols = set(
            ranked.get("symbol", pd.Series(dtype=str)).astype(str).str.upper()
        )

        for row in result.to_dict(orient="records"):
            symbol = str(row.get("symbol", "")).strip().upper()
            if symbol not in symbols:
                continue

            price = num(row.get("price_change_pct"))
            direction = str(
                row.get("decision_direction", row.get("direction", "NEUTRAL"))
            ).upper()
            state = str(row.get("decision_state", "NO DECISION")).upper()
            gate = (
                "BULL_GATE"
                if direction == "BULLISH" and price is not None and price > 0.75
                else "BEAR_GATE"
                if direction == "BEARISH" and price is not None and price < -0.75
                else "NOT_PASSED"
            )
            visible = symbol in ranked_symbols
            source_cols = [
                c for c in (
                    "_source_BASE", "_source_FUTURES", "_source_IV",
                    "_source_SUPPORT", "_source_RESISTANCE", "_source_VOLUME"
                ) if bool(row.get(c, False))
            ]

            audit.append({
                "Time": ts,
                "Snapshot": seq,
                "Symbol": symbol,
                "PriceChg": price,
                "Direction": direction,
                "Gate": gate,
                "State": state,
                "Score": row.get("decision_score", 0),
                "Strength": row.get("decision_strength", ""),
                "S_R": row.get("sr_status", ""),
                "Quality": row.get("decision_quality", ""),
                "Conflicts": row.get("conflict_count", 0),
                "Sources": ",".join(source_cols),
                "DashboardVisible": visible,
            })

        previous = _snapshot_rows(
            pd.read_excel(path).rename(columns=lambda c: str(c).strip())
        )

    out = pd.DataFrame(audit)
    if out.empty:
        print("NONE OF THE SELECTED SYMBOLS WERE FOUND IN THE DAYWISE TRACE")
        return

    out_path = Path(args.root) / f"NTIS_gate_dashboard_audit_{args.date}.csv"
    out.to_csv(out_path, index=False)

    print()
    print("NTIS SDL GATE → DECISION → DASHBOARD AUDIT")
    print(f"Date      : {args.date}")
    print(f"Snapshots : {len(paths)}")
    print(f"Symbols   : {len(symbols)}")
    print(f"Audit CSV : {out_path}")
    print()
    print("SUMMARY")
    print("-" * 120)

    for symbol in sorted(symbols):
        s = out[out["Symbol"] == symbol]
        if s.empty:
            print(f"{symbol:14} NOT FOUND IN DAYWISE")
            continue

        gate_rows = s[s["Gate"] != "NOT_PASSED"]
        visible_rows = s[s["DashboardVisible"]]
        qualified_rows = s[s["State"].isin(QUALIFIED_STATES)]

        first_gate = gate_rows.iloc[0] if not gate_rows.empty else None
        first_visible = visible_rows.iloc[0] if not visible_rows.empty else None
        last = s.iloc[-1]

        if first_gate is None:
            gate_text = "NO GATE"
        else:
            gate_text = f"{first_gate['Time']} {first_gate['PriceChg']:+.2f}%"

        if first_visible is None:
            visible_text = "NEVER"
        else:
            visible_text = f"{first_visible['Time']} {first_visible['State']}"

        print(
            f"{symbol:14} "
            f"FIRST_GATE={gate_text:18} "
            f"FIRST_VISIBLE={visible_text:28} "
            f"LAST={last['Time']} {last['PriceChg']!s:>7} {last['State']}"
        )

    print()
    print("DETAILED GATE-PASS EVENTS")
    print("-" * 120)
    detail = out[out["Gate"] != "NOT_PASSED"].copy()
    if detail.empty:
        print("No selected stock crossed the +/-0.75% gate in available snapshots.")
    else:
        # Show only the first gate crossing and every later state/visibility change.
        for symbol in sorted(symbols):
            s = out[out["Symbol"] == symbol]
            if s.empty:
                continue
            gate = s[s["Gate"] != "NOT_PASSED"]
            if gate.empty:
                continue
            first_idx = gate.index[0]
            tail = s.loc[first_idx:]
            changed = tail[
                tail["State"].ne(tail["State"].shift())
                | tail["DashboardVisible"].ne(tail["DashboardVisible"].shift())
            ]
            print(f"\n{symbol}")
            print(
                changed[
                    ["Time", "PriceChg", "Direction", "Gate", "State",
                     "Score", "Strength", "S_R", "Quality",
                     "Sources", "DashboardVisible"]
                ].to_string(index=False)
            )

    print()
    print("INTERPRETATION")
    print("1. NO GATE       = source/price ingestion problem or stock never crossed +/-0.75%.")
    print("2. GATE BUT NEVER VISIBLE = decision/ranking/dashboard qualification problem.")
    print("3. VISIBLE THEN LOST       = state transition/ranking problem.")
    print("4. GATE + QUALIFIED + VISIBLE = pipeline is working for that stock.")
    print()
    print("Read-only audit: no processing_state.json or production file is changed.")


if __name__ == "__main__":
    main()
