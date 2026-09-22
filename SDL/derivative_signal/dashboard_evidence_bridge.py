from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Callable
import sys

import pandas as pd


EVIDENCE_KEYS = (
    "sdl",
    "retracement",
    "rsi_momentum",
    "stock_state",
    "pit_differential",
    "eod_unusual_activity",
    "historical_outcome",
    "pdna",
    "alerts",
)


def _as_frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [dict(x) for x in value if isinstance(x, Mapping)]
    return []


def _symbol(record: Mapping[str, Any]) -> str:
    return str(record.get("symbol", record.get("Symbol", ""))).strip().upper()


def _timestamp(record: Mapping[str, Any]) -> str:
    raw = record.get("observation_timestamp", record.get("source_timestamp", ""))
    ts = pd.to_datetime(raw, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _history_for_symbol(history_by_symbol: Mapping[str, Any] | None, symbol: str) -> list[Any]:
    if not isinstance(history_by_symbol, Mapping):
        return []
    value = history_by_symbol.get(symbol, history_by_symbol.get(symbol.upper(), []))
    return list(value) if isinstance(value, (list, tuple)) else []


def _load_component_imports():
    """Import only already-deployed evidence packages; return None for absent layers."""
    imports: dict[str, Any] = {}
    for name in (
        "rsi_momentum.integration",
        "stock_state.integration",
        "pit_differential",
        "eod_unusual_activity.integration",
        "historical_outcome.integration",
        "pdna_ranking",
        "ntis_integration.engine",
        "alert_chart_integration",
    ):
        try:
            module = __import__(name, fromlist=["*"])
            imports[name] = module
        except Exception:
            imports[name] = None
    return imports


def _rsi(history: list[Any], timestamp: str, module: Any) -> dict[str, Any]:
    if module is None or not hasattr(module, "build_rsi_evidence"):
        return {}
    try:
        return dict(module.build_rsi_evidence(history, timestamp))
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _stock_state(result: pd.DataFrame, retracement_rows: list[dict[str, Any]],
                 rsi_by_symbol: Mapping[str, Mapping[str, Any]], module: Any) -> pd.DataFrame:
    if module is None or not hasattr(module, "build_stock_state_evidence"):
        return pd.DataFrame()
    records = result.to_dict(orient="records") if isinstance(result, pd.DataFrame) else []
    rt_map = {
        _symbol(x): x for x in retracement_rows
        if isinstance(x, Mapping) and _symbol(x)
    }
    try:
        rows = module.build_stock_state_evidence(
            records,
            retracement_by_symbol=rt_map,
            rsi_by_symbol=rsi_by_symbol,
        )
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def _pit(frame: pd.DataFrame, timestamp: str, module: Any) -> pd.DataFrame:
    if module is None or not hasattr(module, "PITDifferentialEngine"):
        return pd.DataFrame()
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    try:
        return module.PITDifferentialEngine().analyze(frame, timestamp).rows
    except Exception:
        return pd.DataFrame()


def _unusual(pit_rows: pd.DataFrame, module: Any) -> dict[str, Any]:
    if module is None or not hasattr(module, "build_eod_unusual_activity"):
        return {}
    try:
        return dict(module.build_eod_unusual_activity(pit_rows))
    except Exception:
        return {}


def _pdna(pdna_rows: Any, module: Any) -> pd.DataFrame:
    if module is None or not hasattr(module, "rank_pdna_candidates"):
        return pd.DataFrame()
    frame = _as_frame(pdna_rows)
    if frame.empty:
        return frame
    try:
        return module.rank_pdna_candidates(frame)
    except Exception:
        return pd.DataFrame()


def _alerts(
    result: pd.DataFrame,
    trading_date: str,
    timestamp: str,
    rules: Iterable[dict[str, Any]] | None,
    previous_by_symbol: Mapping[str, Mapping[str, Any]] | None,
    module: Any,
    build_context: Callable[..., dict[str, Any]] | None,
    evaluate_snapshot: Callable[..., list[dict[str, Any]]] | None,
    store: Any = None,
) -> list[dict[str, Any]]:
    if not rules or module is None or build_context is None or evaluate_snapshot is None:
        return []
    rows = result.to_dict(orient="records") if isinstance(result, pd.DataFrame) else []
    previous = dict(previous_by_symbol or {})
    try:
        return list(module.integrate_alerts(
            rows,
            rules=rules,
            build_context=build_context,
            evaluate_snapshot=evaluate_snapshot,
            store=store,
            trading_date=trading_date,
            previous_by_symbol=previous,
        ))
    except Exception:
        return []



def resolve_alert_runtime(
    *,
    dashboard_file: str | Path | None = None,
    store_path: str | Path | None = None,
) -> tuple[list[dict[str, Any]], Any, Callable[..., dict[str, Any]] | None, Callable[..., list[dict[str, Any]]] | None]:
    """Resolve the existing Git alert package without copying or changing it.

    Rules are read only from the caller-provided SQLite store path. If no path
    is supplied, no alert evaluation is attempted. This prevents V12 from
    inventing a rule source.
    """
    if dashboard_file is None:
        return [], None, None, None
    dashboard_path = Path(dashboard_file).resolve()
    sdl_root = dashboard_path.parents[1]
    if str(sdl_root) not in sys.path:
        sys.path.insert(0, str(sdl_root))
    try:
        from extensions.alert_chart.integration_adapter import build_context
        from extensions.alert_chart.alert_engine import evaluate_snapshot
        from extensions.alert_chart.alert_store import AlertStore
    except Exception:
        return [], None, None, None

    if store_path is None:
        return [], None, build_context, evaluate_snapshot
    try:
        store = AlertStore(Path(store_path))
        rules = store.list_rules()
        return rules, store, build_context, evaluate_snapshot
    except Exception:
        return [], None, build_context, evaluate_snapshot

def build_live_evidence(
    *,
    result: pd.DataFrame,
    trading_date: str,
    observation_timestamp: Any,
    history_by_symbol: Mapping[str, Any] | None = None,
    retracement_rows: Iterable[Mapping[str, Any]] | None = None,
    pit_history: pd.DataFrame | None = None,
    historical_observations: pd.DataFrame | None = None,
    pdna_rows: pd.DataFrame | None = None,
    alert_rules: Iterable[dict[str, Any]] | None = None,
    previous_by_symbol: Mapping[str, Mapping[str, Any]] | None = None,
    alert_build_context: Callable[..., dict[str, Any]] | None = None,
    alert_evaluate_snapshot: Callable[..., list[dict[str, Any]]] | None = None,
    alert_store: Any = None,
) -> dict[str, Any]:
    """Build additive evidence after the frozen SDL result exists.

    This function is deliberately downstream of SDL selection/ranking.
    Missing/failed evidence layers stay missing; they never block the SDL
    result and never remove or reorder rows.
    """
    frame = _as_frame(result)
    ts = _timestamp({"observation_timestamp": observation_timestamp})
    symbols = sorted({
        _symbol(row) for row in frame.to_dict(orient="records")
        if _symbol(row)
    })

    mods = _load_component_imports()

    rt = [dict(x) for x in (retracement_rows or []) if isinstance(x, Mapping)]
    if not rt and isinstance(frame, pd.DataFrame) and not frame.empty:
        # Accept only already-emitted retracement fields. Never calculate a
        # second retracement lifecycle here.
        rt_fields = {
            c for c in frame.columns
            if c in {"symbol", "Symbol", "lifecycle", "retracement_state",
                     "state", "reentry_state", "reentry", "alert_type",
                     "reentry_alert", "alert_timestamp"}
        }
        if rt_fields & {"lifecycle", "retracement_state", "reentry_state", "reentry", "alert_type"}:
            rt = frame[[c for c in frame.columns if c in rt_fields]].to_dict(orient="records")

    rsi_by_symbol: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        rsi_by_symbol[symbol] = _rsi(
            _history_for_symbol(history_by_symbol, symbol),
            ts,
            mods.get("rsi_momentum.integration"),
        )

    stock_state = _stock_state(
        frame,
        rt,
        rsi_by_symbol,
        mods.get("stock_state.integration"),
    )

    pit_rows = _pit(
        pit_history if isinstance(pit_history, pd.DataFrame) else pd.DataFrame(),
        ts,
        mods.get("pit_differential"),
    )
    unusual = _unusual(pit_rows, mods.get("eod_unusual_activity.integration"))

    outcomes = pd.DataFrame()
    outcome_mod = mods.get("historical_outcome.integration")
    if (
        outcome_mod is not None
        and isinstance(historical_observations, pd.DataFrame)
        and not historical_observations.empty
        and not pit_rows.empty
    ):
        events = pit_rows.copy()
        events["event_timestamp"] = pd.to_datetime(
            events.get("current_timestamp"), errors="coerce"
        )
        events["event_price"] = pd.to_numeric(
            events.get("current_value"), errors="coerce"
        )
        try:
            outcomes = outcome_mod.build_historical_outcome_evidence(
                events, historical_observations
            ).get("outcomes", pd.DataFrame())
        except Exception:
            outcomes = pd.DataFrame()

    pdna = _pdna(pdna_rows, mods.get("pdna_ranking"))

    alerts = _alerts(
        frame,
        str(trading_date),
        ts,
        alert_rules,
        previous_by_symbol,
        mods.get("ntis_integration.engine"),
        alert_build_context,
        alert_evaluate_snapshot,
        alert_store,
    )

    # Use the already-validated V11 composer if present. The fallback is the
    # same additive schema and keeps SDL authoritative.
    composer = mods.get("ntis_integration.engine")
    if composer is not None and hasattr(composer, "compose_evidence"):
        package = composer.compose_evidence(
            sdl=frame,
            retracement=rt,
            rsi_momentum=rsi_by_symbol,
            stock_state=stock_state,
            pit_differential=pit_rows,
            eod_unusual_activity=unusual,
            historical_outcome=outcomes,
            pdna=pdna,
            alerts=alerts,
            trading_date=str(trading_date),
            observation_timestamp=ts,
            symbol=None,
        )
    else:
        package = {
            "schema_version": 1,
            "symbol": None,
            "trading_date": str(trading_date),
            "observation_timestamp": ts,
            "evidence": {},
            "selection_gate": False,
            "decision_owner": "SDL",
        }

    package["evidence"]["sdl"] = frame
    package["evidence"]["retracement"] = pd.DataFrame(rt)
    package["evidence"]["rsi_momentum"] = pd.DataFrame(
        [{"symbol": s, **v} for s, v in rsi_by_symbol.items()]
    )
    package["evidence"]["stock_state"] = stock_state
    package["evidence"]["pit_differential"] = pit_rows
    package["evidence"]["eod_unusual_activity"] = unusual
    package["evidence"]["historical_outcome"] = outcomes
    package["evidence"]["pdna"] = pdna
    package["evidence"]["alerts"] = pd.DataFrame(alerts)
    package["evidence_status"] = {
        key: bool(
            not _as_frame(package["evidence"].get(key)).empty
            if key not in {"rsi_momentum", "alerts"}
            else len(_rows(package["evidence"].get(key))) > 0
        )
        for key in EVIDENCE_KEYS
    }
    package["evidence_status"]["sdl"] = not frame.empty
    package["selection_gate"] = False
    package["decision_owner"] = "SDL"
    return package
