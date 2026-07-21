"""
=========================================================
NTIS Replay README
Version : 1.0
Purpose :
    Package documentation and module
    reference for the Replay Engine.
=========================================================
"""

REPLAY_PACKAGE = {
    "Package": "NTIS Replay Engine",
    "Version": "1.0.0",
    "Release": "R1",
    "Modules": [
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
        "replay_manifest",
        "replay_info",
        "replay_bootstrap",
        "test_replay",
    ]
}


def print_readme():

    print("=" * 60)
    print(REPLAY_PACKAGE["Package"])
    print("=" * 60)

    print(f"Version : {REPLAY_PACKAGE['Version']}")
    print(f"Release : {REPLAY_PACKAGE['Release']}")
    print()

    print("Installed Modules")
    print("-" * 60)

    for module in REPLAY_PACKAGE["Modules"]:
        print(module)

    print("-" * 60)
    print(f"Total Modules : {len(REPLAY_PACKAGE['Modules'])}")
    print("=" * 60)


if __name__ == "__main__":
    print_readme()