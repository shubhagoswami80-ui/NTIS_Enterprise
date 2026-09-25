
from __future__ import annotations

from pathlib import Path
import shutil

DASHBOARD = Path(__file__).resolve().parent / "dashboard.py"

IMPORT_ANCHOR = "from decision_evidence import merge_evidence, enrich_decision\n"
IMPORT_LINE = "from dashboard_evidence_bridge import build_live_evidence, resolve_alert_runtime\n"

HOOK_ANCHOR = """            else:
                result.attrs["retracement_disabled_for_live"] = True
            result.attrs["replay_lifecycle_events"] = _point_lifecycle_from_state(
"""

HOOK_REPLACEMENT = """            else:
                result.attrs["retracement_disabled_for_live"] = True

            # V12 additive evidence bridge. This runs only after the frozen SDL
            # result and optional retracement layer have completed. It cannot
            # remove, reorder, rank, qualify, or gate SDL rows.
            try:
                _pit_frames = [
                    frame for key, frame in cached_snapshots.items()
                    if str(key).startswith("logical::")
                    and isinstance(frame, pd.DataFrame)
                    and not frame.empty
                ]
                _pit_history = (
                    pd.concat(_pit_frames, ignore_index=True)
                    if _pit_frames else pd.DataFrame()
                )
                _alert_db = STATE_JSON.with_name("alerts.db")
                _rules, _alert_store, _alert_build_context, _alert_evaluate_snapshot = (
                    resolve_alert_runtime(
                        dashboard_file=__file__,
                        store_path=_alert_db if _alert_db.is_file() else None,
                    )
                )
                _evidence_package = build_live_evidence(
                    result=result,
                    trading_date=str(trading_date),
                    observation_timestamp=pd.Timestamp(timestamp),
                    history_by_symbol=history_by_symbol,
                    retracement_rows=result.to_dict(orient="records"),
                    pit_history=_pit_history,
                    historical_observations=_pit_history,
                    pdna_rows=day.get("pdna_evidence"),
                    alert_rules=_rules,
                    previous_by_symbol=(
                        {
                            str(row.get("symbol", "")).upper(): row
                            for row in previous
                            if isinstance(row, dict) and str(row.get("symbol", "")).strip()
                        }
                        if isinstance(previous, list)
                        else {}
                    ),
                    alert_build_context=_alert_build_context,
                    alert_evaluate_snapshot=_alert_evaluate_snapshot,
                    alert_store=_alert_store,
                )
                result.attrs["ntis_evidence_package"] = _evidence_package
                st.session_state[
                    f"_ntis_live_evidence::{trading_date}::{pd.Timestamp(timestamp).isoformat()}"
                ] = _evidence_package
            except Exception as exc:
                # Evidence layers are strictly fault-isolated from the frozen
                # decision path.
                result.attrs["ntis_evidence_bridge_error"] = (
                    f"{type(exc).__name__}: {exc}"[:240]
                )

            result.attrs["replay_lifecycle_events"] = _point_lifecycle_from_state(
"""

def main() -> int:
    if not DASHBOARD.is_file():
        print(f"dashboard.py not found: {DASHBOARD}")
        return 2
    text = DASHBOARD.read_text(encoding="utf-8")
    if IMPORT_LINE.strip() in text:
        print("V12 import already present; no change.")
        return 0
    if IMPORT_ANCHOR not in text:
        print("Import anchor not found; refusing to patch.")
        return 3
    if HOOK_ANCHOR not in text:
        print("LIVE retracement hook anchor not found; refusing to patch.")
        return 4

    backup = DASHBOARD.with_name("dashboard.py.v12_preintegration.bak")
    shutil.copy2(DASHBOARD, backup)
    text = text.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_LINE, 1)
    text = text.replace(HOOK_ANCHOR, HOOK_REPLACEMENT, 1)
    DASHBOARD.write_text(text, encoding="utf-8")
    print(f"Patched: {DASHBOARD}")
    print(f"Backup: {backup}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
