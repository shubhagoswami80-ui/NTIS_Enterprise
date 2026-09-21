# NTIS Stock State Composer — Bundle V4

Baseline reviewed: `f052e8390f1da69fefdcf83956a6c19cc50d91ca` on `master`.

## Purpose

This bundle creates an isolated **Stock State Composer**. It combines already-produced SDL, Retracement/Re-entry, and RSI/MTF evidence into a descriptive stock-state object.

It is an evidence/presentation layer only.

## Explicit non-goals

This bundle does **not**:

- change SDL qualification or `_rank()`;
- change candidate selection, scoring, signals, or decision gates;
- change replay/PIT gates;
- change LIVE checkpointing or snapshot processing;
- change Retracement lifecycle rules;
- calculate or replace the existing dashboard RSI implementation;
- add a new stock-selection gate;
- replace `dashboard.py` or `sdl_decision_centre_preview.py`.

Missing evidence is preserved as missing. No forward fill or cross-layer inference is performed.

## Integration model

`SDL result` + `Retracement evidence` + `RSI/MTF evidence` -> `StockState`.

The final `state` field is descriptive precedence for display/audit only. Upstream eligibility remains authoritative.

## Deployment

Copy the `stock_state` directory into:

`E:\NSE_Daily_Analysis\SDL\derivative_signal\stock_state`

Copy tests into:

`E:\NSE_Daily_Analysis\SDL\derivative_signal\stock_state\tests`

Do not overwrite existing dashboard or engine files.
