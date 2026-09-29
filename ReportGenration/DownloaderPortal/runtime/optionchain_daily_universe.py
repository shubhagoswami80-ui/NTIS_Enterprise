from __future__ import annotations
import json
from datetime import date
from pathlib import Path
from typing import Any

INVALID_SYMBOL_VALUES = {"", "0", "SELECT", "SELECT SYMBOL"}

def _normalise_symbols(values: list[Any]) -> list[str]:
    result, seen = [], set()
    for value in values:
        symbol = str(value or "").strip().upper()
        if symbol in INVALID_SYMBOL_VALUES or symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
    return result

def universe_directory(output_root: str | Path) -> Path:
    return Path(output_root) / "_universe"

def universe_path(output_root: str | Path, trading_date: date) -> Path:
    return universe_directory(output_root) / f"optionchain_universe_{trading_date:%Y-%m-%d}.json"

async def discover_optionchain_symbols(page) -> list[str]:
    if page is None or page.is_closed():
        raise RuntimeError("Option Chain discovery page is unavailable.")
    values = await page.locator("#optSymbol option").evaluate_all(
        'els => els.map(e => ({value: e.value || "", text: (e.textContent || "").trim()}))'
    )
    raw = []
    for item in values or []:
        if isinstance(item, dict):
            raw.append(str(item.get("value") or "").strip() or str(item.get("text") or "").strip())
    symbols = _normalise_symbols(raw)
    if not symbols:
        raise RuntimeError("No symbols were discovered from #optSymbol.")
    return symbols

def save_daily_universe(output_root: str | Path, trading_date: date, symbols: list[str], *, source_state: str = "LIVE_DISCOVERED") -> tuple[Path, dict[str, Any]]:
    symbols = _normalise_symbols(symbols)
    path = universe_path(output_root, trading_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"schema": "ntis.option_chain.daily_universe.v1", "trading_date": trading_date.isoformat(), "source_state": source_state, "symbol_count": len(symbols), "symbols": symbols}
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return path, metadata

def load_daily_universe(output_root: str | Path, trading_date: date) -> tuple[list[str], dict[str, Any], Path | None]:
    path = universe_path(output_root, trading_date)
    if not path.exists():
        return [], {}, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], {}, path
    metadata = payload if isinstance(payload, dict) else {}
    symbols = _normalise_symbols(metadata.get("symbols", []))
    metadata["symbol_count"] = len(symbols)
    return symbols, metadata, path

async def get_or_create_daily_universe(page, output_root: str | Path, trading_date: date, *, force_refresh: bool = False) -> tuple[list[str], dict[str, Any], Path | None]:
    if not force_refresh:
        symbols, metadata, path = load_daily_universe(output_root, trading_date)
        if symbols:
            metadata = dict(metadata)
            metadata["source_state"] = "FROZEN_DAILY_UNIVERSE"
            return symbols, metadata, path
    symbols = await discover_optionchain_symbols(page)
    path, metadata = save_daily_universe(output_root, trading_date, symbols, source_state="LIVE_DISCOVERED")
    return symbols, metadata, path

def compare_current_to_frozen(current_symbols: list[str], frozen_symbols: list[str]) -> dict[str, Any]:
    current, frozen = _normalise_symbols(current_symbols), _normalise_symbols(frozen_symbols)
    current_set, frozen_set = set(current), set(frozen)
    return {"current_count": len(current), "frozen_count": len(frozen), "added": sorted(current_set - frozen_set), "removed": sorted(frozen_set - current_set), "unchanged_count": len(current_set & frozen_set), "match": current_set == frozen_set}
