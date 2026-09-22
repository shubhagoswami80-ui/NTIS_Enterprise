from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import os
import sys

W73 = Path(__file__).resolve().parents[1]
ADAPTER_DIR = W73 / "03_LIVE_ADAPTER"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))

from w73_source_adapter import W73SourceAdapter, W73SourceConfig
from w73_point_in_time_cache import W73PointInTimeCache
from w73_canonical_observation import canonicalize, REQUIRED_SOURCE_FIELDS

MONTH = os.getenv("NTIS_W73_VALIDATE_MONTH", "September26")
TRADING_DATE = os.getenv("NTIS_W73_VALIDATE_DATE", "2026-09-18")
CUTOFF_TEXT = os.getenv("NTIS_W73_VALIDATE_CUTOFF", "09:18:09")


def main() -> int:
    hh, mm, ss = map(int, CUTOFF_TEXT.split(":"))
    cutoff = datetime.fromisoformat(
        f"{TRADING_DATE}T{hh:02d}:{mm:02d}:{ss:02d}"
    )

    cfg = W73SourceConfig.from_environment()
    adapter = W73SourceAdapter(cfg)
    intervals = adapter.list_intervals(MONTH, TRADING_DATE)

    if not intervals:
        raise SystemExit(
            f"NO_INTERVALS_FOUND month={MONTH} trading_date={TRADING_DATE} "
            f"source_root={cfg.source_root}"
        )

    selected, header, records = adapter.read_interval(
        MONTH, TRADING_DATE, cutoff=cutoff
    )

    if selected.timestamp > cutoff:
        raise AssertionError("CUT_OFF_VIOLATION")

    if not selected.path.is_file():
        raise AssertionError("SELECTED_SOURCE_FILE_MISSING")

    if not records:
        raise AssertionError("SELECTED_WORKBOOK_HAS_NO_RECORDS")

    symbols = [str(r.get("Symbol", "")).strip() for r in records]
    symbols = [s for s in symbols if s]
    if not symbols:
        raise AssertionError("NO_SYMBOLS_IN_SELECTED_WORKBOOK")

    sample = records[0]
    missing_source_columns = [
        field for field in REQUIRED_SOURCE_FIELDS if field not in sample
    ]

    canonical = canonicalize(sample)
    canonical_missing = [
        field for field in REQUIRED_SOURCE_FIELDS if field not in canonical
    ]

    # This validator intentionally does not claim that raw XLSX fields are
    # already V8 state features. That derivation is the next controlled layer.
    v8_state_fields = [
        "orb_minutes", "maturity", "orb_dir", "price_dir", "fut_dir",
        "option_dir", "fut_state", "volume_state", "ce_state", "pe_state",
        "pec_state", "fut_oi_state", "ce_pct_state", "pe_pct_state",
        "pec_pct_state", "fut_pct_state", "price_state", "orb_agree",
        "evidence_agreement", "persistent", "strength_bucket",
        "core_count_band", "magnitude_count_band", "orb_fut_agree",
        "orb_price_agree",
    ]
    v8_present_in_raw = [f for f in v8_state_fields if f in sample]

    cache = W73PointInTimeCache()
    cache_path = cache.write_interval(selected, TRADING_DATE, records)
    cached = cache.read_interval(TRADING_DATE, selected.timestamp)

    report = {
        "status": "PASS",
        "source_root": str(cfg.source_root),
        "month_folder": MONTH,
        "trading_date": TRADING_DATE,
        "cutoff": cutoff.isoformat(),
        "selected_source_file": selected.path.name,
        "selected_source_timestamp": selected.timestamp.isoformat(),
        "interval_count_in_selected_day": len(intervals),
        "record_count": len(records),
        "symbol_count": len(symbols),
        "header_count": len(header),
        "required_source_fields_missing": missing_source_columns,
        "canonical_fields_missing": canonical_missing,
        "cached_record_count": len(cached),
        "cache_path": str(cache_path),
        "v8_state_fields_present_in_raw": v8_present_in_raw,
        "v8_derivation_status": "NOT_YET_DERIVED",
        "source_is_read_only": True,
    }

    if missing_source_columns or canonical_missing:
        report["status"] = "FAIL"
    if len(cached) != len(records):
        report["status"] = "FAIL"

    out = W73 / "07_OUTPUT" / "real_source_validation_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("STATUS " + report["status"])
    print(f"SOURCE_ROOT={cfg.source_root}")
    print(f"TRADING_DATE={TRADING_DATE}")
    print(f"CUTOFF={cutoff.strftime('%H:%M:%S')}")
    print(f"SELECTED_FILE={selected.path.name}")
    print(f"SELECTED_TIMESTAMP={selected.timestamp.strftime('%H:%M:%S')}")
    print(f"INTERVALS_FOUND={len(intervals)}")
    print(f"RECORDS={len(records)}")
    print(f"SYMBOLS={len(symbols)}")
    print(f"REQUIRED_FIELDS_MISSING={len(missing_source_columns)}")
    print(f"CANONICAL_FIELDS_MISSING={len(canonical_missing)}")
    print(f"CACHED_RECORDS={len(cached)}")
    print(f"V8_STATE_FIELDS_PRESENT={len(v8_present_in_raw)}")
    print(f"V8_DERIVATION_STATUS=NOT_YET_DERIVED")
    print(f"REPORT={out}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
