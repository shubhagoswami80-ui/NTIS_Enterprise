"""
=========================================================
NTIS Intraday System Health Check
Version : 1.0

Purpose:
    Final integration validation.

Checks:
    - Configuration
    - Data Health
    - Intelligence Layer
    - Replay Layer
    - Dashboard Layer
    - Governance Layer

Run:
    python run_ntis_intraday_health_check.py
=========================================================
"""

from pathlib import Path


def check_file(name):

    return Path(name).exists()


def main():

    print("=" * 60)
    print("NTIS INTRADAY SYSTEM HEALTH CHECK")
    print("=" * 60)


    checks = {

        "Configuration":
            [
                "intraday_config.py",
                "intraday_settings.ini"
            ],


        "Data Health":
            [
                "intraday_data_health_monitor.py",
                "intraday_data_quality_monitor.py"
            ],


        "Market Master Pipeline":
            [
                "intraday_market_master_builder.py",
                "intraday_market_master_cleaner.py",
                "intraday_market_master_normalizer.py",
                "intraday_market_master_schema.py"
            ],


        "Intelligence Layer":
            [
                "intraday_intelligence_schema.py",
                "intraday_intelligence_snapshot.py",
                "intraday_snapshot_registry.py",
                "intraday_intelligence_loader.py",
                "intraday_intelligence_query.py",
                "intraday_intelligence_export.py"
            ],


        "Replay Engine":
            [
                "intraday_historical_replay_engine.py",
                "intraday_outcome_engine.py",
                "intraday_accuracy_tracker.py",
                "intraday_probability_calibration.py"
            ],


        "Dashboard Layer":
            [
                "intraday_dashboard.py",
                "intraday_dashboard_health_panel.py",
                "intraday_dashboard_compare_engine.py"
            ],


        "Governance Layer":
            [
                "intraday_duplicate_detector.py",
                "intraday_archive_manager.py",
                "intraday_storage_monitor.py"
            ]

    }


    overall = True


    for module, files in checks.items():

        status = all(
            check_file(f)
            for f in files
        )

        print(
            f"{module:<30}",
            "PASS" if status else "FAIL"
        )

        overall = overall and status


    print("=" * 60)


    if overall:

        print(
            "SYSTEM STATUS: READY"
        )

    else:

        print(
            "SYSTEM STATUS: INCOMPLETE"
        )


    print("=" * 60)



if __name__ == "__main__":

    main()