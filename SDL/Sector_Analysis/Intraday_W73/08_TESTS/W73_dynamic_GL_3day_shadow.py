import sys
from pathlib import Path
import pandas as pd

ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73")
sys.path.insert(0, str(ROOT / "03_LIVE_ADAPTER"))
sys.path.insert(0, str(ROOT / "02_FEATURE_ENGINE"))

from w73_live_ingestor import discover_files, read_workbook, build_pece_index
from w73_exact_v8_live_engine import build_exact_v8

DAYS = ["2026-09-23", "2026-09-24", "2026-09-25"]
MATURITIES = ["09:30", "09:45", "10:00", "10:15"]
TOP_N = 15

def row_ts(r):
    try:
        return pd.Timestamp(r["_observation_timestamp"])
    except Exception:
        return pd.NaT

def price_change(r):
    for k in ("Price Chg %", "price_chg_pct", "Price Change %"):
        try:
            v = r.get(k)
            if v is not None and str(v).strip() not in ("", "-", "nan", "None"):
                return float(str(v).replace("%", "").replace(",", "").strip())
        except Exception:
            pass
    return None

def symbol(r):
    return str(r.get("Symbol", "")).strip().upper()

def select_gainers_losers(rows, cutoff):
    latest = {}
    for r in rows:
        s = symbol(r)
        t = row_ts(r)
        if not s or pd.isna(t) or t > cutoff:
            continue
        pc = price_change(r)
        if pc is None:
            continue
        if s not in latest or t > latest[s][0]:
            latest[s] = (t, r, pc)

    vals = list(latest.values())
    gainers = sorted([x for x in vals if x[2] > 0], key=lambda x: x[2], reverse=True)[:TOP_N]
    losers = sorted([x for x in vals if x[2] < 0], key=lambda x: x[2])[:TOP_N]

    return gainers, losers

def evaluate(day, rows, maturity):
    cutoff = pd.Timestamp(f"{day} {maturity}:00")
    gainers, losers = select_gainers_losers(rows, cutoff)
    selected = {}
    for side, items in (("G", gainers), ("L", losers)):
        for _, r, pc in items:
            selected[(symbol(r), side)] = pc

    strict_a = strict_b = t3_a = t3_b = t2_a = t2_b = ready = 0
    candidates = []

    for (sym, side), selected_pc in selected.items():
        sr = [
            r for r in rows
            if symbol(r) == sym and pd.notna(row_ts(r)) and row_ts(r) <= cutoff
        ]
        if not sr:
            continue

        try:
            x = build_exact_v8(sr, symbol=sym, trading_date=day,
                               maturity=maturity, orb_minutes=15)
        except TypeError as e:
            if "ExactV8Result.__init__" in str(e) or "missing 1 required positional argument" in str(e):
                print(f"  SKIP {sym} {side} @ {maturity}: existing Exact V8 constructor error")
                continue
            raise

        if x.status != "READY":
            continue

        ready += 1
        a = bool(x.variants.get("W73-A"))
        b = bool(x.variants.get("W73-B"))
        strict_a += a
        strict_b += b

        f = x.feature_vector
        neg = x.trajectory.get("px_negative_count_pre_maturity", 999)

        t3a = f.get("orb_agree") == "NO" and f.get("magnitude_count_band") == "0" and neg <= 3
        t3b = f.get("orb_price_agree") == "NO" and f.get("magnitude_count_band") == "0" and neg <= 3
        t2a = f.get("orb_agree") == "NO" and f.get("magnitude_count_band") == "0" and neg <= 2
        t2b = f.get("orb_price_agree") == "NO" and f.get("magnitude_count_band") == "0" and neg <= 2

        t3_a += t3a
        t3_b += t3b
        t2_a += t2a
        t2_b += t2b

        if a or b or t3a or t3b or t2a or t2b:
            candidates.append({
                "date": day, "maturity": maturity, "side": side, "symbol": sym,
                "selected_price_chg_pct": selected_pc,
                "strict_A": a, "strict_B": b,
                "T3_A": t3a, "T3_B": t3b,
                "T2_A": t2a, "T2_B": t2b,
                "orb_agree": f.get("orb_agree"),
                "orb_price_agree": f.get("orb_price_agree"),
                "magnitude_count_band": f.get("magnitude_count_band"),
                "px_negative_count": neg,
                "trajectory_all_negative": x.trajectory.get("px_all_negative_pre_maturity"),
            })

    print(f"{maturity}: selected G/L={len(selected)} | READY={ready} | "
          f"STRICT A/B={strict_a}/{strict_b} | T3 A/B={t3_a}/{t3_b} | T2 A/B={t2_a}/{t2_b}")
    print("  GAINERS:", [(symbol(r), round(pc,2)) for _, r, pc in gainers])
    print("  LOSERS :", [(symbol(r), round(pc,2)) for _, r, pc in losers])
    for c in candidates:
        print("  CAND:", c)
    return candidates

all_results = []

print("W73 DYNAMIC GAINER/LOSER SHADOW — READ ONLY")
print("STRICT WINDOW: 09:15-10:15 | TOP_N:", TOP_N)
print("No full-day workbook reads; files after 10:15 are skipped before read.")

for day in DAYS:
    pece = build_pece_index(day)
    files = discover_files(day, "September26")
    rows = []

    for path, file_ts in files:
        try:
            ft = pd.Timestamp(file_ts)
        except Exception:
            continue
        if ft < pd.Timestamp(f"{day} 09:15:00") or ft > pd.Timestamp(f"{day} 10:15:00"):
            continue
        for r in read_workbook(path, file_ts, pece):
            t = row_ts(r)
            if pd.notna(t) and pd.Timestamp(f"{day} 09:15:00") <= t <= pd.Timestamp(f"{day} 10:15:00"):
                rows.append(r)

    print(f"\n=== {day} | bounded rows: {len(rows)} ===")
    for maturity in MATURITIES:
        all_results.extend(evaluate(day, rows, maturity))

if all_results:
    out = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73\08_TESTS\W73_dynamic_GL_3day_shadow.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_results).to_csv(out, index=False)
    print("\nOUTPUT:", out)
else:
    print("\nOUTPUT: no strict/T2/T3 candidates found")

print("\nDONE")
