from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
TARGET = ROOT
DASHBOARD = TARGET / "dashboard.py"
BACKUP = TARGET / "dashboard.py.v13_preintegration.bak"
SRC_PACKAGE = ROOT / "ntis_dashboard_evidence"
DST_PACKAGE = TARGET / "ntis_dashboard_evidence"

IMPORT_ANCHOR = "from dashboard_evidence_bridge import build_live_evidence, resolve_alert_runtime\n"
IMPORT_LINE = "from ntis_dashboard_evidence.renderer import render_ntis_evidence_surface\n"
CALL_ANCHOR = "            _render_evidence(selected)\n"
CALL_REPLACEMENT = '''            _render_evidence(selected)\n\n            # V13 additive NTIS evidence surface. Presentation only: it consumes\n            # the V12 evidence package/cache and never changes SDL selection.\n            try:\n                _ntis_live_date = str(\n                    lifecycle_trading_date\n                    or st.session_state.get("ds_trading_date", "")\n                )\n                render_ntis_evidence_surface(\n                    result=result,\n                    selected_symbol=str(symbol),\n                    trading_date=_ntis_live_date,\n                    snapshot_results=snapshot_results,\n                    snapshot_label=snapshot_label,\n                )\n            except Exception as exc:\n                st.warning(\n                    f"NTIS evidence surface unavailable: {type(exc).__name__}: {exc}"\n                )\n'''



REQUIRED_COMPONENTS = (
    "rsi_momentum", "stock_state", "pit_differential",
    "eod_unusual_activity", "historical_outcome", "pdna_ranking",
    "alert_chart_integration", "evidence_orchestrator", "ntis_integration",
)

def recover_missing_components() -> None:
    recovery = ROOT / "recovery"
    for name in REQUIRED_COMPONENTS:
        target = TARGET / name
        source = recovery / name
        if target.exists():
            print(f"Component present: {name}")
            continue
        if not source.exists():
            raise SystemExit(f"Required component missing from bundle: {name}")
        shutil.copytree(source, target)
        print(f"Recovered missing component: {name}")

def copy_package() -> None:
    if not SRC_PACKAGE.is_dir():
        raise SystemExit(f"Missing bundle package: {SRC_PACKAGE}")
    # The bundle is extracted directly into derivative_signal, so the package is
    # already at its final location. Do not overwrite an existing deployment.
    print(f"Evidence UI package: {DST_PACKAGE}")


def patch_dashboard() -> bool:
    if not DASHBOARD.is_file():
        raise SystemExit(f"dashboard.py not found: {DASHBOARD}")
    text = DASHBOARD.read_text(encoding="utf-8")
    changed = False
    if IMPORT_LINE.strip() not in text:
        if IMPORT_ANCHOR not in text:
            raise SystemExit("V12 evidence bridge import anchor not found; refusing V13 patch.")
        text = text.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_LINE, 1)
        changed = True
    if "render_ntis_evidence_surface(" not in text:
        if CALL_ANCHOR not in text:
            raise SystemExit("Decision evidence inspector anchor not found; refusing V13 patch.")
        text = text.replace(CALL_ANCHOR, CALL_REPLACEMENT, 1)
        changed = True
    if changed:
        if not BACKUP.exists():
            shutil.copy2(DASHBOARD, BACKUP)
        DASHBOARD.write_text(text, encoding="utf-8")
    return changed


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, cwd=TARGET, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    print("NTIS V13 FINAL DASHBOARD DEPLOYMENT")
    print(f"Target: {TARGET}")
    recover_missing_components()
    copy_package()
    changed = patch_dashboard()
    print("Dashboard patch:", "APPLIED" if changed else "ALREADY PRESENT")
    print("Backup:", BACKUP if BACKUP.exists() else "not created (already deployed)")
    run([sys.executable, "-m", "compileall", "dashboard.py", "ntis_dashboard_evidence"])
    run([sys.executable, "-m", "pytest", "ntis_dashboard_evidence/tests", "-q"])
    print("V13 DEPLOYMENT + VALIDATION: PASS")
    print("Git was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
