"""
=========================================================
NTIS Replay Manifest
Version : 1.0
Purpose :
    Central manifest of Replay Engine
    modules and package metadata.
=========================================================
"""

from pathlib import Path


PACKAGE_NAME = "NTIS Replay Engine"

PACKAGE_VERSION = "1.0.0"

PACKAGE_RELEASE = "R1"

PACKAGE_ROOT = Path(__file__).parent


MODULES = [
    "__init__",
    "historical_replay",
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
    "replay_healthcheck",
    "replay_cli",
]


def module_count():

    return len(MODULES)


def module_exists(module_name):

    return (PACKAGE_ROOT / f"{module_name}.py").exists()


def verify():

    return {
        module: module_exists(module)
        for module in MODULES
    }