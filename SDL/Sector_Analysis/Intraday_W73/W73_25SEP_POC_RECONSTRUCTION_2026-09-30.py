import sys
from pathlib import Path
import json
import pandas as pd

ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73")
DAY = "2026-09-25"
MONTH = "September26"
SYMBOLS = ["BANDHANBNK", "MOTILALOFS", "POLICYBZR", "RADICO", "SAIL"]
MATURITIES = ["09:30", "09:45", "10:00", "10:15"]

sys.path.insert(0, str(ROOT / "03_LIVE_ADAPTER"))
sys.path.insert(0, str(ROOT / "02_FEATURE_ENGINE"))

from w73_live_ingestor import discover_files, read_workbook, build_pece_index
from w73_exact_v8_live_engine import build_exact_v8


def row_ts(r):
    try:
        return pd.Timestamp(r.get("_observation_timestamp"))
    except Exception:
        return pd.NaT


def val(r, *keys):
    for k in keys:
        if k in r and r.get(k) not in (None, ""):
            return r.get(k)
    return None


def run():
    pece = build_pece_index(DAY)
    files = discover_files(DAY, MONTH)

    rows = []
    selected_files = []

    for path, file_ts in files:
        file_rows = read_workbook(path, file_ts, pece)
        filtered = []
        for r in file_rows:
            sym = str(r.get("Symbol", "")).strip().upper()
            ts = row_ts(r)
            if sym in SYMBOLS and pd.notna(ts) and ts <= pd.Timestamp(f"{DAY} 10:15:00"):
                rows.append(r)
                filtered.append(r)
        if filtered:
            selected_files.append({
                "file": str(path),
                "file_timestamp": str(file_ts),
                "controlled_rows": len(filtered),
            })

    print("=" * 100)
    print("NTIS W73 — ISOLATED 25-SEP POC RECONSTRUCTION")
    print("LIVE DASHBOARD / LIVE QUEUE: NOT TOUCHED")
    print("=" * 100)
    print(f"DAY={DAY}  SYMBOLS={','.join(SYMBOLS)}")
    print(f"DISCOVERED_DAYWISE_FILES={len(files)}")
    print(f"FILES_WITH_CONTROLLED_ROWS={len(selected_files)}")
    print(f"CONTROLLED_ROWS_THROUGH_10:15={len(rows)}")

    if rows:
        max_ts = max(row_ts(r) for r in rows if pd.notna(row_ts(r)))
        print(f"MAX_CONTROLLED_PIT_TIMESTAMP={max_ts}")
    else:
        max_ts = pd.NaT
        print("MAX_CONTROLLED_PIT_TIMESTAMP=None")

    results = []
    for maturity in MATURITIES:
        cutoff = pd.Timestamp(f"{DAY} {maturity}:00")
        pit_rows = [r for r in rows if row_ts(r) <= cutoff]
        future_rows = [r for r in rows if row_ts(r) > cutoff]

        print("\n" + "-" * 100)
        print(f"CHECKPOINT={maturity}  PIT_ROWS={len(pit_rows)}  FUTURE_ROWS_EXCLUDED={len(future_rows)}")

        for sym in SYMBOLS:
            sr = [r for r in pit_rows if str(r.get("Symbol", "")).strip().upper() == sym]

            record = {
                "trading_date": DAY,
                "maturity": maturity,
                "symbol": sym,
                "pit_rows": len(sr),
                "future_rows_for_symbol": len([r for r in rows
                                               if str(r.get("Symbol", "")).strip().upper() == sym
                                               and row_ts(r) > cutoff]),
            }

            if not sr:
                record.update({
                    "status": "NO_PIT_ROWS",
                    "variant": None,
                    "missing_fields": [],
                    "warnings": ["NO_PIT_ROWS"],
                })
                results.append(record)
                print(f"{sym:12} NO_PIT_ROWS")
                continue

            try:
                x = build_exact_v8(
                    sr,
                    symbol=sym,
                    trading_date=DAY,
                    maturity=maturity,
                    orb_minutes=15,
                )
            except Exception as exc:
                record.update({
                    "status": "ENGINE_ERROR",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                results.append(record)
                print(f"{sym:12} ENGINE_ERROR {type(exc).__name__}: {exc}")
                continue

            f = x.feature_vector or {}
            t = x.trajectory or {}
            a = bool(x.variants.get("W73-A"))
            b = bool(x.variants.get("W73-B"))

            # NL is research/display-only and is calculated only from a complete
            # Exact V8 result. It never feeds W73-A/B.
            nl_t3_a = (
                x.status == "READY"
                and f.get("orb_agree") == "NO"
                and f.get("magnitude_count_band") == "0"
                and t.get("px_negative_count_pre_maturity") is not None
                and t.get("px_negative_count_pre_maturity") <= 3
            )
            nl_t3_b = (
                x.status == "READY"
                and f.get("orb_price_agree") == "NO"
                and f.get("magnitude_count_band") == "0"
                and t.get("px_negative_count_pre_maturity") is not None
                and t.get("px_negative_count_pre_maturity") <= 3
            )
            nl_t2_a = (
                x.status == "READY"
                and f.get("orb_agree") == "NO"
                and f.get("magnitude_count_band") == "0"
                and t.get("px_negative_count_pre_maturity") is not None
                and t.get("px_negative_count_pre_maturity") <= 2
            )
            nl_t2_b = (
                x.status == "READY"
                and f.get("orb_price_agree") == "NO"
                and f.get("magnitude_count_band") == "0"
                and t.get("px_negative_count_pre_maturity") is not None
                and t.get("px_negative_count_pre_maturity") <= 2
            )

            last = max(sr, key=lambda r: row_ts(r))
            record.update({
                "status": x.status,
                "variant": "W73-A" if a else "W73-B" if b else None,
                "w73_a": a,
                "w73_b": b,
                "missing_fields": list(x.missing_fields),
                "warnings": list(x.warnings),
                "observation_timestamp": str(x.observation_timestamp),
                "orb_agree": f.get("orb_agree"),
                "orb_price_agree": f.get("orb_price_agree"),
                "magnitude_count_band": f.get("magnitude_count_band"),
                "px_all_negative_pre_maturity": t.get("px_all_negative_pre_maturity"),
                "px_negative_count_pre_maturity": t.get("px_negative_count_pre_maturity"),
                "observations_used": t.get("observations_used"),
                "pec_state": f.get("pec_state"),
                "pec_pct_state": f.get("pec_pct_state"),
                "pec_num": f.get("pec_num"),
                "pec_pct": f.get("pec_pct"),
                "source_direct_pec_num": val(last, "Tot PE-CE OI Chg"),
                "source_direct_pec_pct": val(last, "Tot PE-CE OI Chg %"),
                "nl_t3_a": nl_t3_a,
                "nl_t3_b": nl_t3_b,
                "nl_t2_a": nl_t2_a,
                "nl_t2_b": nl_t2_b,
            })
            results.append(record)

            print(
                f"{sym:12} STATUS={x.status:9} "
                f"A={str(a):5} B={str(b):5} "
                f"T3A={str(nl_t3_a):5} T3B={str(nl_t3_b):5} "
                f"T2A={str(nl_t2_a):5} T2B={str(nl_t2_b):5} "
                f"ORB_A={str(f.get('orb_agree')):3} "
                f"ORB_B={str(f.get('orb_price_agree')):3} "
                f"MAG={str(f.get('magnitude_count_band')):3} "
                f"NEG={str(t.get('px_negative_count_pre_maturity')):3} "
                f"MISSING={','.join(x.missing_fields) if x.missing_fields else '-'}"
            )

    out_dir = Path.home() / "Downloads"
    json_path = out_dir / "W73_25SEP_POC_RECONSTRUCTION_2026-09-30.json"
    csv_path = out_dir / "W73_25SEP_POC_RECONSTRUCTION_2026-09-30.csv"

    payload = {
        "status": "COMPLETED",
        "trading_date": DAY,
        "symbols": SYMBOLS,
        "maturities": MATURITIES,
        "source_month": MONTH,
        "discovered_daywise_files": len(files),
        "files_with_controlled_rows": len(selected_files),
        "controlled_rows_through_10_15": len(rows),
        "max_controlled_pit_timestamp": str(max_ts) if pd.notna(max_ts) else None,
        "selected_files": selected_files,
        "results": results,
        "live_dashboard_modified": False,
        "raw_source_modified": False,
    }

    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(results).to_csv(csv_path, index=False)

    print("\n" + "=" * 100)
    print("RECONSTRUCTION COMPLETE")
    print(f"JSON={json_path}")
    print(f"CSV ={csv_path}")
    print("LIVE_DASHBOARD_MODIFIED=False")
    print("RAW_SOURCE_MODIFIED=False")
    print("=" * 100)


if __name__ == "__main__":
    run()
