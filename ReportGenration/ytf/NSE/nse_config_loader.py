from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def load_config(config_path: str | Path) -> dict:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_day_paths(config: dict, trade_date: str | None = None) -> dict[str, Path]:
    root = Path(config["feed_root"])
    configured_date = trade_date or config.get("runtime", {}).get("trade_date") or ""
    dt = datetime.strptime(configured_date, "%Y-%m-%d") if configured_date else datetime.now()

    date_root = (
        root
        / dt.strftime(config["date_folder"]["year_format"])
        / dt.strftime(config["date_folder"]["month_format"])
        / dt.strftime(config["date_folder"]["day_format"])
    )
    output_root = date_root / config.get("output_subfolder", "output")

    date_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    return {"day_root": date_root, "raw_root": date_root, "output_root": output_root}
