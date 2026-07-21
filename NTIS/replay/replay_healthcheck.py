"""
=========================================================
NTIS Replay Health Check
Version : 1.0
Purpose :
    Verify the Replay Engine installation
    and required components.
=========================================================
"""

from pathlib import Path
import importlib


class ReplayHealthCheck:

    REQUIRED_MODULES = [
        "replay_models",
        "replay_loader",
        "replay_engine",
        "replay_validator",
        "replay_report",
        "replay_logger",
        "replay_metrics",
        "replay_analyzer",
        "replay_filters",
        "replay_exporter",
        "replay_strategy",
        "replay_factory",
        "replay_registry",
        "replay_cache",
        "replay_scheduler",
        "replay_session",
        "replay_context",
        "replay_state",
        "replay_timer",
        "replay_constants",
        "replay_exceptions",
        "replay_utils",
        "replay_version",
    ]

    @staticmethod
    def check_modules():

        status = {}

        for module in ReplayHealthCheck.REQUIRED_MODULES:

            try:
                importlib.import_module(module)
                status[module] = "OK"

            except Exception as ex:
                status[module] = f"FAILED ({ex})"

        return status

    @staticmethod
    def check_folder(folder):

        folder = Path(folder)

        return {
            "Exists": folder.exists(),
            "Files": len(list(folder.glob("*.py")))
        }

    @staticmethod
    def run(folder):

        print("=" * 60)
        print("NTIS REPLAY HEALTH CHECK")
        print("=" * 60)

        folder_status = ReplayHealthCheck.check_folder(folder)

        print("\nReplay Folder")
        print(folder_status)

        print("\nModules")

        results = ReplayHealthCheck.check_modules()

        for module, result in results.items():
            print(f"{module:<30} {result}")

        print("=" * 60)