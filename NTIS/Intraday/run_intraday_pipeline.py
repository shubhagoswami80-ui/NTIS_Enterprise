import subprocess
import sys

modules = [
"current_report_importer.py",
"intraday_market_master_builder.py",
"intraday_market_master_cleaner.py",
"intraday_market_master_normalizer.py",
"intraday_market_master_schema.py",
"intraday_scoring_engine.py",
"intraday_pattern_engine.py",
"intraday_probability_engine.py",
"intraday_trade_validation_engine.py",
"intraday_daily_report_generator.py",
"intraday_accuracy_tracker.py",
"intraday_historical_replay_engine.py",
"intraday_probability_calibration.py",
"intraday_snapshot_evolution_engine.py"
]

for m in modules:
    print("Running:",m)
    r=subprocess.run([sys.executable,m])
    if r.returncode:
        raise SystemExit("FAILED: "+m)

print("NTIS INTRADAY PIPELINE COMPLETE")
