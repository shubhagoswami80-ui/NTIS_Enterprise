# NTIS Intraday
# MODULE CONTRACTS

Version : 1.0
Status  : ACTIVE

Purpose

Defines the public contract for production modules.

Only update when a module's public interface changes.

------------------------------------------------------------
pattern_statistics_engine.py
------------------------------------------------------------

Purpose

Generate historical statistical summaries for learning.

Inputs

intraday_learning_memory.csv

Outputs

pattern_statistics.csv

Dependencies

config_loader.py

Used By

intraday_intelligence_loader.py

Test

python pattern_statistics_engine.py

------------------------------------------------------------
intraday_intelligence_loader.py
------------------------------------------------------------

Purpose

Load historical intelligence into memory.

Inputs

pattern_statistics.csv

Outputs

Historical Intelligence Cache

Dependencies

pattern_statistics_engine.py

Used By

intraday_intelligence_query.py

Test

python intraday_intelligence_loader.py

------------------------------------------------------------
intraday_intelligence_query.py
------------------------------------------------------------

Purpose

Query historical intelligence.

Inputs

Historical Intelligence Cache

Outputs

Historical Evidence

Dependencies

intraday_intelligence_loader.py

Used By

Trade Validation

Dashboard

Replay

Test

python intraday_intelligence_query.py

------------------------------------------------------------
intraday_historical_replay_engine.py
------------------------------------------------------------

Purpose

Replay historical validated trades.

Inputs

Trade Candidates

EOD OHLC

Outputs

intraday_backtest_results.csv

Dependencies

intraday_outcome_engine.py

Historical Intelligence

Test

python intraday_historical_replay_engine.py

------------------------------------------------------------
intraday_dashboard.py
------------------------------------------------------------

Purpose

Production Dashboard

Dependencies

dashboard_loader.py

dashboard_sidebar.py

dashboard_snapshot_viewer.py

dashboard_compare_engine.py

dashboard_health_panel.py

Test

powershell .\start_intraday_dashboard.ps1