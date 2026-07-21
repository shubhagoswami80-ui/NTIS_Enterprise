"""
=========================================================
NTIS Replay Dependency Graph
Version : 1.0
Purpose :
    Display module dependencies for the
    Historical Replay Engine.
=========================================================
"""


class ReplayDependencyGraph:

    DEPENDENCIES = {

        "historical_replay": [
            "replay_engine",
            "replay_validator",
            "replay_report",
        ],

        "replay_engine": [
            "replay_loader",
            "replay_strategy",
        ],

        "replay_validator": [
            "replay_metrics",
        ],

        "replay_report": [
            "replay_exporter",
        ],

        "replay_plugin_manager": [
            "replay_plugin",
        ],

        "replay_factory": [
            "replay_strategy",
        ],

        "replay_registry": [
            "replay_factory",
        ],

    }

    @classmethod
    def print(cls):

        print("=" * 60)
        print("NTIS REPLAY DEPENDENCY GRAPH")
        print("=" * 60)

        for module, deps in cls.DEPENDENCIES.items():

            print(f"\n{module}")

            for dep in deps:
                print(f"  └── {dep}")

        print("=" * 60)

    @classmethod
    def modules(cls):

        return sorted(cls.DEPENDENCIES.keys())