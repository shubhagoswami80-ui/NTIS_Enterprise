from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re
import pandas as pd

ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot\August26\2026-08-19")
SYMBOL = "DIXON"
OUT_CSV = ROOT / "DIXON_trace_2026-08-19.csv"
OUT_XLSX = ROOT / "DIXON_trace_2026-08-19.xlsx"

PRICE_COLS = ["Price Chg %", "Price Change %", "price_chg_pct", "% Chg", "%CHNG", "% Change"]
RELEVANT = [
    "Symbol", "symbol", "Price", "CMP", "LTP", "Close", "Prev Close",
    "Price Chg %", "Price Change %", "OI Chg %", "OI Change %",
    "Volume Chg %", "Volume Change %", "Futures Buildup",
    "Futures OI Chg %", "PE OI", "CE OI", "PE-CE OI",
    "Tot PE-CE OI Chg", "PCR", "PCR Chg %", "IV", "IV Chg %",
    "ATM Straddle %", "Support", "Resistance", "High", "Low",
    "Open"
]

def clean(v):
    if pd.isna(v):
        return ""
    return str(v).strip()

def observation_time(path: Path):
    # Try common HHMM/HHMMSS patterns in filename; otherwise use mtime.
    s = path.stem
    matches = re.findall(r"(?<!\d)(\d{2})[:._-]?(\d{2})(?::?(\d{2}))?(?!\d)", s)
    for hh, mm, ss in matches:
        h, m, sec = int(hh), int(mm), int(ss or 0)
        if 0 <= h <= 23 and 0 <= m <= 59 and 0 <= sec <= 59:
            return f"{h:02d}:{m:02d}:{sec:02d}"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M:%S")

def find_symbol_col(df):
    for c in df.columns:
        if str(c).strip().lower() in {"symbol", "security", "stock", "name"}:
            return c
    return None

def find_price_change(df):
    for c in PRICE_COLS:
        if c in df.columns:
            return c
    # tolerant fallback
    for c in df.columns:
        s = str(c).strip().lower()
        if "price" in s and ("chg" in s or "change" in s):
            return c
        if "%chng" in s:
            return c
    return None

files = sorted(ROOT.glob("*.xlsx"), key=lambda p: (observation_time(p), p.stat().st_mtime, p.name.lower()))

records = []
for path in files:
    try:
        xl = pd.ExcelFile(path)
    except Exception as exc:
        print(f"SKIP unreadable: {path.name}: {exc}")
        continue

    for sheet in xl.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sheet)
        except Exception:
            continue

        df.columns = [str(c).strip() for c in df.columns]
        sym_col = find_symbol_col(df)
        if not sym_col:
            continue

        mask = df[sym_col].astype(str).str.strip().str.upper().eq(SYMBOL)
        hits = df.loc[mask]
        if hits.empty:
            continue

        price_col = find_price_change(df)

        for idx, row in hits.iterrows():
            rec = {
                "Time": observation_time(path),
                "File": path.name,
                "Sheet": sheet,
                "Source_Row": int(idx) + 2,
                "Symbol": SYMBOL,
            }

            # Preserve every source column for auditability.
            for c in df.columns:
                rec[f"SRC::{c}"] = row.get(c, "")

            price = None
            if price_col:
                raw = row.get(price_col)
                try:
                    price = float(str(raw).replace("%", "").replace(",", "").strip())
                except Exception:
                    pass

            rec["Detected_Price_Chg_Col"] = price_col or ""
            rec["Detected_Price_Chg_Pct"] = price
            rec["Eligibility"] = (
                "BULLISH_ELIGIBLE" if price is not None and price > 0.75
                else "BEARISH_ELIGIBLE" if price is not None and price < -0.75
                else "NOT_ELIGIBLE" if price is not None
                else "PRICE_CHANGE_UNAVAILABLE"
            )
            records.append(rec)

if not records:
    raise SystemExit(
        f"No DIXON rows found under {ROOT}. "
        "Confirm the files are .xlsx and contain a Symbol/Security column."
    )

out = pd.DataFrame(records)
out["_sort_time"] = pd.to_timedelta(out["Time"])
out = out.sort_values(["_sort_time", "File", "Sheet", "Source_Row"]).drop(columns="_sort_time")

out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

# Also create a compact human-readable workbook.
compact_cols = [
    "Time", "File", "Sheet", "Source_Row", "Symbol",
    "Detected_Price_Chg_Pct", "Eligibility"
]
compact = out[compact_cols].copy()

with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
    compact.to_excel(writer, sheet_name="DIXON_Timeline", index=False)
    out.to_excel(writer, sheet_name="Raw_DIXON_Rows", index=False)

print()
print("DIXON TRACE COMPLETE")
print(f"Source folder : {ROOT}")
print(f"Files scanned : {len(files)}")
print(f"DIXON rows    : {len(out)}")
print(f"CSV           : {OUT_CSV}")
print(f"Excel         : {OUT_XLSX}")
print()
print(compact.to_string(index=False))
