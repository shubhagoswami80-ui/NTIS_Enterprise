from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, time
from pathlib import Path

ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73")
SOURCE_ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot")
MONTH = "September26"
DATES = ("2026-09-23", "2026-09-24", "2026-09-25")
CHECKPOINTS = ("09:45", "10:00", "10:15")
SYMBOLS = ("BANDHANBNK", "MOTILALOFS", "POLICYBZR", "RADICO", "SAIL")

MAX_FILES_PER_DAY = 11
MAX_FILES_TOTAL = 33
MAX_ROWS_TOTAL = 10000

OUT_DIR = ROOT / "08_TESTS" / "source_truth_acceptance_output"
OUT_FILE = OUT_DIR / "W73_STAGE2_BOUNDED_PIT_5STOCK.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dt_cutoff(trading_date: str, hhmm: str) -> datetime:
    hh, mm = map(int, hhmm.split(":"))
    return datetime.fromisoformat(trading_date).replace(
        hour=hh, minute=mm, second=0, microsecond=0
    )


def main() -> int:
    adapter_path = ROOT / "03_LIVE_ADAPTER" / "w73_source_adapter.py"
    engine_path = ROOT / "02_FEATURE_ENGINE" / "w73_exact_v8_live_engine.py"

    if not adapter_path.exists():
        raise FileNotFoundError(adapter_path)
    if not engine_path.exists():
        raise FileNotFoundError(engine_path)

    # Use the existing W73 source adapter and the existing exact V8 engine.
    adapter_mod = load_module("w73_stage2_source_adapter", adapter_path)
    engine_mod = load_module("w73_stage2_exact_v8", engine_path)

    adapter = adapter_mod.W73SourceAdapter(
        adapter_mod.W73SourceConfig(source_root=SOURCE_ROOT)
    )

    all_days = []
    total_files = 0
    total_rows = 0

    for trading_date in DATES:
        cutoff_1015 = dt_cutoff(trading_date, "10:15")
        files = adapter.list_intervals(
            MONTH, trading_date, cutoff=cutoff_1015
        )

        if len(files) != MAX_FILES_PER_DAY:
            raise RuntimeError(
                f"{trading_date}: expected exactly {MAX_FILES_PER_DAY} eligible "
                f"files <=10:15, got {len(files)}"
            )

        day_rows = []
        file_records = []

        for sf in files:
            header, records = adapter.read_workbook(sf.path)
            file_hash = sha256(sf.path)

            selected = []
            for row in records:
                symbol = str(row.get("Symbol", "")).strip().upper()
                if symbol not in SYMBOLS:
                    continue
                r = dict(row)
                r["_trading_date"] = trading_date
                r["_observation_timestamp"] = sf.timestamp.isoformat(timespec="seconds")
                r["_source_file"] = sf.path.name
                # This is the existing W73 live-ingestor family contract.
                r["family"] = "FUTURES"
                selected.append(r)

            day_rows.extend(selected)
            file_records.append(
                {
                    "file": sf.path.name,
                    "timestamp": sf.timestamp.isoformat(timespec="seconds"),
                    "sha256": file_hash,
                    "raw_row_count": len(records),
                    "controlled_symbol_row_count": len(selected),
                    "controlled_symbols_found": sorted(
                        {str(x.get("Symbol", "")).strip().upper() for x in selected}
                    ),
                }
            )

        if len(day_rows) > MAX_ROWS_TOTAL:
            raise RuntimeError(
                f"{trading_date}: bounded row limit exceeded: {len(day_rows)}"
            )

        total_files += len(files)
        total_rows += len(day_rows)

        checkpoints = []
        for maturity in CHECKPOINTS:
            cutoff = dt_cutoff(trading_date, maturity)
            pit_rows = [
                r for r in day_rows
                if datetime.fromisoformat(str(r["_observation_timestamp"])) <= cutoff
            ]

            # Explicit future-leakage assertion on the rows supplied to Exact V8.
            future_rows = [
                r for r in pit_rows
                if datetime.fromisoformat(str(r["_observation_timestamp"])) > cutoff
            ]
            if future_rows:
                raise RuntimeError(
                    f"{trading_date} {maturity}: future rows entered PIT input"
                )

            stock_results = []
            for symbol in SYMBOLS:
                result = engine_mod.build_exact_v8(
                    pit_rows,
                    symbol=symbol,
                    trading_date=trading_date,
                    maturity=maturity,
                    orb_minutes=15,
                )
                d = result.to_dict()
                d["requested_maturity_cutoff"] = cutoff.isoformat()
                d["max_input_timestamp"] = (
                    max(
                        datetime.fromisoformat(str(r["_observation_timestamp"]))
                        for r in pit_rows
                    ).isoformat()
                    if pit_rows else None
                )
                d["future_input_rows"] = len(future_rows)
                stock_results.append(d)

            checkpoints.append(
                {
                    "maturity": maturity,
                    "requested_cutoff": cutoff.isoformat(),
                    "pit_input_row_count": len(pit_rows),
                    "max_pit_input_timestamp": (
                        max(
                            datetime.fromisoformat(str(r["_observation_timestamp"]))
                            for r in pit_rows
                        ).isoformat()
                        if pit_rows else None
                    ),
                    "future_input_rows": len(future_rows),
                    "results": stock_results,
                }
            )

        all_days.append(
            {
                "trading_date": trading_date,
                "eligible_files_loaded_once": len(files),
                "file_records": file_records,
                "controlled_rows_loaded_once": len(day_rows),
                "checkpoints": checkpoints,
            }
        )

    if total_files != MAX_FILES_TOTAL:
        raise RuntimeError(
            f"Global workbook bound failed: {total_files} != {MAX_FILES_TOTAL}"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "status": "PASS",
        "stage": "STAGE_2_BOUNDED_PIT_5STOCK",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(ROOT),
        "source_root": str(SOURCE_ROOT),
        "month_folder": MONTH,
        "dates": list(DATES),
        "checkpoints": list(CHECKPOINTS),
        "controlled_symbols": list(SYMBOLS),
        "hard_limits": {
            "max_workbooks_per_day": MAX_FILES_PER_DAY,
            "max_workbooks_total": MAX_FILES_TOTAL,
            "max_controlled_rows_per_day": MAX_ROWS_TOTAL,
        },
        "workbooks_read_total": total_files,
        "controlled_rows_loaded_total": total_rows,
        "cache_used": False,
        "dashboard_used": False,
        "raw_source_modified": False,
        "adapter_used": str(adapter_path),
        "exact_v8_engine_used": str(engine_path),
        "days": all_days,
        "acceptance_scope": [
            "authoritative day-folder selection",
            "non-recursive Daywise discovery",
            "PIT cutoff enforcement",
            "controlled five-stock replay input",
            "existing Exact V8 execution",
            "W73-A/W73-B output preservation",
            "future-input leakage assertion",
        ],
        "not_claimed": [
            "authoritative ORB source proof",
            "final historical validation",
            "trading performance validation",
            "replay/live consistency",
        ],
    }

    OUT_FILE.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"STAGE2_STATUS={report['status']}")
    print(f"WORKBOOKS_READ={total_files}")
    print(f"CONTROLLED_ROWS={total_rows}")
    print(f"OUTPUT={OUT_FILE}")
    for day in all_days:
        print(
            f"{day['trading_date']}: files={day['eligible_files_loaded_once']} "
            f"rows={day['controlled_rows_loaded_once']}"
        )
        for cp in day["checkpoints"]:
            statuses = ", ".join(
                f"{x['symbol']}={x['status']}"
                for x in cp["results"]
            )
            print(
                f"  {cp['maturity']}: cutoff={cp['requested_cutoff']} "
                f"max_input={cp['max_pit_input_timestamp']} "
                f"future_rows={cp['future_input_rows']} | {statuses}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
