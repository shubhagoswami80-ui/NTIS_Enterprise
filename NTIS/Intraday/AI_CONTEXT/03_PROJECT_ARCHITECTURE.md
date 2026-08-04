# NTIS Intraday
# PROJECT ARCHITECTURE

Version : 1.0

Status : FROZEN

------------------------------------------------------------
SYSTEM LAYERS
------------------------------------------------------------

Configuration

↓

Pipeline

↓

Learning

↓

Historical Intelligence

↓

Replay

↓

Dashboard

↓

Governance

↓

Scanner

------------------------------------------------------------
CONFIGURATION
------------------------------------------------------------

intraday_settings.ini

config_loader.py

intraday_execution_context.py

intraday_config.py

intraday_path_config.py

------------------------------------------------------------
PIPELINE
------------------------------------------------------------

current_report_importer

↓

intraday_market_master_builder

↓

intraday_market_master_cleaner

↓

intraday_market_master_normalizer

↓

intraday_market_master_schema

↓

intraday_scoring_engine

↓

intraday_pattern_engine

↓

intraday_probability_engine

↓

intraday_trade_validation_engine

↓

intraday_daily_report_generator

↓

intraday_snapshot_evolution_engine

------------------------------------------------------------
LEARNING
------------------------------------------------------------

intraday_trade_memory_connector

↓

intraday_learning_memory_builder

↓

intraday_learning_outcome_updater

↓

pattern_statistics_engine

------------------------------------------------------------
HISTORICAL INTELLIGENCE
------------------------------------------------------------

pattern_statistics_engine

↓

intraday_intelligence_loader

↓

intraday_intelligence_query

------------------------------------------------------------
REPLAY
------------------------------------------------------------

intraday_historical_replay_engine

↓

intraday_outcome_engine

------------------------------------------------------------
DASHBOARD
------------------------------------------------------------

intraday_dashboard.py

↓

dashboard_loader.py

↓

dashboard_sidebar.py

↓

dashboard_snapshot_viewer.py

↓

dashboard_compare_engine.py

↓

dashboard_health_panel.py

------------------------------------------------------------
GOVERNANCE
------------------------------------------------------------

File Registry

↓

Quality Monitor

↓

Health Monitor

↓

Archive

↓

Validation

------------------------------------------------------------
SCANNER
------------------------------------------------------------

NTIS_Intraday_Scanner

Purpose

Project inspection only.

Not part of production pipeline.

------------------------------------------------------------
FROZEN DECISIONS
------------------------------------------------------------

Architecture frozen.

Business rules frozen.

Dashboard design frozen.

Workspace frozen.

Git disabled.

Runtime folders remain external.

Configuration driven paths only.

Documentation follows implementation.