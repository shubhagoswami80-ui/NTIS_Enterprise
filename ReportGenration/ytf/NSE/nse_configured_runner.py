from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from nse_config_loader import load_config, get_day_paths


PROJECT_DIR = Path(__file__).resolve().parent


def resolve_config_path(value: str | None) -> Path:
    return Path(value) if value else PROJECT_DIR / "nse_config.json"


def resolve_trade_date(config: dict, supplied: str | None) -> str:
    value = supplied or config.get("runtime", {}).get("trade_date") or ""
    if value:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    return datetime.now().strftime("%Y-%m-%d")


def build_runtime_manifest(config: dict, trade_date: str | None = None) -> dict:
    selected_date = resolve_trade_date(config, trade_date)
    paths = get_day_paths(config, selected_date)
    manifest = {
        "trade_date": selected_date,
        "feed_root": str(Path(config["feed_root"])),
        "day_root": str(paths["day_root"]),
        "raw_root": str(paths["raw_root"]),
        "output_root": str(paths["output_root"]),
        "inputs": {},
    }

    for key, configured_value in config.get("inputs", {}).items():
        if configured_value:
            p = Path(configured_value)
            if not p.is_absolute():
                p = paths["raw_root"] / p
            manifest["inputs"][key] = {
                "path": str(p),
                "exists": p.exists(),
            }
        else:
            manifest["inputs"][key] = {
                "path": "",
                "exists": False,
                "status": "not_configured",
            }

    return manifest


def print_manifest(manifest: dict) -> None:
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve and validate the configured NSE day-wise runtime paths."
    )
    parser.add_argument("--config", help="Path to nse_config.json")
    parser.add_argument("--trade-date", help="Override date in YYYY-MM-DD format")
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Write runtime_paths.json inside the resolved day output folder",
    )
    parser.add_argument(
        "--run",
        nargs=argparse.REMAINDER,
        help=(
            "Optional external command to run after path resolution. "
            "The resolved paths are exposed through NSE_* environment variables."
        ),
    )
    args = parser.parse_args()

    config_path = resolve_config_path(args.config)
    if not config_path.exists():
        print(f"ERROR: Configuration file not found: {config_path}", file=sys.stderr)
        return 2

    config = load_config(config_path)
    manifest = build_runtime_manifest(config, args.trade_date)
    print_manifest(manifest)

    output_root = Path(manifest["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)

    if args.write_manifest:
        manifest_path = output_root / "runtime_paths.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nManifest written: {manifest_path}")

    if args.run:
        env = dict()
        import os
        env.update(os.environ)
        env.update(
            {
                "NSE_TRADE_DATE": manifest["trade_date"],
                "NSE_FEED_ROOT": manifest["feed_root"],
                "NSE_DAY_ROOT": manifest["day_root"],
                "NSE_RAW_ROOT": manifest["raw_root"],
                "NSE_OUTPUT_ROOT": manifest["output_root"],
                "NSE_CONFIG_PATH": str(config_path),
            }
        )
        command = args.run
        print("\nExecuting external command:")
        print(" ".join(command))
        completed = subprocess.run(command, env=env, cwd=str(PROJECT_DIR))
        return completed.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
