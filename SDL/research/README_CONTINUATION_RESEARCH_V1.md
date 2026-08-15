# SDL Continuation Research V1 — Authoritative Master Baseline

Baseline:
`bda7958e4616a611c196df615c95b83e6dc6ea4a`
`SDL current authoritative development state`

This is research-only.

## Production protection

The module does not modify:
- `pipeline.py`
- `approaching_breakout.py`
- `app.py`
- `processing_state.json`
- `approaching_breakouts.csv`
- Phase-1 breakout semantics

## Research question

For each first 50% approaching-breakout event:

> Does a later same-day observation cross the frozen 1x breakout boundary in the same direction?

Same-observation 100% is kept as a separate edge case and excluded from the clean continuation rate.

## Current authoritative evidence schema

The current `storage.save_daily_evidence()` persists:
- trading_date
- observation_timestamp
- Symbol
- Open/High/Low/Close
- ATM Straddle %
- current_price
- opening_straddle_premium
- upper/lower frozen breakout levels
- breakout flags/direction
- Price Chg %
- IV Chg %
- OI Chg %
- PCR Chg %

The project source contract separately identifies richer source families containing futures OI/change/buildup, IVR/IVP, HV, IV/HV, strike/distance and support/resistance. These are mapped only when their physical workbook headers are found.

## Run

From:
`E:\NSE_Daily_Analysis\SDL`

```powershell
python research\continuation_research.py 2026-08-12 2026-08-13
```

Outputs:
`data\output\continuation_research\`

No probability or arbitrary weighting is generated.
