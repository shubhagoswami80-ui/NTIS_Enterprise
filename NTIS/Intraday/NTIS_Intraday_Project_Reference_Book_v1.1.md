# NTIS Intraday Project Reference Book

## Version 1.1

Date: 2026-07-22

Scope: NTIS Intraday Pipeline Only

This document is the reference point for future continuation,
troubleshooting, and enhancements.

------------------------------------------------------------------------

# 1. Project Objective

Build an independent intraday intelligence pipeline for NSE market
reports.

Purpose:

-   Import intraday XLS/XLSX reports
-   Build market master
-   Normalize data
-   Generate intraday scoring
-   Detect patterns
-   Calculate probability
-   Validate trade candidates
-   Generate daily report

Important Rule:

Intraday modules must not modify the existing EOD NTIS pipeline.

------------------------------------------------------------------------

# 2. Default Module Location

All Intraday Python modules:

E:`\NSE`{=tex}\_Daily_Analysis`\NTIS`{=tex}`\Intraday`{=tex}\

------------------------------------------------------------------------

# 3. Current Architecture

NSE Intraday Reports

↓

current_report_importer.py

↓

intraday_market_master_builder.py

↓

intraday_market_master_cleaner.py

↓

intraday_market_master_normalizer.py

↓

intraday_market_master_schema.py

↓

intraday_scoring_engine.py

↓

intraday_pattern_engine.py

↓

intraday_probability_engine.py

↓

intraday_trade_validation_engine.py

↓

intraday_daily_report_generator.py

------------------------------------------------------------------------

# 4. Completed Modules

## Import Framework

Status: COMPLETED

Purpose:

-   Discover XLS/XLSX reports
-   Identify report types
-   Create import outputs

------------------------------------------------------------------------

## Market Master Builder

File:

intraday_market_master_builder.py

Output:

intraday_market_master_latest.csv

Validation:

1054 rows 75 columns

------------------------------------------------------------------------

## Market Master Cleaner

File:

intraday_market_master_cleaner.py

Output:

intraday_market_master_clean.csv

Validation:

836 rows 58 columns

------------------------------------------------------------------------

## Schema Normalization

Files:

intraday_market_master_normalizer.py

intraday_market_master_schema.py

Output:

intraday_market_master_schema.csv

Validation:

218 rows 17 columns

Final schema:

-   Symbol
-   Price
-   Price Chg %
-   OI
-   OI Chg %
-   PCR
-   ATM Straddle %
-   IV Chg
-   IV Chg %
-   Fut OI
-   Fut OI Chg
-   Fut OI Chg %
-   Fut Buildup
-   Volume
-   Volume Chg %
-   Report_Type
-   Source_File

------------------------------------------------------------------------

# 5. Intelligence Layer

## Intraday Scoring Engine

File:

intraday_scoring_engine.py

Output:

intraday_scored_stocks.csv

Adds:

-   NTIS Intraday Score
-   Trade Bias
-   Reason

------------------------------------------------------------------------

## Intraday Pattern Engine

File:

intraday_pattern_engine.py

Output:

intraday_pattern_analysis.csv

Patterns:

-   Fresh Long Buildup
-   Short Buildup
-   Short Covering
-   Long Unwinding
-   Volume Expansion
-   Futures setups

------------------------------------------------------------------------

## Intraday Probability Engine

File:

intraday_probability_engine.py

Output:

intraday_probability_analysis.csv

Adds:

-   Intraday Probability %
-   Confidence
-   Final Bias

------------------------------------------------------------------------

## Intraday Trade Validation

File:

intraday_trade_validation_engine.py

Output:

intraday_trade_candidates.csv

Adds:

-   Validation Signal
-   Risk Level
-   Entry Price
-   Stop Loss
-   Target

------------------------------------------------------------------------

## Intraday Daily Report Generator

File:

intraday_daily_report_generator.py

Output:

intraday_daily_trade_report.xlsx

Report sections:

-   Summary
-   BUY Candidates
-   SELL Candidates
-   Watchlist

------------------------------------------------------------------------

# 6. Current Output Location

Example:

E:`\NSE`{=tex}\_Daily_Analysis`\Intraday`{=tex}`\Output`{=tex}\\2026-07-22\

Generated files:

-   intraday_market_master_schema.csv
-   intraday_scored_stocks.csv
-   intraday_pattern_analysis.csv
-   intraday_probability_analysis.csv
-   intraday_trade_candidates.csv
-   intraday_daily_trade_report.xlsx

------------------------------------------------------------------------

# 7. Current Milestone Status

Sprint 6A: Import Framework COMPLETED

Sprint 6B: Market Master and Schema Layer COMPLETED

Sprint 6C: Intraday Scoring Engine COMPLETED

Sprint 6D: Pattern Engine COMPLETED

Sprint 6E: Probability Engine COMPLETED

Sprint 6F: Trade Validation Engine COMPLETED

Sprint 6G: Daily Report Generator COMPLETED

------------------------------------------------------------------------

# 8. Future Enhancement Roadmap

Phase 2:

## 1. Intraday Accuracy Tracker

Purpose:

-   Track generated signals
-   Compare actual price movement
-   Measure accuracy

------------------------------------------------------------------------

## 2. Historical Replay Engine

Purpose:

-   Replay previous intraday sessions
-   Test scoring behaviour
-   Improve calibration

------------------------------------------------------------------------

## 3. Live Refresh Framework

Purpose:

-   Multiple intraday snapshots
-   Morning/midday/closing comparison

------------------------------------------------------------------------

## 4. Dashboard Layer

Purpose:

-   Visual ranking
-   Probability view
-   Risk dashboard

------------------------------------------------------------------------

# 9. Development Rules

-   Preserve working modules
-   Add incremental modules only
-   Keep Intraday and EOD separate
-   Validate every milestone
-   Update this reference book after major changes

------------------------------------------------------------------------

# Change Log

Version 1.1

Added:

-   Complete Intraday pipeline documentation
-   All completed milestone records
-   Current architecture
-   Future enhancement roadmap
