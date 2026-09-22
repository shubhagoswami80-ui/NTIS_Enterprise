from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json


def write_cycle_workbook(
    output_path: Path,
    data_rows: list[dict],
    status_rows: list[dict],
    run: dict,
) -> None:
    import pandas as pd

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(data_rows).to_excel(writer, index=False, sheet_name="Data")
        pd.DataFrame(status_rows).to_excel(writer, index=False, sheet_name="Status")
        pd.DataFrame([run]).to_excel(writer, index=False, sheet_name="Run")


def write_manifest(trace_path: Path, manifest: dict) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
