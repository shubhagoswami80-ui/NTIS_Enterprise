from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

DEFAULT_ROOT = r"D:\My-data\Share_P&L\Ichart Data\Screenshot\August26\2026-08-20"
DEFAULT_SYMBOLS = [
    "MOTILALOFS", "MUTHOOTFIN", "SBICARD", "MCX", "BANDHANBNK",
    "NAM-INDIA", "COFORGE", "PREMIERENE", "SWIGGY", "ABCAPITAL",
    "PERSISTENT", "VEDL", "360ONE", "ETERNAL", "SHRIRAMFIN",
    "RECLTD", "PFC", "BDL", "HINDALCO", "GMRAIRPORT", "DIXON",
]

def norm(x):
    return str(x).strip().upper().replace("-", "").replace("_", "").replace(" ", "")

def find_files(root):
    patterns = [
        "*decision*.csv", "*decision*.json", "*evidence*.csv", "*evidence*.json",
        "*rank*.csv", "*state*.json", "*snapshot*.csv"
    ]
    found = []
    for pat in patterns:
        found.extend(root.glob(pat))
    return sorted(set(p for p in found if p.is_file()))

def symbol_col(df):
    for c in df.columns:
        if norm(c) in {"SYMBOL", "TICKER", "STOCK", "STOCKSYMBOL"}:
            return c
    return None

def load_csv(path):
    try:
        df = pd.read_csv(path)
        c = symbol_col(df)
        if c is None:
            return None
        df["_SYMBOL_"] = df[c].astype(str).map(norm)
        return df
    except Exception:
        return None

def extract_json(path):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if isinstance(obj, list):
        return pd.json_normalize(obj)
    if isinstance(obj, dict):
        for key in ("records", "data", "decisions", "evidence", "stocks", "results"):
            val = obj.get(key)
            if isinstance(val, list):
                return pd.json_normalize(val)
        return pd.json_normalize(obj)
    return None

def main():
    ap = argparse.ArgumentParser(description="Read-only post-gate evidence/decision locator.")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    args = ap.parse_args()

    root = Path(args.root)
    wanted = {norm(s) for s in args.symbols}

    files = find_files(root)
    if not files:
        print("NO LOCAL DECISION/EVIDENCE/RANKING FILES FOUND IN SOURCE FOLDER")
        print(f"Folder checked: {root}")
        print()
        print("This is useful: it means the decision layer is likely elsewhere in the")
        print("SDL runtime/output path, and we should locate that path before changing code.")
        return

    print("POST-GATE DECISION/EVIDENCE LOCATOR")
    print("=" * 110)
    print(f"Folder : {root}")
    print(f"Files  : {len(files)}")
    print()

    hits = []

    for path in files:
        df = load_csv(path)
        if df is None:
            try:
                df = extract_json(path)
                if df is not None:
                    c = symbol_col(df)
                    if c is not None:
                        df["_SYMBOL_"] = df[c].astype(str).map(norm)
            except Exception:
                df = None

        if df is None or "_SYMBOL_" not in df.columns:
            continue

        sub = df[df["_SYMBOL_"].isin(wanted)].copy()
        if sub.empty:
            continue

        for _, row in sub.iterrows():
            useful = {}
            for c, v in row.items():
                if c == "_SYMBOL_":
                    continue
                if pd.notna(v) and str(v).strip() not in ("", "nan", "None"):
                    useful[c] = v
            hits.append((path.name, row["_SYMBOL_"], useful))

    if not hits:
        print("NO SELECTED GATE-PASSED SYMBOL FOUND IN LOCAL DECISION/EVIDENCE/RANKING OUTPUTS")
        print()
        print("This means the next step is to locate the actual runtime decision output,")
        print("not modify the decision logic.")
        return

    for symbol in sorted(wanted):
        stock_hits = [(f, s, d) for f, s, d in hits if s == symbol]
        print()
        print(f"### {symbol}")
        if not stock_hits:
            print("POST_GATE_RECORD = NOT FOUND")
            continue

        for fname, _, data in stock_hits:
            print(f"SOURCE = {fname}")
            preferred = [
                k for k in data
                if any(x in norm(k) for x in (
                    "DIRECTION", "STATE", "DECISION", "SCORE", "STRENGTH",
                    "QUALITY", "SR", "SUPPORT", "RESISTANCE", "QUALIF",
                    "CONFLUENCE", "CONFLICT", "GATE"
                ))
            ]
            if preferred:
                for k in preferred:
                    print(f"  {k}: {data[k]}")
            else:
                print(f"  columns: {', '.join(data.keys())}")

    out = root / "NTIS_post_gate_locator_2026-08-20.txt"
    with out.open("w", encoding="utf-8") as f:
        for symbol in sorted(wanted):
            f.write(f"\n### {symbol}\n")
            for fname, _, data in [(a,b,c) for a,b,c in hits if b == symbol]:
                f.write(f"SOURCE = {fname}\n")
                for k, v in data.items():
                    f.write(f"  {k}: {v}\n")

    print()
    print("=" * 110)
    print(f"Locator report: {out}")
    print()
    print("READ-ONLY. No dashboard/config/engine/state files were imported or changed.")

if __name__ == "__main__":
    main()
