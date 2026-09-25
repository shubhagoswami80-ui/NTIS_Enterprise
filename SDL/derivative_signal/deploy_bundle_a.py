from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DASHBOARD = ROOT / "dashboard.py"
BACKUP = ROOT / "dashboard.py.bundleA_preintegration.bak"

IMPORT_ANCHOR = "from dashboard_evidence_bridge import build_live_evidence, resolve_alert_runtime\n"
IMPORT_LINE = "from retracement_runtime.integration import enrich_snapshot\n"

LIVE_ANCHOR = '''            # V12 additive evidence bridge. This runs only after the frozen SDL
'''
LIVE_BLOCK = '''            # Bundle A: construct point-in-time RSI/MTF + Stock State from the
            # already-computed snapshot. Retracement remains owned by the existing
            # dashboard lifecycle; this block only reads its state.
            try:
                _lifecycle = result.attrs.get("replay_lifecycle_events", {})
                result, _stock_state_frame = enrich_snapshot(
                    result,
                    history_by_symbol=history_by_symbol,
                    lifecycle_by_symbol=_lifecycle,
                )
                result.attrs["ntis_stock_state_frame"] = _stock_state_frame
            except Exception as exc:
                result.attrs["ntis_intelligence_runtime_error"] = f"{type(exc).__name__}: {exc}"[:240]

'''

REPLAY_ANCHOR = '''        if run_retracement:
            result = _update_retracement_alerts(
                replay_state,
                trading_date,
                result,
                snapshots,
                history_by_symbol,
                durable_prior_state,
            )
            lifecycle_point = _point_lifecycle_from_state(
                replay_state, trading_date, _rank(result)
            )
            result.attrs["replay_lifecycle_events"] = lifecycle_point
        else:
            result.attrs["retracement_disabled_for_live"] = True
            result.attrs["replay_lifecycle_events"] = {}
'''
REPLAY_TARGET = '''            result.attrs["replay_lifecycle_events"] = lifecycle_point
'''
REPLAY_BLOCK = '''            # Bundle A: same RSI/MTF + Stock State composition used by LIVE.
            # Replay uses only history accumulated through this observation.
            try:
                result, _stock_state_frame = enrich_snapshot(
                    result,
                    history_by_symbol=history_by_symbol,
                    lifecycle_by_symbol=lifecycle_point,
                )
                result.attrs["ntis_stock_state_frame"] = _stock_state_frame
            except Exception as exc:
                result.attrs["ntis_intelligence_runtime_error"] = f"{type(exc).__name__}: {exc}"[:240]
'''

def run(*args: str) -> None:
    print("$", sys.executable, *args)
    p = subprocess.run([sys.executable, *args], cwd=ROOT, check=False)
    if p.returncode:
        raise SystemExit(p.returncode)

def main() -> int:
    if not DASHBOARD.is_file():
        raise SystemExit("dashboard.py not found; refusing deployment")
    text = DASHBOARD.read_text(encoding="utf-8")
    if IMPORT_LINE.strip() not in text:
        if IMPORT_ANCHOR not in text:
            raise SystemExit("V12/V13 evidence bridge import anchor not found; refusing patch")
        text = text.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_LINE, 1)
    if "# Bundle A: construct point-in-time RSI/MTF + Stock State" not in text:
        if text.count(LIVE_ANCHOR) != 1:
            raise SystemExit("LIVE evidence bridge anchor is ambiguous; refusing patch")
        text = text.replace(LIVE_ANCHOR, LIVE_BLOCK + LIVE_ANCHOR, 1)
    if "# Bundle A: same RSI/MTF + Stock State composition used by LIVE." not in text:
        if text.count(REPLAY_ANCHOR) != 1:
            raise SystemExit("REPLAY lifecycle anchor is ambiguous; refusing patch")
        text = text.replace(REPLAY_ANCHOR, REPLAY_ANCHOR + REPLAY_BLOCK, 1)
    if not BACKUP.exists():
        shutil.copy2(DASHBOARD, BACKUP)
    DASHBOARD.write_text(text, encoding="utf-8")
    print("Bundle A dashboard patch: APPLIED/VERIFIED")
    print("Backup:", BACKUP)
    run("-m", "compileall", "dashboard.py", "rsi_momentum", "stock_state", "retracement_runtime")
    run("-m", "pytest", "tests", "-q")
    print("BUNDLE A DEPLOYMENT + VALIDATION: PASS")
    print("Git was not modified.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
