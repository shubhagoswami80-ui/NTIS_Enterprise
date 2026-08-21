from __future__ import annotations

import argparse
from pathlib import Path
import re
import pandas as pd

DEFAULT_ROOT = r"D:\My-data\Share_P&L\Ichart Data\Screenshot\August26\2026-08-20"
DEFAULT_SYMBOLS = [
    "MOTILALOFS", "MUTHOOTFIN", "SBICARD", "MCX", "BANDHANBNK",
    "NAM-INDIA", "COFORGE", "PREMIERENE", "SWIGGY", "ABCAPITAL",
    "PERSISTENT", "VEDL", "360ONE", "ETERNAL", "SHRIRAMFIN",
    "RECLTD", "PFC", "BDL", "HINDALCO", "GMRAIRPORT", "DIXON",
]

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def find_col(df, names):
    norm = {re.sub(r"[^a-z0-9]", "", str(c).lower()): c for c in df.columns}
    for name in names:
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        if key in norm:
            return norm[key]
    return None


def read_snapshot(path):
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]

    sym_col = find_col(df, ["Symbol", "Ticker", "symbol"])
    price_col = find_col(
        df,
        ["Price Chg %", "Price Chg (%)", "Price_Chg_Pct", "Price Change %"]
    )

    if sym_col is None:
        return None, None, "NO_SYMBOL_COLUMN"
    if price_col is None:
        return None, None, "NO_PRICE_CHANGE_COLUMN"

    out = pd.DataFrame()
    out["Symbol"] = df[sym_col].astype(str).str.strip().str.upper()
    out["PriceChg"] = pd.to_numeric(df[price_col], errors="coerce")
    out = out[out["Symbol"].ne("") & out["Symbol"].ne("NAN")]
    out = out.drop_duplicates("Symbol", keep="last")

    # File modification time is the intraday observation time used by
    # the existing Daywise workflow.
    ts = pd.Timestamp.fromtimestamp(path.stat().st_mtime)
    return out, ts, ""


def main():
    ap = argparse.ArgumentParser(
        description="Read-only NTIS +/-0.75% gate audit. No dashboard imports."
    )
    ap.add_argument("--date", default="2026-08-20")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    args = ap.parse_args()

    root = Path(args.root)
    symbols = {x.strip().upper() for x in args.symbols if x.strip()}

    if not root.is_dir():
        print(f"ERROR: source folder not found: {root}")
        return

    paths = sorted(
        [
            p for p in root.glob("Daywise_*.xlsx")
            if p.is_file() and not p.name.startswith("~$")
        ],
        key=lambda p: (p.stat().st_mtime, p.name.lower()),
    )

    if not paths:
        print(f"ERROR: no Daywise snapshots found in {root}")
        return

    rows = []
    errors = []

    for seq, path in enumerate(paths, 1):
        df, ts, err = read_snapshot(path)
        if err:
            errors.append((path.name, err))
            continue

        for symbol in symbols:
            match = df[df["Symbol"].eq(symbol)]
            if match.empty:
                rows.append({
                    "Snapshot": seq,
                    "Time": ts.strftime("%H:%M:%S"),
                    "Symbol": symbol,
                    "Present": False,
                    "PriceChg": None,
                    "Gate": "NOT_PRESENT",
                    "File": path.name,
                })
                continue

            price = match.iloc[-1]["PriceChg"]

            if pd.isna(price):
                gate = "PRICE_MISSING"
            elif price >= 0.75:
                gate = "BULL_GATE"
            elif price <= -0.75:
                gate = "BEAR_GATE"
            else:
                gate = "BELOW_GATE"

            rows.append({
                "Snapshot": seq,
                "Time": ts.strftime("%H:%M:%S"),
                "Symbol": symbol,
                "Present": True,
                "PriceChg": float(price) if not pd.isna(price) else None,
                "Gate": gate,
                "File": path.name,
            })

    audit = pd.DataFrame(rows)

    out_path = root / f"NTIS_gate_audit_{args.date}.csv"
    audit.to_csv(out_path, index=False)

    print()
    print("NTIS SDL +/-0.75% GATE AUDIT")
    print("=" * 100)
    print(f"Date      : {args.date}")
    print(f"Snapshots : {len(paths)}")
    print(f"Symbols   : {len(symbols)}")
    print(f"Audit CSV : {out_path}")
    print()

    for symbol in sorted(symbols):
        s = audit[audit["Symbol"].eq(symbol)].copy()

        if s.empty:
            print(f"{symbol:14} NO DATA")
            continue

        present = s[s["Present"]]
        passed = s[s["Gate"].isin(["BULL_GATE", "BEAR_GATE"])]

        if present.empty:
            print(f"{symbol:14} NOT FOUND IN ANY DAYWISE SNAPSHOT")
            continue

        first_present = present.iloc[0]
        first_pass = passed.iloc[0] if not passed.empty else None
        last = present.iloc[-1]

        if first_pass is None:
            gate_text = "NEVER"
        else:
            gate_text = (
                f"{first_pass['Time']} "
                f"{first_pass['PriceChg']:+.2f}% "
                f"{first_pass['Gate']}"
            )

        print(
            f"{symbol:14} "
            f"FIRST={first_present['Time']} "
            f"GATE={gate_text:25} "
            f"LAST={last['Time']} "
            f"{last['PriceChg']:+.2f}%"
        )

    print()
    print("FIRST GATE CROSSING DETAILS")
    print("=" * 100)

    for symbol in sorted(symbols):
        s = audit[
            audit["Symbol"].eq(symbol)
            & audit["Gate"].isin(["BULL_GATE", "BEAR_GATE"])
        ]

        if s.empty:
            continue

        first = s.iloc[0]

        print(
            f"{symbol:14} "
            f"{first['Time']}  "
            f"{first['PriceChg']:+.2f}%  "
            f"{first['Gate']}  "
            f"{first['File']}"
        )

    print()
    print("INTERPRETATION")
    print("=" * 100)
    print("NOT FOUND       = source/universe problem.")
    print("BELOW_GATE      = correctly filtered by the +/-0.75% noise gate.")
    print("BULL/BEAR_GATE  = stock became eligible and must be investigated downstream.")
    print("PRICE_MISSING   = source parsing/data-integrity problem.")
    print()
    print("This audit is READ-ONLY and does not import dashboard.py, config.py,")
    print("decision_evidence.py, signal_engine.py, or modify NTIS state.")

    if errors:
        print()
        print("SOURCE ERRORS")
        for name, err in errors:
            print(f"{name}: {err}")


if __name__ == "__main__":
    main()
