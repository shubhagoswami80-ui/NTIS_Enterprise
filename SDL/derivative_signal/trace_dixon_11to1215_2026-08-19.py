from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot\August26\2026-08-19")
SYMBOL = "DIXON"
START = "11:00:00"
END = "12:15:59"

# Important: timestamp is taken ONLY from the final _HHMMSS portion
# of the filename, not from the date/year.
TIME_RE = re.compile(r"_(\d{2})(\d{2})(\d{2})(?:\.[^.]+)?$")

def file_time(path: Path):
    m = TIME_RE.search(path.stem)
    if not m:
        return None
    h, mnt, sec = map(int, m.groups())
    if h > 23 or mnt > 59 or sec > 59:
        return None
    return f"{h:02d}:{mnt:02d}:{sec:02d}"

def in_window(t):
    return t is not None and START <= t <= END

def symbol_col(df):
    wanted = {"symbol", "security", "stock", "name"}
    for c in df.columns:
        if str(c).strip().lower() in wanted:
            return c
    return None

def find_col(df, terms):
    for c in df.columns:
        s = str(c).strip().lower()
        if all(term in s for term in terms):
            return c
    return None

def numeric(v):
    try:
        s = str(v).replace(",", "").replace("%", "").strip()
        return float(s)
    except Exception:
        return None

rows = []
files = []

for p in ROOT.glob("*.xlsx"):
    t = file_time(p)
    if in_window(t):
        files.append((t, p))

files.sort(key=lambda x: (x[0], x[1].name.lower()))

for t, p in files:
    try:
        xl = pd.ExcelFile(p)
    except Exception as e:
        print(f"UNREADABLE: {p.name}: {e}")
        continue

    for sheet in xl.sheet_names:
        try:
            df = pd.read_excel(p, sheet_name=sheet)
        except Exception:
            continue
        df.columns = [str(c).strip() for c in df.columns]
        sc = symbol_col(df)
        if not sc:
            continue

        hit = df[df[sc].astype(str).str.strip().str.upper().eq(SYMBOL)]
        if hit.empty:
            continue

        # Keep all source columns so this remains an audit trace.
        for idx, r in hit.iterrows():
            rec = {
                "Time": t,
                "File": p.name,
                "Sheet": sheet,
                "Source_Row": int(idx) + 2,
                "Symbol": SYMBOL,
            }
            for c in df.columns:
                rec[f"SRC::{c}"] = r.get(c, "")

            price_col = find_col(df, ["price", "chg"])
            if price_col is None:
                price_col = find_col(df, ["price", "change"])

            rec["Detected_Price_Change_Column"] = price_col or ""
            rec["Detected_Price_Change_Pct"] = numeric(r.get(price_col)) if price_col else None

            px = rec["Detected_Price_Change_Pct"]
            if px is None:
                rec["Price_Gate"] = "UNAVAILABLE"
            elif px > 0.75:
                rec["Price_Gate"] = "BULLISH_CONFIRMED_GATE"
            elif px < -0.75:
                rec["Price_Gate"] = "BEARISH_CONFIRMED_GATE"
            else:
                rec["Price_Gate"] = "PENDING_CONFIRMATION"

            # Classify source family from filename for easy timeline review.
            n = p.name.lower()
            if "daywise_price_and_oi" in n:
                family = "DAYWISE_PRICE_OI"
            elif "volumeandoispikescans" in n:
                family = "VOLUME_OI"
            elif "support_resistance" in n:
                family = "SUPPORT_RESISTANCE"
            elif "resistance_resistance" in n:
                family = "RESISTANCE"
            elif "ivr-ivp" in n:
                family = "IV_IVP"
            elif "sector_summary" in n:
                family = "SECTOR"
            else:
                family = "OTHER"
            rec["Source_Family"] = family

            rows.append(rec)

if not rows:
    raise SystemExit(
        f"No DIXON rows found between {START} and {END} in {ROOT}"
    )

out = pd.DataFrame(rows)
out["_td"] = pd.to_timedelta(out["Time"])
out = out.sort_values(["_td", "Source_Family", "File", "Sheet", "Source_Row"]).drop(columns="_td")

# Compact audit view
compact_cols = [
    "Time", "Source_Family", "File", "Sheet", "Source_Row",
    "Symbol", "Detected_Price_Change_Pct", "Price_Gate"
]
compact = out[compact_cols].copy()

# A useful source-family x time inventory
inventory = (
    compact.groupby(["Time", "Source_Family"], as_index=False)
    .agg(
        Rows=("Symbol", "size"),
        Price_Change=("Detected_Price_Change_Pct", "first"),
        Gate=("Price_Gate", "first"),
    )
)

csv1 = ROOT / "DIXON_trace_11to1215_2026-08-19.csv"
csv2 = ROOT / "DIXON_trace_inventory_11to1215_2026-08-19.csv"
xlsx = ROOT / "DIXON_trace_11to1215_2026-08-19.xlsx"

compact.to_csv(csv1, index=False, encoding="utf-8-sig")
inventory.to_csv(csv2, index=False, encoding="utf-8-sig")

with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
    compact.to_excel(w, sheet_name="DIXON_Audit", index=False)
    inventory.to_excel(w, sheet_name="Time_Source_Inventory", index=False)
    out.to_excel(w, sheet_name="Raw_DIXON_Rows", index=False)

print()
print("DIXON 11:00-12:15 TRACE COMPLETE")
print(f"Files in window : {len(files)}")
print(f"DIXON rows      : {len(out)}")
print(f"Audit CSV       : {csv1}")
print(f"Inventory CSV   : {csv2}")
print(f"Excel           : {xlsx}")
print()
print("TIME / SOURCE / PRICE GATE")
print(inventory.to_string(index=False))
