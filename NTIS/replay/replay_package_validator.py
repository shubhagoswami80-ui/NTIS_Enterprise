"""
=========================================================
NTIS Replay Package Validator
Version : 1.0
Purpose :
    Validate completeness of the
    Historical Replay package.
=========================================================
"""

from pathlib import Path


class ReplayPackageValidator:

    REQUIRED_FILES = [

        "__init__.py",

        "historical_replay.py",

        "replay_models.py",
        "replay_loader.py",
        "replay_engine.py",
        "replay_validator.py",
        "replay_report.py",

        "replay_logger.py",
        "replay_metrics.py",
        "replay_analyzer.py",
        "replay_filters.py",
        "replay_exporter.py",

        "replay_strategy.py",
        "replay_factory.py",
        "replay_registry.py",

        "replay_cache.py",

        "replay_scheduler.py",
        "replay_session.py",

        "replay_context.py",
        "replay_state.py",
        "replay_timer.py",

        "replay_constants.py",
        "replay_enums.py",
        "replay_events.py",

        "replay_hooks.py",
        "replay_observer.py",

        "replay_plugin.py",
        "replay_plugin_manager.py",

        "replay_dependency_graph.py",

        "replay_manifest.py",
        "replay_info.py",
        "replay_banner.py",
        "replay_metadata.py",
        "replay_paths.py",
        "replay_environment.py",
        "replay_diagnostics.py",
        "replay_healthcheck.py",
        "replay_bootstrap.py",
        "replay_cli.py",
        "replay_version.py",
        "replay_utils.py",
        "replay_exceptions.py",

        "test_replay.py",
        "replay_readme.py",

    ]

    @classmethod
    def validate(cls, folder):

        folder = Path(folder)

        missing = []

        for file in cls.REQUIRED_FILES:

            if not (folder / file).exists():
                missing.append(file)

        return missing

    @classmethod
    def report(cls, folder):

        missing = cls.validate(folder)

        print("=" * 60)
        print("NTIS REPLAY PACKAGE VALIDATION")
        print("=" * 60)

        if not missing:

            print("Status : COMPLETE")
            print(f"Modules: {len(cls.REQUIRED_FILES)}")

        else:

            print("Status : INCOMPLETE")
            print()

            for file in missing:
                print(file)

        print("=" * 60)


if __name__ == "__main__":

    ReplayPackageValidator.report(".")